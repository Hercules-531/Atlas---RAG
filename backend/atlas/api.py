import hashlib
import json
import threading
import time
import uuid
import mimetypes
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import ROOT, DATA, APP_NAME, DEFAULTS, setting, directories
from .store import init, db, rows
from . import ingest, embeddings, privacy, llm
from .calculations import operation,calculate
from . import media
from .multimodal import IMAGES,VIDEOS,AUDIO,SUPPORTED as MEDIA_TYPES

init()
app=FastAPI(title=APP_NAME)
PENDING={}

class UploadBodyLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('path')!='/api/files' or scope.get('method')!='POST':
            return await self.app(scope,receive,send)
        from starlette.responses import JSONResponse
        cap=setting('max_upload_mib')*1048576+65536
        headers=dict(scope['headers'])
        if int(headers.get(b'content-length',b'0'))>cap:
            return await JSONResponse({'detail':'Upload body exceeds configured file limit'},status_code=413)(scope,receive,send)
        total=0
        async def bounded():
            nonlocal total
            message=await receive();total+=len(message.get('body',b''))
            if total>cap:raise HTTPException(413,'Upload exceeds configured streaming body limit')
            return message
        return await self.app(scope,bounded,send)

app.add_middleware(UploadBodyLimit)

@app.middleware('http')
async def local_boundary(request:Request,call_next):
    from urllib.parse import urlparse
    from starlette.responses import JSONResponse
    if request.url.hostname not in ('localhost','127.0.0.1','testserver'):
        return JSONResponse({'detail':'Loopback host required'},status_code=403)
    origin=request.headers.get('origin')
    if origin and origin not in ('http://localhost:8765','http://127.0.0.1:8765','http://localhost:5173','http://127.0.0.1:5173'):
        return JSONResponse({'detail':'Untrusted origin'},status_code=403)
    return await call_next(request)

@app.get('/api/config')
def config():
    return {'name':APP_NAME,'limits':{k:setting(k) for k in DEFAULTS if k!='name'},
        'embedding_ready':(DATA/'models/embeddinggemma-2-F32.gguf').exists() or (DATA/'models/embeddinggemma-2/model.safetensors').exists(),
        'privacy_notice':'Prune sees approved transmitted content. Gemini free-tier content may be used to improve products. Local mode bypasses Prune.',
        'embedding':'EmbeddingGemma 2 · local · 768 dimensions'}

@app.get('/api/files')
def files():
    return rows('SELECT id,name,status,error,progress FROM documents ORDER BY rowid DESC')

@app.get('/api/search')
def search(q:str,kind:Literal['all','image','video','audio']='all'):
    if not q.strip() or len(q)>4000:raise HTTPException(400,'Enter a search query of 1–4000 characters')
    extensions={'image':IMAGES,'video':VIDEOS,'audio':AUDIO,'all':MEDIA_TYPES}[kind]
    docs=[d['id'] for d in files() if d['status']=='ready' and Path(d['name']).suffix.lower() in extensions]
    if not docs:return []
    try:
        found=ingest.retrieve(q,docs);result=[]
        for hit in found:
            source=rows('SELECT path FROM documents WHERE id=?',(hit['document_id'],))[0]
            ext=Path(hit['name']).suffix.lower();media_type='image' if ext in IMAGES else 'video' if ext in VIDEOS else 'audio'
            result.append({'id':hit['id'],'document_id':hit['document_id'],'name':hit['name'],'kind':media_type,
                'location':hit['location'],'excerpt':hit['text'],'images':media.for_location(Path(source['path']),hit['location'],hit['document_id']),
                'url':f'/api/files/{hit["document_id"]}/content'})
        return result
    except Exception as exc:raise HTTPException(400,str(exc)) from exc

class ReindexRequest(BaseModel):
    document_ids:list[str]|None=None

@app.post('/api/reindex')
def reindex_files(request:ReindexRequest):
    # Embedded Chroma must have one owning writer process. CLI maintenance delegates here.
    return ingest.reindex(request.document_ids)

@app.post('/api/retrieval/contextualize')
def contextualize_index():
    from .contextual import rebuild
    return rebuild()

@app.get('/api/files/{docid}/content')
def original_source(docid:str):
    found=rows('SELECT * FROM documents WHERE id=?',(docid,))
    if not found:raise HTTPException(404,'Source file was deleted or is unavailable')
    item=found[0];path=Path(item['path']).resolve()
    if path.parent!=(DATA/'uploads').resolve() or not path.is_file():raise HTTPException(404,'Source file unavailable')
    return FileResponse(path,media_type=mimetypes.guess_type(item['name'])[0] or 'application/octet-stream',filename=item['name'],content_disposition_type='inline')

@app.get('/api/files/{docid}/images')
def source_images(docid:str,location:str=''):
    found=rows('SELECT path FROM documents WHERE id=? AND status="ready"',(docid,))
    if not found:raise HTTPException(404,'Source image unavailable')
    path=Path(found[0]['path']).resolve()
    if path.parent!=(DATA/'uploads').resolve():raise HTTPException(404,'Source image unavailable')
    return media.for_location(path,location,docid)

@app.get('/api/files/{docid}/images/{imageid}')
def source_image(docid:str,imageid:str):
    found=rows('SELECT path FROM documents WHERE id=? AND status="ready"',(docid,))
    if not found:raise HTTPException(404,'Source image unavailable')
    source=Path(found[0]['path']).resolve()
    if source.parent!=(DATA/'uploads').resolve():raise HTTPException(404,'Source image unavailable')
    entry=next((i for i in media.read(source)['images'] if i['id']==imageid),None)
    if not entry:raise HTTPException(404,'Source image unavailable')
    root=media.folder(source).resolve();target=(root/entry['filename']).resolve()
    if target.parent!=root or not target.is_file():raise HTTPException(404,'Source image unavailable')
    return FileResponse(target,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/sources/{chunkid}')
def source_chunk(chunkid:str):
    found=rows('SELECT c.*,d.name,p.text AS parent_text,p.location AS parent_location FROM chunks c JOIN documents d ON c.document_id=d.id LEFT JOIN chunk_parents cp ON cp.chunk_id=c.id LEFT JOIN parents p ON p.id=cp.parent_id WHERE c.id=? AND d.status="ready"',(chunkid,))
    if not found:raise HTTPException(404,'Evidence no longer indexed; original-file links remain available')
    item=found[0]
    return {'document_id':item['document_id'],'name':item['name'],'location':item['parent_location'] or item['location'],'text':item['parent_text'] or item['text']}

@app.post('/api/files')
async def upload(file:UploadFile=File(...)):
    directories(); docid=uuid.uuid4().hex
    name=Path(file.filename or 'upload').name
    ext=Path(name).suffix.lower()
    if ext not in {'.pdf','.docx','.txt','.md','.csv','.xlsx','.json'}|MEDIA_TYPES:
        raise HTTPException(415,'Unsupported format. Upload a document, image, video or audio file.')
    path=DATA/'uploads'/(docid+ext)
    total=0
    try:
        with path.open('wb') as f:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>setting('max_upload_mib')*1048576:
                    raise HTTPException(413,f"File is {total} bytes; maximum {setting('max_upload_mib')} MiB")
                f.write(chunk)
        if not total:
            raise HTTPException(400,'Empty file')
        with db() as c:
            c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',(docid,name,str(path),'queued'))
        threading.Thread(target=ingest.ingest,args=(docid,),daemon=True).start()
        return {'id':docid,'status':'queued'}
    except BaseException:
        path.unlink(missing_ok=True); raise
    finally:
        await file.close()

@app.post('/api/files/{docid}/cancel')
def cancel(docid:str):
    ingest.CANCELLED.add(docid)
    ingest.update(docid,'cancelled','Cancelled by user')
    return {'status':'cancellation requested'}

@app.post('/api/files/{docid}/retry')
def retry_file(docid:str):
    found=rows('SELECT status FROM documents WHERE id=?',(docid,))
    if not found:raise HTTPException(404,'File not found')
    if found[0]['status'] not in ('error','cancelled'):raise HTTPException(409,'Only failed or cancelled files can be retried')
    ingest.CANCELLED.discard(docid);ingest.update(docid,'queued')
    threading.Thread(target=ingest.ingest,args=(docid,),daemon=True).start()
    return {'status':'queued'}

@app.delete('/api/files/{docid}')
def delete_file(docid:str):
    with llm.DATA_LOCK:
        return _delete_file(docid)

def _delete_file(docid):
    ingest.CANCELLED.add(docid)
    with ingest.LOCK:
        found=rows('SELECT path FROM documents WHERE id=?',(docid,))
        with db() as c:
            c.execute('DELETE FROM documents WHERE id=?',(docid,)); c.execute('DELETE FROM chunks WHERE document_id=?',(docid,))
            c.execute('DELETE FROM parents WHERE document_id=?',(docid,))
            # History and audit may contain information derived from this document.
            c.execute('DELETE FROM history'); c.execute('DELETE FROM budgets')
        for item in found:
            path=Path(item['path']).resolve()
            if path.parent == (DATA/'uploads').resolve():
                media.clear(path);path.unlink(missing_ok=True)
        embeddings.collection().delete(where={'document_id':docid})
        for path in (DATA/'audit').glob('*.json'): path.unlink()
        PENDING.clear()
    return {'deleted':docid}

@app.delete('/api/data')
def delete_all():
    for file in files(): ingest.CANCELLED.add(file['id'])
    for file in files(): delete_file(file['id'])
    with db() as c:
        c.execute('DELETE FROM history'); c.execute('DELETE FROM budgets');c.execute('DELETE FROM settings')
    for col in embeddings.client().list_collections():
        if col.name.startswith('atlas-'):embeddings.client().delete_collection(col.name)
    for path in (DATA/'audit').glob('*'):
        if path.is_file(): path.unlink()
    for path in (ROOT/'reports').glob('*'):
        if path.is_file() and path.suffix in ('.json','.md'): path.unlink()
    return {'deleted':'all application records, uploads, vectors, audits and reports'}

class Ask(BaseModel):
    question:str=Field(min_length=1,max_length=4000)
    mode:Literal['local','privacy']='privacy'
    session:str=Field(min_length=1,max_length=100)
    document_ids:list[str]=Field(default_factory=list,max_length=100)

def snapshot():
    return hashlib.sha256(json.dumps(rows('SELECT id,status FROM documents ORDER BY id'),sort_keys=True).encode()+(ROOT/'config/policy.yaml').read_bytes()).hexdigest()

def execute(query,plan):
    with llm.DATA_LOCK:
        return _execute(query,plan)

def _execute(query,plan):
    for citation in plan['citations']:
        if not rows('SELECT id FROM documents WHERE id=? AND status="ready"',(citation['document_id'],)):
            raise ValueError('Evidence changed or was deleted. Ask again.')
    if not plan['context']:
        return {'status':'answered','answer':'I cannot answer from the selected evidence. Try a more specific question or select another document.','citations':[],'receipt':{'external_requests':0,'prune_metadata':{},'signature':{'status':'no generation'}}}
    generated=llm.generate(plan['question'],plan['context'],query.mode,query.session)
    for citation in plan['citations']:
        source=rows('SELECT path FROM documents WHERE id=?',(citation['document_id'],))
        citation['images']=media.for_location(Path(source[0]['path']),citation['location'],citation['document_id']) if source else []
    answer=privacy.restore(generated['answer'],plan['mapping'])
    import re
    groups=re.findall(r'\[((?:S?\d+)(?:\s*,\s*S?\d+)*)\]',answer)
    references={'S'+n for group in groups if ',' not in group or 'S' in group for n in re.findall(r'\d+',group)}
    unknown=references-{c['id'] for c in plan['citations']}
    warnings=[]
    if unknown: warnings.append('Unverified citations: '+', '.join(unknown))
    if '[[ATLAS_' in answer: warnings.append('An unknown placeholder was not restored')
    scope=query.document_ids or [d['id'] for d in files() if d['status']=='ready']
    corpus=rows('SELECT text FROM chunks WHERE document_id IN ('+','.join('?' for _ in scope)+')',scope) if scope else []
    full='\n'.join(r['text'] for r in corpus)
    sent_tokens=privacy.estimate(generated['payload']); full_tokens=privacy.estimate(full)
    audit_records=[json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'audit').glob('*.json')]
    external=sum(bool(r['external']) for r in audit_records if r['session']==query.session)
    receipt={'audit_id':generated['audit_id'],'sent':json.loads(generated['payload']),
        'source_images_sent_to_model':False,'raw_media_sent_to_cloud':False,
        'source_images_scope':'No raw media attached to this answer request. Uploaded media can have local Gemma visual descriptions or local Whisper speech transcripts; these can contain errors.',
        'withheld':[{k:v for k,v in item.items() if k!='value'} for item in plan['withheld']],
        'withheld_local':plan['withheld'],'not_retrieved_chunks':max(0,len(corpus)-len(plan['citations'])),
        'tokens_sent_estimate':sent_tokens,'full_document_tokens_estimate':full_tokens,
        'estimate_method':'UTF-8 bytes / 3, rounded up; not Gemini tokenizer counts',
        'withheld_percent_estimate':round(max(0,1-privacy.estimate(plan['context'])/max(1,full_tokens))*100,2),
        'input_list_price_saving_estimate_usd':max(0,full_tokens-sent_tokens)*.30/1e6,
        'billing':'Free tier configured by user; actual invoice not verified',
        'usage':generated['usage'],'prune_metadata':generated['prune_metadata'],'signature':generated['signature'],
        'elapsed_seconds':generated['elapsed_seconds'],'external_requests':external,
        'scope':'Application-owned HTTP requests during this session; not machine-wide monitoring'}
    result={'status':'answered','answer':answer,'citations':plan['citations'],'receipt':receipt,'warnings':warnings}
    identifier=uuid.uuid4().hex
    with db() as c:
        c.execute('INSERT INTO history VALUES (?,?,?,?,?)',(identifier,time.time(),query.question,query.mode,json.dumps(result)))
    result['id']=identifier
    return result

@app.post('/api/ask')
def ask(query:Ask):
    try:
        chunks=ingest.retrieve(query.question,query.document_ids)
        calculation=None
        if operation(query.question):
            if not query.document_ids:
                raise ValueError('Select the document(s) to calculate across, so duplicate files are not counted twice.')
            marks=','.join('?' for _ in query.document_ids)
            chunks=rows('SELECT chunks.*,documents.name FROM chunks JOIN documents ON chunks.document_id=documents.id WHERE documents.status="ready" AND chunks.document_id IN ('+marks+') LIMIT 10001',query.document_ids)
            if len(chunks)>10000:raise ValueError('Calculation scope exceeds 10,000 chunks. Select fewer documents.')
            calculation=calculate(query.question,chunks)
        plan=privacy.minimize(query.question,chunks)
        if calculation:
            # Compute with originals locally; cloud only receives a reversible result token.
            token='[[ATLAS_'+uuid.uuid4().hex+']]'
            plan['mapping'][token]=calculation['value']
            plan['context']='[S1] Locally verified '+calculation['operation']+' of '+calculation['field']+' across '+str(calculation['rows'])+' records: '+token
            plan['calculation']=calculation
        if query.mode=='privacy' and plan['needed']:
            identifier=uuid.uuid4().hex
            PENDING[identifier]={'query':query,'plan':plan,'expires':time.time()+600,'snapshot':snapshot()}
            return {'status':'consent_required','consent_id':identifier,'categories':plan['needed'],
                'message':'I need these sensitive fields to answer. Allow tokenized use? Originals stay local.',
                'preview':{'question':plan['question'],'context':plan['context']}}
        return execute(query,plan)
    except Exception as exc:
        raise HTTPException(400,str(exc)) from exc

class Consent(BaseModel):
    allow:bool

@app.post('/api/consent/{identifier}')
def consent(identifier:str,decision:Consent):
    pending=PENDING.pop(identifier,None)
    if not pending or pending['expires']<time.time() or pending['snapshot']!=snapshot():
        raise HTTPException(409,'Consent expired or documents/policy changed. Ask again.')
    if not decision.allow: return {'status':'blocked','answer':'No information was sent.'}
    try: return execute(pending['query'],pending['plan'])
    except Exception as exc: raise HTTPException(400,str(exc)) from exc

@app.get('/api/history')
def history(q:str=''):
    return [{**r,'result':json.loads(r['result'])} for r in rows('SELECT * FROM history WHERE question LIKE ? ORDER BY created DESC',('%'+q+'%',))]

@app.delete('/api/history')
def clear_history():
    with db() as c: c.execute('DELETE FROM history')
    return {'deleted':'history'}

@app.delete('/api/history/{identifier}')
def remove_history(identifier:str):
    with db() as c: c.execute('DELETE FROM history WHERE id=?',(identifier,))
    return {'deleted':identifier}

@app.get('/api/evaluation')
def evaluation():
    path=ROOT/'reports/evaluation.json'
    return json.loads(path.read_text()) if path.exists() else {'status':'not run','message':'Run uv run atlas eval; no results fabricated.'}

@app.post('/api/demo')
def demo():
    from .demo import build
    build()
    added=[]
    for path in (ROOT/'demo/sources').glob('*'):
        if rows('SELECT id FROM documents WHERE name=?',(path.name,)): continue
        import shutil
        docid=uuid.uuid4().hex; target=DATA/'uploads'/(docid+path.suffix)
        shutil.copyfile(path,target)
        with db() as c: c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',(docid,path.name,str(target),'queued'))
        threading.Thread(target=ingest.ingest,args=(docid,),daemon=True).start(); added.append(docid)
    return {'queued':added}

dist=ROOT/'frontend/dist'
if dist.exists():
    app.mount('/',StaticFiles(directory=dist,html=True),name='ui')
