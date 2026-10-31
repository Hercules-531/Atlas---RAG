import httpx
import pytest
from unittest.mock import patch,MagicMock
from atlas import embeddings

def test_embedding_backend_reason_is_preserved(tmp_path,monkeypatch):
    monkeypatch.setattr(embeddings,'DATA',tmp_path)
    (tmp_path/'models').mkdir();(tmp_path/'models/embeddinggemma-2-F32.gguf').touch()
    response=httpx.Response(500,json={'error':{'message':'input (649 tokens) is too large; physical batch size: 512'}})
    client=MagicMock();client.__enter__.return_value.post.return_value=response
    with patch.object(httpx,'Client',return_value=client):
        with pytest.raises(ValueError,match=r'Local embedding failed: input \(649 tokens\)'):
            embeddings.embed(['synthetic scientific passage'])
