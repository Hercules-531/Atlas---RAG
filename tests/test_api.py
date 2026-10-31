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
