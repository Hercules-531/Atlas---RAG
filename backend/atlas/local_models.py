"""Reuse installed Unsloth assets; never download LLM weights implicitly."""
import atexit
import os
from pathlib import Path
import socket
import subprocess
from .config import DATA

def listening(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1',port))==0

def start():
    binary=Path(os.getenv('ATLAS_LLAMA_SERVER',str(Path.home()/'.unsloth/llama.cpp/build/bin/Release/llama-server.exe')))
    if not binary.exists():
        print('llama-server not found. Configure ATLAS_LLAMA_SERVER and local model paths.'); return
    cache=Path.home()/'.cache/huggingface/hub'
    candidates=list(cache.glob('models--unsloth--gemma-4-E4B-it-qat-GGUF/snapshots/*/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf'))
    override=os.getenv('ATLAS_LOCAL_GGUF')
    llm=Path(override) if override else next(iter(candidates),None)
    embed=DATA/'models/embeddinggemma-2-F32.gguf'
    env=os.environ.copy()
    cuda_lib=Path.home()/'.unsloth/studio/unsloth_studio/Lib/site-packages/torch/lib'
    if cuda_lib.exists():
        env['PATH']=str(cuda_lib)+os.pathsep+env.get('PATH','')
    try:
        devices=subprocess.run([str(binary),'--list-devices'],env=env,capture_output=True,text=True,timeout=15)
        gpu='CUDA0' in devices.stdout+devices.stderr
    except subprocess.TimeoutExpired:
        gpu=False
        print('CUDA discovery timed out; using local CPU inference.',flush=True)
    print('Local generation device: '+('CUDA0 (dedicated NVIDIA GPU)' if gpu else 'CPU; CUDA runtime unavailable'),flush=True)
    for port,path,extra in [(8767,embed,['--embeddings','--pooling','mean','--device','none','-ngl','0','--cache-type-k','f32','--cache-type-v','f32']),
                             (8766,llm,['--device','CUDA0','-ngl','99'] if gpu else ['-ngl','0'])]:
        if listening(port) or path is None or not path.exists(): continue
        log=(DATA/f'model-{port}.log').open('w',encoding='utf-8')
        command=[str(binary),'-m',str(path),'--host','127.0.0.1','--port',str(port),'-c','8192','--parallel','1','--no-warmup']+extra
        process=subprocess.Popen(command,stdout=log,stderr=log,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        atexit.register(lambda p=process: p.terminate() if p.poll() is None else None)
        print(f'Local model server {port}: {path.name}',flush=True)
