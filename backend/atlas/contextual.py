"""Bounded extractive index context. Never changes original citation evidence."""
import json
import re
from pathlib import Path

VERSION='extractive-index-context-v1'

def context_prefix(name,parent_text,child_text,location):
    # Source names stay local, as do any sensitive values they might contain.
    title=re.sub(r'[_-]+',' ',Path(name).stem).strip()[:180]
    parts=['Document: '+title,'Location: '+location[:100]]
    try:record=json.loads(parent_text)
    except (ValueError,TypeError):record=None
    if isinstance(record,dict):
        parts.append('Record fields: '+', '.join(str(k) for k in record)[:200])
    else:
        # Extract existing opening/heading text, with no generated factual additions.
        lines=[line.strip() for line in parent_text.splitlines() if line.strip()]
        opening=lines[0] if lines else ''
        if opening and not child_text.lstrip().startswith(opening):
            parts.append('Section opening: '+' '.join(opening.split()[:35]))
    text='\n'.join(parts)
    return ' '.join(text.split()[:80])

def indexed_text(context,text):
    return ('Index context: '+context+'\n\n'+text) if context else text

def rebuild():
    """Update existing vectors/FTS in their owning process; preserve all evidence IDs/text."""
    from .store import rows,db
    from .embeddings import collection,embed
    from .ingest import LOCK
    from .llm import DATA_LOCK
    count=0;last='';index=collection()
    with DATA_LOCK,LOCK:
        while True:
            batch=rows('SELECT c.id,c.document_id,c.text,c.location,d.name,COALESCE(p.text,c.text) AS parent_text '
                'FROM chunks c JOIN documents d ON d.id=c.document_id '
                'LEFT JOIN chunk_parents cp ON cp.chunk_id=c.id LEFT JOIN parents p ON p.id=cp.parent_id '
                'WHERE d.status="ready" AND c.id>? ORDER BY c.id LIMIT 8',(last,))
            if not batch:break
            contexts=[context_prefix(r['name'],r['parent_text'],r['text'],r['location']) for r in batch]
            vectors=embed([indexed_text(prefix,r['text']) for prefix,r in zip(contexts,batch)])
            index.upsert(ids=[r['id'] for r in batch],embeddings=vectors,metadatas=[{'document_id':r['document_id']} for r in batch])
            with db() as c:
                for r,prefix in zip(batch,contexts):
                    c.execute('INSERT OR REPLACE INTO chunk_contexts VALUES (?,?,?)',(r['id'],prefix,VERSION))
                    c.execute('DELETE FROM chunks_fts WHERE chunk_id=?',(r['id'],))
                    c.execute('INSERT INTO chunks_fts(chunk_id,text,document_id) VALUES (?,?,?)',(r['id'],indexed_text(prefix,r['text']),r['document_id']))
            count+=len(batch);last=batch[-1]['id']
        with db() as c:c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('contextual_index_version',VERSION))
    return {'indexed_chunks':count,'version':VERSION,'extra_llm_calls':0,'scope':'Index-only context; original source text, citations and history preserved'}
