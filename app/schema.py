import hashlib
import json
from .ingest import clean_value

def schema_cards(tables, schema_only=False):
    result=[]
    for table in tables.values():
        columns=[]
        for c in table.columns:
            card={k:v for k,v in c.items() if k not in ('distinct_values','sample_values','values')}
            if not schema_only:
                for field in ('distinct_values','sample_values'):
                    if c.get(field) is not None: card[field]=[str(v)[:60] if isinstance(v,str) else v for v in c[field]][:50 if field=='distinct_values' else 5]
            columns.append(card)
        result.append(dict(table=table.name,file=table.file,sheet=table.sheet,row_count=len(table.frame),columns=columns))
    return result

def schema_hash(tables):
    digest=hashlib.sha256(json.dumps(schema_cards(tables),sort_keys=True,default=str).encode())
    for table in tables.values():
        digest.update(table.frame.to_json(date_format='iso').encode())
    return digest.hexdigest()

def examples(tables):
    chips=[]
    for t in tables.values():
        chips.append(f'How many rows are in {t.file} / {t.sheet}?')
        num=next((c for c in t.columns if c['type'] in ('number','currency') and not c['name'].endswith('id')),None)
        category=next((c for c in t.columns if c['type']=='text' and 1<c['distinct_count']<=20),None)
        if num: chips.append(f'What is the total {num["original_name"]} in {t.file} / {t.sheet}?')
        if category and num: chips.append(f'Show total {num["original_name"]} by {category["original_name"]} in {t.file}.')
    return chips[:12]
