from pathlib import Path
from unittest.mock import MagicMock
from atlas import local_models

def test_cuda_dependency_path_and_explicit_gpu_offload(tmp_path,monkeypatch):
    binary=tmp_path/'llama-server.exe';binary.touch()
    cuda=tmp_path/'.unsloth/studio/unsloth_studio/Lib/site-packages/torch/lib';cuda.mkdir(parents=True)
    data=tmp_path/'data';(data/'models').mkdir(parents=True);(data/'models/embeddinggemma-2-F32.gguf').touch()
    llm=tmp_path/'local.gguf';llm.touch()
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:tmp_path))
    monkeypatch.setenv('ATLAS_LLAMA_SERVER',str(binary));monkeypatch.setenv('ATLAS_LOCAL_GGUF',str(llm))
    monkeypatch.setattr(local_models,'DATA',data);monkeypatch.setattr(local_models,'listening',lambda _:False)
    monkeypatch.setattr(local_models.subprocess,'run',lambda *a,**kw:MagicMock(stdout='CUDA0: NVIDIA GPU',stderr=''))
    calls=[]
    def spawn(command,**kwargs):calls.append((command,kwargs));return MagicMock(poll=lambda:0)
    monkeypatch.setattr(local_models.subprocess,'Popen',spawn)
    local_models.start()
    assert len(calls)==2
    assert calls[1][0][-4:]==['--device','CUDA0','-ngl','99']
    assert calls[0][0][calls[0][0].index('--device')+1]=='none'
    assert calls[0][0][calls[0][0].index('--batch-size')+1]=='8192'
    assert calls[0][0][calls[0][0].index('--ubatch-size')+1]=='8192'
    assert calls[1][1]['env']['PATH'].startswith(str(cuda))
