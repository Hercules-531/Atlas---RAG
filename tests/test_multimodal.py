import base64
import json
from unittest.mock import patch
import pytest
from PIL import Image
from atlas import multimodal,llm,store

def test_timestamp_is_stable():
    assert multimodal.stamp(65.25)=='00:01:05.250'

def test_probe_rejects_excess_duration(tmp_path,monkeypatch):
    monkeypatch.setattr(multimodal,'tools',lambda name:name)
    from types import SimpleNamespace
    monkeypatch.setattr(multimodal.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps({'format':{'duration':'1000'},'streams':[{'codec_type':'audio'}]})))
    with pytest.raises(ValueError,match='exceeds'):multimodal.probe(tmp_path/'long.wav')

def test_cloud_raw_image_dispatch_is_blocked():
    with pytest.raises(ValueError,match='local-only'):
        llm.generate('q','','privacy','s',images=['data:image/jpeg;base64,AAAA'])

def test_local_caption_rejects_remote_image_url():
    with pytest.raises(ValueError,match='inline JPEG'):
        llm.generate('q','','local','s',images=['https://example.invalid/image.jpg'])

def test_caption_uses_local_model_and_bounded_inline_image(tmp_path,monkeypatch):
    path=tmp_path/'picture.png';Image.new('RGB',(100,100),'red').save(path)
    with patch.object(multimodal,'generate',return_value={'answer':'A red square'}) as generate:
        assert multimodal.caption(path,'ingest')=='A red square'
        assert generate.call_args.args[2]=='local'
        assert generate.call_args.kwargs['images'][0].startswith('data:image/jpeg;base64,')

def test_media_parent_boundaries_do_not_join_timestamps():
    from atlas.chunking import parents
    assert len(list(parents([('one','time 00:00:01.000'),('two','time 00:00:02.000')])))==2

def test_real_audio_decoder_is_compatible(tmp_path):
    import wave
    import numpy as np
    from faster_whisper.audio import decode_audio
    path=tmp_path/'tone.wav'
    samples=(np.sin(np.arange(1600)*2*np.pi*440/16000)*12000).astype('<i2')
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(samples.tobytes())
    decoded=decode_audio(str(path))
    assert decoded.dtype==np.float32 and len(decoded)>0

def test_transcript_timestamps_are_bounded(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(multimodal,'probe',lambda _: (8,{'audio'}))
    model=SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(start=6,end=14,text=' amber ')],None))
    monkeypatch.setattr(multimodal,'speech_model',lambda:model)
    result=list(multimodal.transcribe('audio.wav'))
    assert result[0][1]=='time 00:00:06.000 – 00:00:08.000'
