import base64
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from atlas import llm,store

@pytest.fixture
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(llm,'DATA',tmp_path)
    store.init();monkeypatch.setenv('PRUNE_API_KEY','test-not-real')
    return tmp_path

def test_shield_never_bypassed(isolated):
    with patch.object(httpx.Client,'post',return_value=httpx.Response(429,headers={'X-Prune-Shield-Code':'spend_cap'},request=httpx.Request('POST','https://api.withprune.com/v1/proxy/gemini/generateContent'))) as call:
        with pytest.raises(ValueError,match='Shield'):llm.generate('q','context','privacy','session')
        assert call.call_count==1
        assert call.call_args.args[0].startswith('https://api.withprune.com/')

def test_audit_failure_prevents_dispatch(isolated):
    with patch.object(llm,'write_audit',side_effect=OSError('disk full')),patch.object(httpx.Client,'post') as call:
        with pytest.raises(OSError):llm.generate('q','context','privacy','session')
        call.assert_not_called()

def test_receipt_tampering(isolated):
    private=Ed25519PrivateKey.generate()
    (isolated/'prune-public-key.pem').write_bytes(private.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo))
    receipt={'cache_hit':False,'cost_saved':0}
    receipt['receipt_signature']=base64.b64encode(private.sign(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode())).decode()
    assert llm.verify(receipt)['status']=='verified'
    receipt['cost_saved']=100
    assert llm.verify(receipt)['status']=='unverified'

def test_atomic_budget(isolated):
    def reserve():
        try:store.reserve('race',60,100);return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(lambda _:reserve(),range(4)))==1

def test_local_endpoint_rejects_remote(isolated,monkeypatch):
    monkeypatch.setenv('ATLAS_LOCAL_BASE_URL','https://example.invalid/v1')
    with pytest.raises(ValueError,match='loopback'):llm.generate('q','c','local','s')

def test_post_dispatch_timeout_not_retried(isolated):
    with patch.object(httpx.Client,'post',side_effect=httpx.ReadTimeout('ambiguous outcome')) as call:
        with pytest.raises(httpx.ReadTimeout):llm.generate('q','c','privacy','session')
        assert call.call_count==1
