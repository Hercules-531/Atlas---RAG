import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from atlas import store
from atlas import api as module

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(module,'DATA',tmp_path)
    (tmp_path/'uploads').mkdir();(tmp_path/'audit').mkdir();store.init()
    with TestClient(module.app) as client:yield client

def test_origin_rejection(client):
    assert client.post('/api/demo',headers={'Origin':'https://evil.example'}).status_code==403

def test_upload_boundary(client,monkeypatch):
    monkeypatch.setenv('ATLAS_MAX_UPLOAD_MIB','1')
    with patch.object(module.ingest,'ingest'):
        assert client.post('/api/files',files={'file':('file.txt',b'x'*1048576)}).status_code==200
        assert client.post('/api/files',files={'file':('large.txt',b'x'*1048577)}).status_code==413

def test_empty_and_unsupported(client):
    assert client.post('/api/files',files={'file':('a.txt',b'')}).status_code==400
    assert client.post('/api/files',files={'file':('a.exe',b'text')}).status_code==415

def test_full_default_100mib_stream(client):
    boundary='atlas-upload-test'
    def body():
        yield f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="large.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()
        for _ in range(100):yield b'x'*1048576
        yield f'\r\n--{boundary}--\r\n'.encode()
    with patch.object(module.ingest,'ingest'):
        response=client.post('/api/files',content=body(),headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    assert response.status_code==200,response.text
    saved=store.rows('SELECT path FROM documents WHERE id=?',(response.json()['id'],))[0]['path']
    from pathlib import Path
    assert Path(saved).stat().st_size==100*1048576

def test_consent_invalidation(client):
    identifier='expired'
    module.PENDING[identifier]={'expires':0,'snapshot':'old'}
    assert client.post('/api/consent/'+identifier,json={'allow':True}).status_code==409

def test_decline_no_dispatch(client):
    import time
    module.PENDING['deny']={'expires':time.time()+60,'snapshot':module.snapshot()}
    with patch.object(module.llm,'generate') as generate:
        assert client.post('/api/consent/deny',json={'allow':False}).json()['status']=='blocked'
        generate.assert_not_called()

def test_deleted_evidence_prevents_generation(client):
    query=module.Ask(question='q',session='s')
    plan={'citations':[{'document_id':'deleted'}]}
    with patch.object(module.llm,'generate') as generate:
        with pytest.raises(ValueError,match='deleted'):module.execute(query,plan)
        generate.assert_not_called()

def test_cancel_updates_status(client):
    with store.db() as c:c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('cancel-me','file.txt','unused','queued'))
    assert client.post('/api/files/cancel-me/cancel').status_code==200
    assert store.rows('SELECT status FROM documents WHERE id="cancel-me"')[0]['status']=='cancelled'

def test_original_source_is_local_and_inline(client,tmp_path):
    path=tmp_path/'uploads/source.pdf';path.write_bytes(b'%PDF-synthetic-test')
    with store.db() as c:c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('source','source.pdf',str(path),'ready'))
    response=client.get('/api/files/source/content')
    assert response.status_code==200 and 'inline' in response.headers['content-disposition']
    assert response.content==b'%PDF-synthetic-test'

def test_source_cannot_escape_upload_directory(client,tmp_path):
    path=tmp_path/'outside.txt';path.write_text('not an upload')
    with store.db() as c:c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('outside','outside.txt',str(path),'ready'))
    assert client.get('/api/files/outside/content').status_code==404

def test_source_endpoint_returns_parent_evidence(client):
    with store.db() as c:
        c.execute('INSERT INTO documents(id,name,status) VALUES (?,?,?)',('pdoc','policy.txt','ready'))
        c.execute('INSERT INTO parents VALUES (?,?,?,?)',('parent','pdoc','Full parent evidence.','line 1 – line 3'))
        c.execute('INSERT INTO chunks VALUES (?,?,?,?)',('child','pdoc','child text','line 2'))
        c.execute('INSERT INTO chunk_parents VALUES (?,?,?,?)',('child','parent',0,10))
    assert client.get('/api/sources/child').json()['text']=='Full parent evidence.'

def test_source_preview_serving_and_missing_source(client,tmp_path):
    import json
    from PIL import Image
    from atlas import media
    path=tmp_path/'uploads/image-source.pdf';path.write_bytes(b'fake PDF original')
    folder=media.folder(path);folder.mkdir(parents=True)
    Image.new('RGB',(10,10),'white').save(folder/'safe.jpg')
    (folder/'manifest.json').write_text(json.dumps({'images':[{'id':'safe','filename':'safe.jpg','location':'page 1','kind':'embedded','width':10,'height':10}]}))
    with store.db() as c:c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('image-doc','source.pdf',str(path),'ready'))
    listed=client.get('/api/files/image-doc/images?location=page%201').json();assert listed[0]['url'].endswith('/safe')
    response=client.get('/api/files/image-doc/images/safe');assert response.status_code==200 and response.headers['content-type']=='image/jpeg'
    assert response.headers['cache-control']=='private, no-store'
    with store.db() as c:c.execute('DELETE FROM documents WHERE id="image-doc"')
    assert client.get('/api/files/image-doc/images/safe').status_code==404

def test_source_preview_path_escape_is_blocked(client,tmp_path):
    import json
    from atlas import media
    path=tmp_path/'uploads/escape.pdf';path.touch();folder=media.folder(path);folder.mkdir(parents=True)
    (folder/'manifest.json').write_text(json.dumps({'images':[{'id':'escape','filename':'../../outside.jpg','location':'page 1'}]}))
    with store.db() as c:c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('escape-doc','source.pdf',str(path),'ready'))
    assert client.get('/api/files/escape-doc/images/escape').status_code==404

def test_deleting_file_clears_local_image_assets(client,tmp_path):
    import json
    from atlas import media
    path=tmp_path/'uploads/delete-images.pdf';path.touch();folder=media.folder(path);folder.mkdir(parents=True)
    (folder/'manifest.json').write_text(json.dumps({'images':[]}));(folder/'preview.jpg').write_bytes(b'preview')
    with store.db() as c:c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('delete-images','source.pdf',str(path),'ready'))
    with patch.object(module.embeddings,'collection'):
        assert client.delete('/api/files/delete-images').status_code==200
    assert not path.exists() and not folder.exists()

def test_image_metadata_is_added_after_text_generation(client,tmp_path):
    import json
    from atlas import media
    path=tmp_path/'uploads/private-preview.pdf';path.touch();folder=media.folder(path);folder.mkdir(parents=True)
    (folder/'manifest.json').write_text(json.dumps({'images':[{'id':'image','filename':'image.jpg','location':'page 1','kind':'embedded','width':10,'height':10}]}))
    with store.db() as c:
        c.execute('INSERT INTO documents(id,name,path,status) VALUES (?,?,?,?)',('preview','preview.pdf',str(path),'ready'))
        c.execute('INSERT INTO chunks VALUES (?,?,?,?)',('preview-chunk','preview','The total is 18.','page 1'))
    query=module.Ask(question='What is the total?',mode='privacy',session='test-images',document_ids=['preview'])
    plan={'question':'What is the total?','context':'[S1] The total is 18.','mapping':{},'withheld':[],
        'citations':[{'id':'S1','document_id':'preview','name':'preview.pdf','location':'page 1','text':'The total is 18.'}]}
    generated={'answer':'18 [S1]','audit_id':'mock','payload':json.dumps({'messages':[{'content':plan['context']}]}),'usage':{},'prune_metadata':{},'signature':{'status':'mock'},'elapsed_seconds':0}
    with patch.object(module.llm,'generate',return_value=generated) as call:
        result=module.execute(query,plan)
        assert '/images/' not in call.call_args.args[1]
        assert result['receipt']['source_images_sent_to_model'] is False
        assert len(result['citations'][0]['images'])==1
        assert '/images/' not in json.dumps(result['receipt']['sent'])
