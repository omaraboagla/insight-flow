"""Schema grounding: BM25 plus embeddings, never row arithmetic."""
import math,re
from collections import Counter
import numpy as np

def tokens(text):return re.findall(r'[a-z0-9]+',str(text).lower())

def bm25(question,documents):
    docs=[tokens(d) for d in documents]; query=tokens(question)
    avg=sum(map(len,docs))/max(1,len(docs)); scores=[]
    for doc in docs:
        count=Counter(doc);score=0
        for word in query:
            df=sum(word in d for d in docs); idf=math.log(1+(len(docs)-df+.5)/(df+.5))
            freq=count[word];score+=idf*freq*2.5/(freq+1.5*(.25+.75*len(doc)/max(1,avg)))
        scores.append(score)
    return np.asarray(scores)

def cosine(query,vectors):
    vectors=np.asarray(vectors,dtype=float);query=np.asarray(query,dtype=float)
    return vectors@query/(np.linalg.norm(vectors,axis=1)*np.linalg.norm(query)+1e-10)

class Retriever:
    def __init__(self): self.card_cache={};self.value_cache={}
    def select(self,question,cards,tables,relationships,gemini,usage,schema_only=False):
        all_count=sum(len(c['columns']) for c in cards)
        matches=[]
        if all_count<60: chosen=cards
        else:
            documents=[c['table']+' '+' '.join(col['original_name'] for col in c['columns']) for c in cards]
            lexical=bm25(question,documents)
            key=tuple(documents)
            if key not in self.card_cache:self.card_cache[key]=gemini.embed(documents,usage)
            query=gemini.embed([question],usage)[0];scores=lexical/max(1,float(lexical.max()))+cosine(query,self.card_cache[key])
            chosen=[cards[i] for i in np.argsort(scores)[-min(5,len(cards)):][::-1]]
            names={c['table'] for c in chosen}
            # Include connecting dimensions for safe joins.
            for r in relationships:
                if r['from_table'] in names or r['to_table'] in names:names.update((r['from_table'],r['to_table']))
            chosen=[c for c in cards if c['table'] in names]
        if not schema_only:
            # Embedding distinct names gives fuzzy entity grounding; values remain data.
            entries=[]
            for card in chosen:
                table=tables[card['table']]
                for col in table.columns:
                    if col['type']=='text' and col['distinct_count']>50 and re.search(r'name|description|product|customer',col['name']):
                        entries.extend((table.name,col['name'],str(v)[:60]) for v in table.frame[col['name']].dropna().unique()[:1000])
            if entries:
                key=tuple(entries)
                if key not in self.value_cache:
                    vectors=[]
                    for start in range(0,len(entries),100):vectors.extend(gemini.embed([e[2] for e in entries[start:start+100]],usage))
                    self.value_cache[key]=vectors
                query=gemini.embed([question],usage)[0];scores=cosine(query,self.value_cache[key])
                matches=[dict(table=entries[i][0],column=entries[i][1],value=entries[i][2]) for i in np.argsort(scores)[-5:][::-1] if scores[i]>.35]
        return chosen,matches
