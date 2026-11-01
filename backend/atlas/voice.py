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
    from .multimodal import speech_ready,speech_path
    return {'local':True,'ready':speech_ready(),
        'model':speech_path().name+' · CPU int8','max_seconds':setting('max_dictation_seconds'),
        'timeout_seconds':setting('dictation_timeout_seconds'),'max_vocabulary_chars':500,
        'max_upload_mib':setting('max_dictation_mib'),
        'languages':[{'code':code,'label':label} for code,label in LANGUAGES.items()]}


def prepare_audio(samples):
    """DC removal and bounded gain; no noise synthesis or LLM transcript rewriting."""
    import numpy as np
    samples=np.asarray(samples,dtype=np.float32)
    samples=samples-float(samples.mean())
    rms=float(np.sqrt(np.mean(samples*samples)));peak=float(np.max(np.abs(samples)))
    if rms<.0003 or peak<.001:raise ValueError('The microphone input is too quiet. Select the correct microphone and move closer before trying again.')
    warnings=[]
    clipped=float(np.mean(np.abs(samples)>=.98))
    if clipped>.01:warnings.append('The recording is distorted or clipping. Lower the microphone gain or move farther away.')
    gain=min(10**(18/20),10**(-23/20)/rms,.95/max(peak,.000001)) if rms<10**(-30/20) else 1.
    gain=max(1.,gain)
    if rms<10**(-40/20):warnings.append('The microphone was quiet; bounded local gain was applied. Check the selected input.')
    return samples*gain,{'rms_dbfs':round(20*float(np.log10(rms)),1),'peak_dbfs':round(20*float(np.log10(peak)),1),
        'clipped_fraction':round(clipped,4),'gain_db':round(20*float(np.log10(gain)),1)},warnings


def transcribe(path,language,vocabulary=''):
    from .multimodal import speech_model
    samples=decode_recording(path)
    samples,audio,warnings=prepare_audio(samples)
    model=speech_model()
    if vocabulary and len(model.hf_tokenizer.encode(vocabulary).ids)>96:
        raise ValueError('Vocabulary hints are too long for speech decoding. Use a shorter list of names or terms.')
    segments,info=model.transcribe(samples,language=None if language=='auto' else language,
        task='transcribe',beam_size=5,temperature=0,vad_filter=True,condition_on_previous_text=False,
        vad_parameters={'min_speech_duration_ms':120,'min_silence_duration_ms':400,'speech_pad_ms':350},
        hotwords=vocabulary or None)
    segments=[s for s in segments if s.text.strip()]
    text=' '.join(s.text.strip() for s in segments).strip()
    if not text:raise ValueError('No intelligible speech detected. Speak clearly and try again.')
    if len(text)>4000:raise ValueError('Transcript is too long. Record a shorter question.')
    weights=[max(1,len(s.text.split())) for s in segments]
    logprob=sum(getattr(s,'avg_logprob',0)*w for s,w in zip(segments,weights))/sum(weights)
    if logprob < -1.1:raise ValueError('Speech was not clear enough to transcribe reliably. Check the microphone, select English for English/Indian English, and record again.')
    if logprob < -.75:warnings.append('Some words may be uncertain. Review the transcript carefully.')
    if language=='auto' and getattr(info,'language_probability',1)<.55:
        warnings.append('The spoken language was uncertain. Select the language explicitly for short questions.')
    return {'text':text,'language':info.language,'duration_seconds':len(samples)/16000,'local':True,
        'audio_quality':audio,'warnings':warnings}


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


def worker(path,language,output,vocabulary=''):
    # The deadline can terminate this process even if a decoder or native model stalls.
    os.environ['HF_HUB_OFFLINE']='1'
    try:result={'result':transcribe(path,language,vocabulary)}
    except Exception as exc:result={'error':str(exc)}
    Path(output).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')


def recognize(stream,filename,language='auto',vocabulary=''):
    if language not in LANGUAGES:raise ValueError('Choose a supported dictation language.')
    if len(vocabulary)>500:raise ValueError('Vocabulary hints must be 500 characters or fewer.')
    vocabulary=' '.join(vocabulary.split())
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
                process=mp.get_context('spawn').Process(target=worker,args=(str(path),language,str(output),vocabulary),daemon=True)
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
