"""Local caption/transcript media search; same text embedder, no raw cloud media."""
import base64
import io
import json
import math
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageOps
from .config import DATA,setting
from . import media
from .llm import generate

IMAGES={'.png','.jpg','.jpeg','.webp','.gif'}
VIDEOS={'.mp4','.webm','.mov','.mkv'}
AUDIO={'.wav','.mp3','.m4a','.ogg','.flac','.aac'}
SUPPORTED=IMAGES|VIDEOS|AUDIO

def stamp(seconds):
    seconds=max(0,float(seconds));return f'{int(seconds//3600):02d}:{int(seconds%3600//60):02d}:{seconds%60:06.3f}'

def tools(name):
    binary=shutil.which(name)
    if not binary:raise ValueError(f'{name} is required for local media processing; install FFmpeg and retry indexing.')
    return binary

def probe(path):
    command=[tools('ffprobe'),'-v','error','-protocol_whitelist','file,pipe','-show_entries','format=duration:stream=codec_type','-of','json',str(path)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30,check=True)
    info=json.loads(result.stdout);duration=float(info.get('format',{}).get('duration',0))
    if not math.isfinite(duration) or duration<=0:raise ValueError('Media duration is missing or invalid')
    if duration>setting('max_media_seconds'):raise ValueError(f'Media exceeds {setting("max_media_seconds")} seconds; split it into shorter clips.')
    return duration,{s.get('codec_type') for s in info.get('streams',[])}

def ffmpeg(args):
    subprocess.run([tools('ffmpeg'),'-hide_banner','-loglevel','error','-y','-protocol_whitelist','file,pipe']+args,capture_output=True,timeout=120,check=True)

def caption(path,session):
    with Image.open(path) as original:
        if original.width*original.height>setting('max_source_image_pixels'):raise ValueError('Image exceeds decoded pixel limit')
        oriented=ImageOps.exif_transpose(original).convert('RGBA');canvas=Image.new('RGBA',oriented.size,'white');canvas.alpha_composite(oriented)
        image=canvas.convert('RGB');image.thumbnail((768,768))
        output=io.BytesIO();image.save(output,format='JPEG',quality=88)
    encoded='data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode()
    result=generate('Describe this source image in up to 100 words for semantic search. Include clearly visible labels and numbers.','',
        'local',session,feature='local-media-caption',images=[encoded])
    return result['answer']

def speech_path():
    return Path(os.getenv('ATLAS_SPEECH_MODEL_DIR') or DATA/'models/whisper-base').expanduser().resolve()

def speech_ready():
    path=speech_path()
    return all((path/name).is_file() for name in ('model.bin','config.json','tokenizer.json')) and any((path/name).is_file() for name in ('vocabulary.txt','vocabulary.json'))

@lru_cache
def speech_model():
    path=speech_path()
    if not speech_ready():raise ValueError('Complete local speech model missing (weights, tokenizer, config, vocabulary). Run uv run atlas setup-media, then retry.')
    from faster_whisper import WhisperModel
    return WhisperModel(str(path),device='cpu',compute_type='int8',local_files_only=True)

def transcribe(path):
    duration,_=probe(path)
    segments,info=speech_model().transcribe(str(path),beam_size=3,vad_filter=True,condition_on_previous_text=False)
    for segment in segments:
        start=min(duration,max(0,float(segment.start)));end=min(duration,max(start,float(segment.end)))
        if segment.text.strip() and start<duration:
            yield f'Local speech transcript (may contain recognition errors): {segment.text.strip()}',f'time {stamp(start)} – {stamp(end)}'

def extract(path):
    path=Path(path);ext=path.suffix.lower();destination=media.folder(path)
    session='ingest-'+path.stem
    if ext in IMAGES:
        media.index(path)
        description=caption(path,session)
        yield 'Local machine-generated visual description (not verified): '+description,'image 1'
        return
    duration,streams=probe(path)
    destination.mkdir(parents=True,exist_ok=True)
    if ext in VIDEOS and 'video' not in streams:raise ValueError('No video stream found')
    if ext in AUDIO and 'audio' not in streams:raise ValueError('No audio stream found')
    manifest={'images':[],'warnings':[],'duration':duration,'index_method':'Local descriptions and speech transcripts; not exhaustive frame analysis'}
    manifest_path=destination/'manifest.json'
    if ext in VIDEOS:
        count=min(setting('max_video_frames'),max(1,math.ceil(duration/10)))
        for index in range(count):
            timestamp=0 if count==1 else (duration-.1)*index/(count-1)
            frame=destination/f'frame-{index:03d}.jpg'
            ffmpeg(['-ss',str(timestamp),'-i',str(path),'-frames:v','1','-vf','scale=1280:1280:force_original_aspect_ratio=decrease',str(frame)])
            description=caption(frame,session)
            with Image.open(frame) as im:width,height=im.size
            location='time '+stamp(timestamp)
            manifest['images'].append({'id':f'frame-{index:03d}','filename':frame.name,'location':location,'kind':'video_frame','width':width,'height':height,'timestamp':timestamp})
            manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
            yield 'Local sampled-frame description (not verified): '+description,location
    if 'audio' in streams:
        audio=destination/'speech.wav'
        spoken=False
        try:
            ffmpeg(['-i',str(path),'-vn','-ac','1','-ar','16000',str(audio)])
            for text,location in transcribe(audio):
                spoken=True
                yield text,location
        finally:audio.unlink(missing_ok=True)
        if ext in AUDIO and not spoken:raise ValueError('No intelligible speech detected. Audio search indexes speech, not music or sound effects.')
    manifest_path.write_text(json.dumps(manifest),encoding='utf-8')

def setup():
    from huggingface_hub import snapshot_download
    return snapshot_download('Systran/faster-whisper-base',local_dir=DATA/'models/whisper-base',
        allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary*'])
