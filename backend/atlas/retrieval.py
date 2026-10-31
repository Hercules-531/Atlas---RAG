"""Local dense + SQLite BM25 reciprocal-rank fusion, then local parent expansion."""
import re
import numpy as np
from .store import rows
from .embeddings import collection,embed
from .privacy import terms
from .chunking import sentences,is_record
from .contextual import indexed_text

def fuse(*rankings,k=60):
    scores={}
    for ranking in rankings:
        for rank,key in enumerate(dict.fromkeys(ranking),1):scores[key]=scores.get(key,0)+1/(k+rank)
    return sorted(scores,key=lambda key:(-scores[key],key))

def lexical(question,document_ids=None,limit=24):
    tokens=[t for t in re.findall(r'\w+(?:-\w+)*',question.lower()) if terms(t)][:24]
    if not tokens:return []
    expression=' OR '.join('"'+t.replace('"','""')+'"' for t in tokens)
    args=[expression];scope=''
    if document_ids:
        scope=' AND c.document_id IN ('+','.join('?' for _ in document_ids)+')';args.extend(document_ids)
    args.append(limit)
    return [r['chunk_id'] for r in rows('SELECT chunks_fts.chunk_id FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.chunk_id JOIN documents d ON d.id=c.document_id WHERE chunks_fts MATCH ? AND d.status="ready"'+scope+' ORDER BY bm25(chunks_fts) LIMIT ?',args)]

def retrieve(question,document_ids=None,method='hybrid',parent=True,compress=True):
    vector=embed([question],query=True)[0]
    dense=collection().query(query_embeddings=[vector],n_results=24,**({'where':{'document_id':{'$in':document_ids}}} if document_ids else {}))['ids'][0]
    ids=fuse(dense,lexical(question,document_ids)) if method=='hybrid' else dense
    result=[];seen=set()
    for key in ids:
        found=rows('SELECT c.*,d.name,p.id AS parent_id,p.text AS parent_text,p.location AS parent_location,cc.context AS index_context FROM chunks c JOIN documents d ON d.id=c.document_id LEFT JOIN chunk_parents cp ON cp.chunk_id=c.id LEFT JOIN parents p ON p.id=cp.parent_id LEFT JOIN chunk_contexts cc ON cc.chunk_id=c.id WHERE c.id=? AND d.status="ready"',(key,))
        if not found:continue
        item=found[0];identity=item['parent_id'] if parent and item['parent_id'] else item['id']
        if identity in seen:continue
        seen.add(identity)
        if parent and item['parent_text']:
            item['child_text']=item['text'];item['text']=item['parent_text'];item['location']=item['parent_location']
        result.append(item)
        if len(result)==8:break
    # An explicit multiword source-name match narrows ambiguous agreements/versions.
    # Names and index context remain local; evidence text is never prefixed for generation.
    if any(c.get('index_context') for c in result):
        from pathlib import Path
        scores=[len(terms(Path(c['name']).stem)&terms(question)) for c in result]
        best=max(scores,default=0)
        if best>=2:result=[c for c,score in zip(result,scores) if score==best]
    if compress:compress_sentences(question,result,vector)
    return result

def compress_sentences(question,chunks,query_vector=None):
    """Extractive contextual compression; no LLM calls, no rewritten facts."""
    candidates=[]
    overview=bool(re.search(r'(?i)^\s*(what\s+(is|are)|what.s|explain|describe|summari[sz]e|give.*overview)\b',question))
    definition=r'(?i)\b(introduces?|propos(?:e|es|ed)|method|framework|approach|designed to|combines?|leverages?)\b'
    for ci,chunk in enumerate(chunks):
        if is_record(chunk['text']):continue
        units=sentences(chunk['text']);chunk['sentence_units']=[u[0] for u in units]
        # Bound local work while favoring lexical matches across the entire parent.
        substantive=[i for i,u in enumerate(units) if len(u[0].split())>=5]
        pool=substantive or list(range(len(units)))
        ranked=sorted(pool,key=lambda i:len(terms(units[i][0])&terms(question)),reverse=True)[:12]
        candidates.extend((ci,i,units[i][0]) for i in ranked)
    if not candidates:return
    query=np.asarray(query_vector if query_vector is not None else embed([question],query=True)[0])
    vectors=np.asarray(embed([indexed_text(chunks[ci].get('index_context') or '',text) for ci,_,text in candidates]))
    scored={}
    for (ci,i,text),v in zip(candidates,vectors):
        overlap=len(terms(text)&terms(question))/max(1,len(terms(question)))
        scope_overlap=len(terms(chunks[ci].get('index_context') or '')&terms(question))/max(1,len(terms(question)))
        cosine=float(v@query)
        boost=.14 if overview and re.search(definition,text) else 0
        if overview and len(re.findall(r'\d+(?:\.\d+)?',text))>12:boost-=.25
        scored.setdefault(ci,[]).append((cosine*.65+overlap*.3+scope_overlap*.05+boost,i,cosine,overlap))
    global_scores=sorted([(score,ci,i,cosine,overlap) for ci,values in scored.items() for score,i,cosine,overlap in values],reverse=True)
    best=global_scores[0][0]
    limit=10 if overview else 8
    accepted={(ci,i) for score,ci,i,cosine,overlap in global_scores[:limit] if score>=best*.78 and (cosine>=.4 or overlap>0)}
    for ci,values in scored.items():
        per_parent=5 if overview else 3
        chosen=[i for _,i,_,_ in sorted(values,reverse=True)[:per_parent] if (ci,i) in accepted]
        units=chunks[ci]['sentence_units']
        # Local antecedents retain meaning for short pronoun-led statements.
        for i in chosen.copy():
            if i>0 and re.match(r'(?i)^(it|they|this|that|these|those)\b',units[i]):chosen.append(i-1)
            if overview and len(chosen)<per_parent and re.search(definition,units[i]) and i+1<len(units) and len(units[i+1].split())<=100:chosen.append(i+1)
        chunks[ci]['selected_sentences']=sorted(set(chosen))
        chunks[ci]['retrieval_method']='hybrid BM25+dense; parent expansion; local semantic sentence compression'
