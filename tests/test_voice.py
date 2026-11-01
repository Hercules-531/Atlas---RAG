import io
import json
import threading
import numpy as np
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from atlas import voice,multimodal,privacy


@pytest.fixture
def local_voice(tmp_path,monkeypatch):
    monkeypatch.setattr(voice,'DATA',tmp_path)
    monkeypatch.setattr(multimodal,'DATA',tmp_path)
    monkeypatch.delenv('ATLAS_SPEECH_MODEL_DIR',raising=False)
    monkeypatch.setattr(voice,'LOCK',threading.Lock())
    model=tmp_path/'models/whisper-base';model.mkdir(parents=True)
    for name in ('model.bin','config.json','tokenizer.json','vocabulary.txt'):(model/name).touch()
    return tmp_path


def test_supported_native_scripts_preserve_combining_marks():
    for word in ['दूरबीन','தமிழ்','తెలుగు','മലയാളം','ગુજરાતી','ਪੰਜਾਬੀ','বাংলা','نیلا']:
        assert word in privacy.terms(word)
    assert privacy.terms('DreamDiffusion customer_id')=={'dream','diffusion','customer','id'}


def test_supported_language_codes_match_installed_whisper():
    from faster_whisper.tokenizer import _LANGUAGE_CODES
    assert set(voice.LANGUAGES)-{'auto'}<=set(_LANGUAGE_CODES)


def test_language_hint_preserves_text_instead_of_translating(monkeypatch):
    monkeypatch.setattr(voice,'decode_recording',lambda _:np.zeros(64000,dtype=np.float32))
    model=SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(text=' नीला फूल ')],SimpleNamespace(language='hi')))
    with patch.object(model,'transcribe',wraps=model.transcribe) as call:
        monkeypatch.setattr(multimodal,'speech_model',lambda:model)
        result=voice.transcribe('speech.webm','hi')
        assert result['text']=='नीला फूल' and result['local'] is True
        assert call.call_args.kwargs['language']=='hi' and call.call_args.kwargs['task']=='transcribe'


def test_auto_language_and_empty_audio(monkeypatch):
    monkeypatch.setattr(voice,'decode_recording',lambda _:np.zeros(16000,dtype=np.float32))
    with patch.object(multimodal,'speech_model') as model:
        model.return_value.transcribe.return_value=([],SimpleNamespace(language='en'))
        with pytest.raises(ValueError,match='No intelligible'):voice.transcribe('silence.wav','auto')
        assert model.return_value.transcribe.call_args.kwargs['language'] is None


def test_duration_and_decode_fail_before_model_load(tmp_path):
    import wave
    long=tmp_path/'long.wav'
    with wave.open(str(long),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*16000*62)
    bad=tmp_path/'bad.webm';bad.write_bytes(b'invalid')
    with patch.object(multimodal,'speech_model') as model:
        with pytest.raises(ValueError,match='at most'):voice.transcribe(long,'hi')
        with pytest.raises(ValueError,match='decoded'):voice.transcribe(bad,'hi')
        model.assert_not_called()


@pytest.mark.parametrize('filename,language,payload',[
    ('recording.exe','en',b'a'),('recording.webm','invalid',b'a'),('recording.webm','en',b''),
])
def test_bad_requests_leave_no_recording(local_voice,filename,language,payload):
    with pytest.raises(ValueError):voice.recognize(io.BytesIO(payload),filename,language)
    assert not list(local_voice.rglob('audio*')) and not voice.LOCK.locked()


def test_size_limit_releases_lock_and_deletes_audio(local_voice,monkeypatch):
    original=voice.setting;monkeypatch.setattr(voice,'setting',lambda k:1 if k=='max_dictation_mib' else original(k))
    with pytest.raises(ValueError,match='upload limit'):
        voice.recognize(io.BytesIO(b'a'*(1048576+1)),'audio.webm')
    assert not list((local_voice/'dictation').iterdir()) and not voice.LOCK.locked()


def test_concurrent_voice_requests_are_bounded(local_voice):
    voice.LOCK.acquire()
    try:
        with pytest.raises(voice.VoiceBusy):voice.recognize(io.BytesIO(b'a'),'audio.webm')
    finally:voice.LOCK.release()


def test_missing_model_fails_without_download(tmp_path,monkeypatch):
    monkeypatch.setattr(voice,'DATA',tmp_path)
    monkeypatch.setattr(multimodal,'DATA',tmp_path)
    monkeypatch.delenv('ATLAS_SPEECH_MODEL_DIR',raising=False)
    with pytest.raises(ValueError,match='setup-media'):voice.recognize(io.BytesIO(b'a'),'audio.webm')


def test_missing_tokenizer_cannot_trigger_download(local_voice):
    (local_voice/'models/whisper-base/tokenizer.json').unlink()
    multimodal.speech_model.cache_clear()
    with patch('faster_whisper.WhisperModel') as model:
        with pytest.raises(ValueError,match='tokenizer'):multimodal.speech_model()
        model.assert_not_called()


def test_custom_local_model_is_still_cpu_and_local_only(local_voice,monkeypatch):
    monkeypatch.setenv('ATLAS_SPEECH_MODEL_DIR',str(local_voice/'models/whisper-base'))
    multimodal.speech_model.cache_clear()
    try:
        with patch('faster_whisper.WhisperModel') as model:
            multimodal.speech_model()
            assert model.call_args.kwargs=={'device':'cpu','compute_type':'int8','local_files_only':True}
    finally:multimodal.speech_model.cache_clear()


def test_worker_deadline_terminates_and_cleans_up(local_voice,monkeypatch):
    class Process:
        pid=1
        def __init__(self,**kw):self.alive=True;self.terminated=False
        def start(self):pass
        def join(self,*args):pass
        def is_alive(self):return self.alive
        def terminate(self):self.alive=False;self.terminated=True
        def close(self):pass
    process=Process();monkeypatch.setattr(voice.mp,'get_context',lambda _:SimpleNamespace(Process=lambda **k:process))
    with pytest.raises(ValueError,match='timed out'):voice.recognize(io.BytesIO(b'a'),'audio.webm')
    assert process.terminated and not list((local_voice/'dictation').iterdir()) and not voice.LOCK.locked()


def test_worker_success_is_ephemeral(local_voice,monkeypatch):
    class Process:
        pid=1
        def __init__(self,**kwargs):self.args=kwargs['args']
        def start(self):
            from pathlib import Path
            Path(self.args[2]).write_text(json.dumps({'result':{'text':'नीला फूल','language':'hi','local':True}}),encoding='utf-8')
        def join(self,*a):pass
        def is_alive(self):return False
        def close(self):pass
    monkeypatch.setattr(voice.mp,'get_context',lambda _:SimpleNamespace(Process=Process))
    result=voice.recognize(io.BytesIO(b'a'),'audio.webm','hi')
    assert result['text']=='नीला फूल' and not list((local_voice/'dictation').iterdir())
