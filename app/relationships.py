import re

def _key(name):
    raw=re.sub(r'[^a-z0-9]','',name.lower())
    return {'soldby':'employeeid','approvedby':'employeeid'}.get(raw,raw)

def detect_relationships(tables):
    relationships=[]
    for i,a in enumerate(tables.values()):
        for b in list(tables.values())[i+1:]:
            for ca in a.columns:
                key=_key(ca['original_name'])
                if not (key.endswith('id') or key in ('sku','productcode','customercode','suppliercode','employeecode')): continue
                for cb in b.columns:
                    if key!=_key(cb['original_name']): continue
                    va=a.frame[ca['name']].dropna().astype(str); vb=b.frame[cb['name']].dropna().astype(str)
                    sa=set(va); sb=set(vb)
                    if not sa or not sb: continue
                    ua=len(sa)==len(va); ub=len(sb)==len(vb)
                    # Transaction-to-transaction matches are not foreign keys.
                    if not (ua or ub): continue
                    if ua and not ub: parent,pc,pvals,child,cc,cvals=a,ca,sa,b,cb,sb
                    elif ub and not ua: parent,pc,pvals,child,cc,cvals=b,cb,sb,a,ca,sa
                    else:
                        # Prefer the entity named by the key; otherwise require strict subset.
                        entity=key.removesuffix('id').removesuffix('code')
                        if entity and entity in _key(a.file): parent,pc,pvals,child,cc,cvals=a,ca,sa,b,cb,sb
                        elif entity and entity in _key(b.file): parent,pc,pvals,child,cc,cvals=b,cb,sb,a,ca,sa
                        else: continue
                    overlap=len(cvals&pvals)/len(cvals)
                    if overlap>=.95:
                        relationships.append(dict(from_table=child.name,from_column=cc['name'],to_table=parent.name,to_column=pc['name'],overlap=round(overlap,3),kind='many-to-one',confidence=round(overlap,3)))
    return relationships
