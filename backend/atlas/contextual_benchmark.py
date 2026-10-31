"""Local-only before/after index-context ablation; no answer accuracy claims."""
import json
import sqlite3
import numpy as np
from .config import ROOT
from .embeddings import embed
from .contextual import context_prefix,indexed_text
from .retrieval import fuse

def check_existing(label):
    from .store import rows
    from .retrieval import retrieve
    from .privacy import minimize,restore
    import re,time
    cases=json.loads((ROOT/'demo/gold.json').read_text());result=[];start=time.monotonic()
    for q in cases:
        docs=rows('SELECT id FROM documents WHERE name=? AND status="ready"',(q['dataset'],))
        if not docs:continue
        hits=retrieve(q['question'],[d['id'] for d in docs]);plan=minimize(q['question'],hits)
        result.append({'id':q['id'],'first_parent_retains_fact':bool(hits and q['expected'].lower() in hits[0]['text'].lower()),
            'compressed_fact_retained':q['expected'].lower() in restore(plan['context'],plan['mapping']).lower(),
            'raw_canaries_in_context':len(re.findall(r'CANARY_[A-Z0-9_]+',plan['context']))})
    report={'scope':'Existing 36 gold retrieval cases; fact retention, not generated-answer accuracy','cases':result,'elapsed_seconds':time.monotonic()-start}
    (ROOT/f'reports/contextual-{label}.json').write_text(json.dumps(report,indent=2))
    print(label,len(result),sum(r['first_parent_retains_fact'] for r in result),sum(r['compressed_fact_retained'] for r in result),sum(r['raw_canaries_in_context'] for r in result))

def run():
    projects=['Orion','Lyra','Vela','Cygnus','Draco','Phoenix','Auriga','Carina']
    items=[]
    for i,project in enumerate(projects):
        # Each standalone paragraph loses its project identifier when chunked.
        text=f'The renewal cancellation notice period is {14+i} calendar days.'
        items.append({'name':project+' spacecraft service agreement.pdf','text':text,'parent':text,
            'query':f'What is the renewal cancellation notice period for the {project} spacecraft service agreement?'})
    result={'scope':'8 manufactured ambiguous-agreement fixtures; retrieval ranking only, not generated-answer accuracy','variants':{}}
    queries=np.asarray(embed([x['query'] for x in items],query=True))
    for contextual in (False,True):
        texts=[indexed_text(context_prefix(x['name'],x['parent'],x['text'],'page 2'),x['text']) if contextual else x['text'] for x in items]
        vectors=np.asarray(embed(texts));db=sqlite3.connect(':memory:');db.execute('CREATE VIRTUAL TABLE docs USING fts5(text)')
        db.executemany('INSERT INTO docs(rowid,text) VALUES (?,?)',enumerate(texts))
        dense_correct=0;hybrid_correct=0;details=[]
        import re
        for i,item in enumerate(items):
            dense=np.argsort(-(vectors@queries[i])).tolist()
            expression=' OR '.join('"'+t+'"' for t in re.findall(r'\w+',item['query']))
            lexical=[r[0] for r in db.execute('SELECT rowid FROM docs WHERE docs MATCH ? ORDER BY bm25(docs)',(expression,))]
            hybrid=fuse(dense,lexical)
            dense_correct+=dense[0]==i;hybrid_correct+=hybrid[0]==i
            details.append({'project':projects[i],'dense_correct':dense[0]==i,'hybrid_correct':hybrid[0]==i})
        result['variants']['contextual' if contextual else 'current']={'dense_top1':dense_correct,'hybrid_top1':hybrid_correct,'cases':len(items),'details':details};db.close()
    (ROOT/'reports/contextual-ablation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
