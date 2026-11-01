"""Bounded microphone transcription with cached Whisper weights, CPU only."""
import json
import multiprocessing as mp
import os
import tempfile
import threading
import time
from pathlib import Path
from .config import DATA,setting

LANGUAGES={
    'auto':'Detect language','en':'English','hi':'हिन्दी · Hindi','bn':'বাংলা · Bengali',
    'ta':'தமிழ் · Tamil','te':'తెలుగు · Telugu','mr':'मराठी · Marathi',
    'gu':'ગુજરાતી · Gujarati','kn':'ಕನ್ನಡ · Kannada','ml':'മലയാളം · Malayalam',
    'pa':'ਪੰਜਾਬੀ · Punjabi','ur':'اردو · Urdu','as':'অসমীয়া · Assamese',
    'ne':'नेपाली · Nepali','sa':'संस्कृतम् · Sanskrit','sd':'سنڌي · Sindhi',
}
LOCK=threading.Lock()
EXTENSIONS={'.webm','.ogg','.m4a','.mp4','.wav','.mp3','.flac'}


class VoiceBusy(ValueError):pass


def config():
    from .multimodal import speech_ready
    return {'local':True,'ready':speech_ready(),
        'model':'Local Whisper · CPU int8','max_seconds':setting('max_dictation_seconds'),
        'max_upload_mib':setting('max_dictation_mib'),
        'languages':[{'code':code,'label':label} for code,label in LANGUAGES.items()]}


def transcribe(path,language):
    from .multimodal import speech_model
    samples=decode_recording(path)
    segments,info=speech_model().transcribe(samples,language=None if language=='auto' else language,
        task='transcribe',beam_size=5,temperature=0,vad_filter=True,condition_on_previous_text=False,
        max_new_tokens=256)
    text=' '.join(s.text.strip() for s in segments if s.text.strip()).strip()
    if not text:raise ValueError('No intelligible speech detected. Speak clearly and try again.')
    if len(text)>4000:raise ValueError('Transcript is too long. Record a shorter question.')
    return {'text':text,'language':info.language,'duration_seconds':len(samples)/16000,'local':True}


def decode_recording(path):
    # Browser MediaRecorder WebM often omits duration metadata. Count decoded
    # samples instead, stopping at the cap before allocating an unbounded clip.
    import av
    import numpy as np
    parts=[];count=0;cap=(setting('max_dictation_seconds')+1)*16000
    def collect(frames):
        nonlocal count
        for frame in frames:
            samples=frame.to_ndarray().reshape(-1);count+=len(samples)
            if count>cap:raise ValueError(f'Record for at most {setting("max_dictation_seconds")} seconds.')
            parts.append(samples)
    try:
        with av.open(str(path),options={'protocol_whitelist':'file,pipe'}) as container:
            if not container.streams.audio:raise ValueError('Recording has no audio track.')
            resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
            for frame in container.decode(audio=0):
                frame.pts=None;collect(resampler.resample(frame))
            collect(resampler.resample(None))
    except av.error.FFmpegError as exc:
        raise ValueError('Recording could not be decoded. Try recording again in a recent browser.') from exc
    if not count:raise ValueError('Recording is empty. Try again.')
    return np.concatenate(parts).astype(np.float32)/32768


def worker(path,language,output):
    # The deadline can terminate this process even if a decoder or native model stalls.
    os.environ['HF_HUB_OFFLINE']='1'
    try:result={'result':transcribe(path,language)}
    except Exception as exc:result={'error':str(exc)}
    Path(output).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')


def recognize(stream,filename,language='auto'):
    if language not in LANGUAGES:raise ValueError('Choose a supported dictation language.')
    ext=Path(filename or '').suffix.lower()
    if ext not in EXTENSIONS:raise ValueError('Unsupported recording format. Use WebM, Ogg, MP4 or WAV.')
    if not config()['ready']:raise ValueError('Local speech model missing. Run uv run atlas setup-media, then retry.')
    if not LOCK.acquire(blocking=False):raise VoiceBusy('Another dictation is processing. Wait and try again.')
    started=time.perf_counter();process=None
    try:
        root=DATA/'dictation';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='recording-',dir=root) as temporary:
            path=Path(temporary)/('audio'+ext);output=Path(temporary)/'result.json';total=0
            try:
                with path.open('wb') as target:
                    while block:=stream.read(65536):
                        total+=len(block)
                        if total>setting('max_dictation_mib')*1048576:raise ValueError('Recording exceeds the dictation upload limit.')
                        target.write(block)
                if not total:raise ValueError('Recording is empty. Try again.')
                process=mp.get_context('spawn').Process(target=worker,args=(str(path),language,str(output)),daemon=True)
                process.start();process.join(setting('dictation_timeout_seconds'))
                if process.is_alive():raise ValueError('Local transcription timed out. Try a shorter recording.')
                if not output.exists():raise ValueError('Local speech worker stopped unexpectedly. Try again.')
                result=json.loads(output.read_text(encoding='utf-8'))
                if 'error' in result:raise ValueError(result['error'])
                return result['result']|{'elapsed_seconds':round(time.perf_counter()-started,3)}
            finally:
                if process is not None and process.pid is not None:
                    if process.is_alive():process.terminate()
                    process.join(5)
                    if process.is_alive():process.kill();process.join(5)
                    process.close()
    finally:LOCK.release()
