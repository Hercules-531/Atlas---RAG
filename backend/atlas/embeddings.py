import hashlib
import os
from functools import lru_cache
import numpy as np
from .config import DATA

def validate(vectors):
    a = np.asarray(vectors, dtype=np.float32)
    if a.ndim != 2 or a.shape[1] != 768 or not np.isfinite(a).all():
        raise ValueError('Embeddings must have 768 finite values')
    norm = np.linalg.norm(a, axis=1, keepdims=True)
    if (norm == 0).any():
        raise ValueError('Zero embedding')
    return (a / norm).tolist()

@lru_cache
def model():
    import torch
    from sentence_transformers import SentenceTransformer
    path = DATA / 'models/embeddinggemma-2'
    if not (path / 'config.json').exists():
        raise RuntimeError('EmbeddingGemma 2 is not installed. Run: uv run atlas setup-models')
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
    return SentenceTransformer(str(path), local_files_only=True,
        config_kwargs={'vision_config': None, 'audio_config': None},
        model_kwargs={'torch_dtype': dtype})

def embed(texts, query=False):
    inputs = [('task: question answering | query: ' if query else 'title: none | text: ') + t for t in texts]
    if (DATA/'models/embeddinggemma-2-F32.gguf').exists():
        import httpx
        with httpx.Client(timeout=120,trust_env=False) as c:
            response=c.post('http://127.0.0.1:8767/v1/embeddings',json={'model':'embeddinggemma-2','input':inputs})
            if response.is_error:
                try:
                    error=response.json().get('error',{})
                    message=error.get('message',str(error)) if isinstance(error,dict) else str(error)
                except (ValueError,TypeError):message=response.text[:500]
                raise ValueError('Local embedding failed: '+message)
            response.raise_for_status()
            return validate([r['embedding'] for r in sorted(response.json()['data'],key=lambda r:r['index'])])
    return validate(model().encode(inputs, batch_size=8, normalize_embeddings=True, show_progress_bar=False))

@lru_cache
def fingerprint():
    gguf=DATA/'models/embeddinggemma-2-F32.gguf'
    if gguf.exists():
        digest=hashlib.sha256()
        with gguf.open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
        return hashlib.sha256(('embeddinggemma-2|F32|qa-v1|'+digest.hexdigest()).encode()).hexdigest()[:20]
    manifest = DATA / 'models/revision.txt'
    revision = manifest.read_text() if manifest.exists() else 'not-installed'
    return hashlib.sha256(('google/embeddinggemma-2|qa-v1|768|'+revision).encode()).hexdigest()[:20]

@lru_cache
def client():
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    from chromadb import PersistentClient
    from chromadb.config import Settings
    return PersistentClient(path=str(DATA / 'chroma'), settings=Settings(anonymized_telemetry=False))

def collection():
    from .store import rows,db
    current=fingerprint()
    old=rows('SELECT value FROM settings WHERE key="embedding_fingerprint"')
    if old and old[0]['value']!=current:
        raise ValueError('Embedding model/index fingerprint changed. Delete data and reindex with one model.')
    if not old:
        with db() as c:c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',('embedding_fingerprint',current))
    return client().get_or_create_collection('atlas-' + fingerprint(), embedding_function=None,
        metadata={'hnsw:space': 'cosine', 'fingerprint': fingerprint()})

def setup():
    from huggingface_hub import HfApi, snapshot_download
    repo = os.getenv('ATLAS_EMBEDDING_MODEL', 'google/embeddinggemma-2')
    revision = HfApi().model_info(repo).sha
    path = DATA / 'models/embeddinggemma-2'
    snapshot_download(repo, revision=revision, local_dir=path,
        ignore_patterns=['*.gguf', '*.onnx', '*.tflite', '*.h5', 'onnx/*', 'openvino/*'])
    (DATA / 'models/revision.txt').write_text(revision)
    model.cache_clear()
    vector = embed(['Model validation'], query=True)[0]
    return {'revision': revision, 'dimensions': len(vector), 'finite': bool(np.isfinite(vector).all())}
