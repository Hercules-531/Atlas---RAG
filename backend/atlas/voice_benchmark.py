"""Reproducible local ASR regression on synthetic English speech, not an accent benchmark."""
import gc
import json
import re
import tempfile
import time
import wave
from pathlib import Path
import numpy as np
from .config import ROOT,DATA
from . import voice,multimodal

GOLD='This is a synthetic observatory recording. The telescope recorded 18 sessions in June. The project code is amber.'
NAMES_GOLD='What is Dream Diffusion and how does retrieval augmented generation work in Atlas?'


def wer(reference,hypothesis):
    ref=re.findall(r'\w+',reference.lower());hyp=re.findall(r'\w+',hypothesis.lower())
    prev=list(range(len(hyp)+1))
    for i,a in enumerate(ref,1):
        row=[i]
        for j,b in enumerate(hyp,1):row.append(min(row[-1]+1,prev[j]+1,prev[j-1]+(a!=b)))
        prev=row
    return prev[-1]/max(1,len(ref))


def run(profile_name='both'):
    from faster_whisper import WhisperModel
    source=ROOT/'tests/fixtures/dictation-en.wav'
    clean=voice.decode_recording(source);rms=float(np.sqrt(np.mean(clean*clean)))
    random=np.random.default_rng(531);noise=random.normal(size=len(clean)).astype(np.float32)
    noise/=float(np.sqrt(np.mean(noise*noise)))
    variants={'clean':clean,'quiet_with_dc':clean*.02+.01,
        'noise_5db':np.clip(clean+noise*rms/10**(5/20),-.99,.99),
        'noise_0db':np.clip(clean+noise*rms,-.99,.99),
        'noise_minus5db':np.clip(clean+noise*rms*10**(5/20),-.99,.99),
        'names':voice.decode_recording(ROOT/'tests/fixtures/dictation-names.wav'),
        'silence':np.zeros_like(clean),'noise_only':noise*rms}
    result={'fixture':'Synthetic English TTS; not Indian-accent or real microphone speech.',
        'gold':GOLD,'names_gold':NAMES_GOLD,'sample_rate':16000,'duration_seconds':len(clean)/16000,'profiles':[]}
    with tempfile.TemporaryDirectory(prefix='atlas-asr-benchmark-') as temporary:
        paths={}
        for name,samples in variants.items():
            path=Path(temporary)/(name+'.wav');paths[name]=path
            with wave.open(str(path),'wb') as file:
                file.setnchannels(1);file.setsampwidth(2);file.setframerate(16000)
                file.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())
        for label,folder in [('before-base','whisper-base'),('after-turbo','whisper-large-v3-turbo')]:
            if profile_name!='both' and not label.startswith(profile_name):continue
            path=DATA/'models'/folder
            if not multimodal.complete_speech_assets(path):raise ValueError(f'Install complete local {folder} assets before benchmarking.')
            started=time.perf_counter();model=WhisperModel(str(path),device='cpu',compute_type='int8',local_files_only=True)
            profile={'name':label,'model_load_seconds':round(time.perf_counter()-started,3),'cases':[]}
            previous=multimodal.speech_model
            try:
                multimodal.speech_model=lambda:model
                for name,path in paths.items():
                    started=time.perf_counter();text='';error=None;warnings=[]
                    try:
                        if label=='before-base':
                            segments,_=model.transcribe(voice.decode_recording(path),language='en',task='transcribe',beam_size=5,temperature=0,vad_filter=True,condition_on_previous_text=False,max_new_tokens=256)
                            text=' '.join(s.text.strip() for s in segments).strip()
                        else:
                            response=voice.transcribe(path,'en');text=response['text'];warnings=response['warnings']
                    except ValueError as exc:error=str(exc)
                    case={'name':name,'text':text,'error':error,'warnings':warnings,'elapsed_seconds':round(time.perf_counter()-started,3)}
                    if name not in {'silence','noise_only'}:case['word_error_rate']=round(wer(NAMES_GOLD if name=='names' else GOLD,text),4)
                    else:case['invented_words']=len(re.findall(r'\w+',text))
                    profile['cases'].append(case);print(json.dumps({'profile':label,**case}),flush=True)
            finally:multimodal.speech_model=previous
            result['profiles'].append(profile);del model;gc.collect()
    output=ROOT/('reports/dictation-quality'+('' if profile_name=='both' else '-'+profile_name)+'.json');output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Saved '+str(output),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['before','after','both'],default='both')
    run(parser.parse_args().profile)
