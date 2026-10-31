import argparse
import json
import os
import subprocess
import sys
from .config import ROOT, directories

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['dev','serve','setup-models','demo','eval','reindex','index-images'])
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--synthetic-full-context',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(); directories()
    if args.command=='setup-models':
        from .config import DATA
        from pathlib import Path
        converted=DATA/'models/embeddinggemma-2-F32.gguf'
        sources=list((Path.home()/'.cache/huggingface/hub').glob('models--unsloth--embeddinggemma-2-GGUF/snapshots/*/embeddinggemma-2-F16.gguf'))
        quantize=Path.home()/'.unsloth/llama.cpp/build/bin/Release/llama-quantize.exe'
        if not converted.exists() and sources and quantize.exists():
            converted.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run([str(quantize),'--pure',str(sources[0]),str(converted),'F32','8'],check=True)
        if converted.exists():
            print('Reusing local EmbeddingGemma 2 FP32 conversion; no weight download.')
        else:
            from .embeddings import setup
            print(json.dumps(setup()))
        import importlib.util
        if not importlib.util.find_spec('en_core_web_sm'):
            result=subprocess.run(['uv','pip','install','--python',sys.executable,'https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl'])
            if result.returncode:
                import urllib.request
                wheel=DATA/'models/en_core_web_sm-3.7.1-py3-none-any.whl'
                wheel.parent.mkdir(parents=True,exist_ok=True)
                with urllib.request.urlopen('https://huggingface.co/spacy/en_core_web_sm/resolve/main/en_core_web_sm-any-py3-none-any.whl',timeout=60) as response:
                    wheel.write_bytes(response.read())
                print('Compatible NER download failed; using official 3.7.1 fallback with a spaCy compatibility warning.')
                subprocess.run(['uv','pip','install','--python',sys.executable,'--no-deps',str(wheel)],check=True)
    elif args.command=='index-images':
        from .media import index
        from .store import init,rows
        init()
        for document in rows('SELECT id,path FROM documents WHERE status="ready"'):
            result=index(document['path']);print(document['id'],len(result['images']),'local previews',flush=True)
    elif args.command=='reindex':
        from .ingest import reindex
        from .store import init
        init();print(json.dumps(reindex(),indent=2))
    elif args.command=='demo':
        from .demo import build
        build(); print('Synthetic demo datasets generated')
    elif args.command=='eval':
        from .evaluation import run
        run(args.live,args.synthetic_full_context,args.resume)
    elif args.command=='serve':
        from .local_models import start
        start()
        import uvicorn
        uvicorn.run('atlas.api:app',host='127.0.0.1',port=8765)
    else:
        frontend=ROOT/'frontend'
        npm='npm.cmd' if os.name=='nt' else 'npm'
        if not (frontend/'node_modules').exists(): subprocess.run([npm,'ci'],cwd=frontend,check=True)
        subprocess.run([npm,'run','build'],cwd=frontend,check=True)
        import uvicorn
        from .local_models import start
        start()
        print('Open http://127.0.0.1:8765')
        uvicorn.run('atlas.api:app',host='127.0.0.1',port=8765)
