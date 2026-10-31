"""Manufactured boundary stress test. It measures evidence coverage, not LLM accuracy."""
import json
import re
import numpy as np
from .chunking import split_children
from .embeddings import embed
from .retrieval import fuse
from .config import ROOT

def run():
    import sqlite3
    fixtures=[]
    for i in range(8):
        words=('The appendix describes standard operational procedures and record keeping. '*40).split()[:250]
        prefix=' '.join(words)+'. '
        code=f'ZQX-{100+i}';answer=f'{14+i} calendar days'
        clause=f'For SKU {code}, cancellation must be requested '
        clause+=' '.join(('under the standard administrative process described in this fictional agreement and its supporting documentation '*8).split()[:70])
        clause+=f' at least {answer} before renewal.'
        text=prefix+clause+' Confidential internal note: CANARY_STRESS_'+str(i)+'.'
        fixtures.append({'code':code,'answer':answer,'text':text,'question':f'How much cancellation notice is required for SKU {code}?'})
    report={'scope':'8 manufactured long-sentence/rare-ID boundary stress fixtures; not representative answer accuracy','variants':{}}
    for kind in ('fixed','sentence','semantic'):
        chunks=[];owners=[]
        for index,item in enumerate(fixtures):
            if kind=='fixed':
                words=item['text'].split();parts=[' '.join(words[i:i+300]) for i in range(0,len(words),260)]
            else:parts=[p[0] for p in split_children(item['text'],embedder=embed,semantic=kind=='semantic')]
            chunks.extend(parts);owners.extend([index]*len(parts))
        vectors=np.asarray(embed(chunks));queries=np.asarray(embed([f['question'] for f in fixtures],query=True))
        connection=sqlite3.connect(':memory:')
        connection.execute('CREATE VIRTUAL TABLE search USING fts5(text)')
        connection.executemany('INSERT INTO search(rowid,text) VALUES (?,?)',[(i,t) for i,t in enumerate(chunks)])
        for hybrid in (False,True):
            coverage=0;parent_coverage=0;details=[]
            for i,item in enumerate(fixtures):
                dense=np.argsort(-(vectors@queries[i])).tolist()
                expression=' OR '.join('"'+t+'"' for t in re.findall(r'\w+(?:-\w+)*',item['question']))
                lexical=[r[0] for r in connection.execute('SELECT rowid FROM search WHERE search MATCH ? ORDER BY bm25(search)',(expression,))]
                order=fuse(dense,lexical) if hybrid else dense
                top=order[0];text=chunks[top];parent=fixtures[owners[top]]['text']
                complete=item['code'] in text and item['answer'] in text
                expanded=item['code'] in parent and item['answer'] in parent
                coverage+=complete;parent_coverage+=expanded
                details.append({'code':item['code'],'child_contains_identifier_and_fact':complete,'parent_contains_identifier_and_fact':expanded})
            name=kind+('-hybrid' if hybrid else '-dense')
            report['variants'][name]={'child_coverage_at_1':coverage,'parent_coverage_at_1':parent_coverage,'cases':8,'details':details}
        connection.close()
    (ROOT/'reports/retrieval-stress.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:{a:b for a,b in v.items() if a!='details'} for k,v in report['variants'].items()},indent=2))

if __name__=='__main__':run()
