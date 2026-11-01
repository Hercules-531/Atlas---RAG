import{useEffect,useId,useRef,useState}from'react';
import{Mic,Square,ChevronDown,X,Loader2}from'lucide-react';
import{api}from'../api';

type SpeechConfig={ready:boolean;model:string;max_seconds:number;max_upload_mib:number;timeout_seconds:number;max_vocabulary_chars:number;languages:{code:string;label:string}[]};
type State='idle'|'requesting'|'recording'|'transcribing'|'done'|'error';
let microphoneOwner:symbol|null=null;

export default function Dictation({onTranscript,onStart,disabled=false,question=false}:{onTranscript:(text:string)=>void;onStart?:()=>void;disabled?:boolean;question?:boolean}){
 const[config,setConfig]=useState<SpeechConfig|null>(null),[language,setLanguage]=useState(()=>localStorage.getItem('atlas-voice-language')||'en'),[device,setDevice]=useState(()=>localStorage.getItem('atlas-voice-device')||''),[processing,setProcessing]=useState(()=>localStorage.getItem('atlas-voice-processing')!=='raw'),[vocabulary,setVocabulary]=useState(()=>localStorage.getItem('atlas-voice-vocabulary')||'');
 const[devices,setDevices]=useState<MediaDeviceInfo[]>([]),[inputName,setInputName]=useState(''),[testing,setTesting]=useState(false),[state,setState]=useState<State>('idle'),[open,setOpen]=useState(false),[message,setMessage]=useState(''),[popupHeight,setPopupHeight]=useState(450);
 const id=useId(),owner=useRef(Symbol('microphone')),control=useRef<HTMLDivElement|null>(null),meter=useRef<HTMLMeterElement|null>(null),signal=useRef<HTMLSpanElement|null>(null),audio=useRef<AudioContext|null>(null),frame=useRef<number|null>(null);
 const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),request=useRef<AbortController|null>(null),epoch=useRef(0);
 const latest=useRef({onTranscript,onStart});latest.current={onTranscript,onStart};
 const active=state==='recording'||state==='requesting'||state==='transcribing',visible=open||active||state==='error';
 async function refreshDevices(){if(navigator.mediaDevices?.enumerateDevices)try{setDevices((await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='audioinput'&&d.deviceId&&d.deviceId!=='default'))}catch{/* Device labels may be hidden until permission is granted. */}}
 function release(){
  if(timer.current)clearTimeout(timer.current);timer.current=null;
  if(frame.current!==null)cancelAnimationFrame(frame.current);frame.current=null;
  const context=audio.current;audio.current=null;if(context&&context.state!=='closed')void context.close().catch(()=>{});
  stream.current?.getTracks().forEach(t=>{t.onended=null;t.stop()});stream.current=null;
  if(microphoneOwner===owner.current)microphoneOwner=null;
 }
 function cancel(){epoch.current++;request.current?.abort();request.current=null;const r=recorder.current;if(r){r.onstop=null;r.onerror=null;if(r.state!=='inactive')r.stop()}recorder.current=null;release();setTesting(false);setState('idle');setMessage('');setOpen(false)}
 useEffect(()=>{
  const abort=new AbortController();api('/dictation/config',{signal:abort.signal}).then(setConfig).catch(e=>{if(e.name!=='AbortError'){setMessage('Local speech settings are unavailable. Check that Atlas is running.');setState('error')}});
  void refreshDevices();navigator.mediaDevices?.addEventListener('devicechange',refreshDevices);
  return()=>{abort.abort();navigator.mediaDevices?.removeEventListener('devicechange',refreshDevices);epoch.current++;request.current?.abort();const r=recorder.current;if(r){r.onstop=null;r.onerror=null;if(r.state!=='inactive')r.stop()}release()};
 },[]);
 useEffect(()=>{if(!visible)return;const position=()=>{const rect=control.current?.getBoundingClientRect();if(rect)setPopupHeight(Math.max(160,innerHeight-rect.bottom-(question?88:24)))};position();window.addEventListener('resize',position);return()=>window.removeEventListener('resize',position)},[visible,question]);
 useEffect(()=>{if(state==='requesting'||state==='recording'){const card=control.current?.querySelector('.dictation-popover');if(card)card.scrollTop=0}},[state]);
 function monitor(input:MediaStream){
  try{
   const context=new AudioContext();audio.current=context;void context.resume().catch(()=>{});
   const analyser=context.createAnalyser();analyser.fftSize=512;context.createMediaStreamSource(input).connect(analyser);
   const samples=new Float32Array(analyser.fftSize);
   const tick=()=>{if(audio.current!==context)return;analyser.getFloatTimeDomainData(samples);let sum=0,peak=0;for(const value of samples){sum+=value*value;peak=Math.max(peak,Math.abs(value))}const db=20*Math.log10(Math.max(.000001,Math.sqrt(sum/samples.length)));if(meter.current)meter.current.value=Math.max(-60,Math.min(0,db));if(signal.current)signal.current.textContent=peak>.98?'Too loud · lower microphone gain':db< -45?'Quiet or paused · speak near the microphone':'Input detected';frame.current=requestAnimationFrame(tick)};tick();
  }catch{if(signal.current)signal.current.textContent='Input meter unavailable in this browser'}
 }
 async function start(testOnly=false){
  if(!config)return;
  if(!testOnly&&!config.ready){setMessage('Install the local speech model with uv run atlas setup-media, then refresh.');setState('error');setOpen(true);return}
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){setMessage('This browser cannot record audio here. Open Atlas on localhost in a recent browser.');setState('error');setOpen(true);return}
  if(microphoneOwner&&microphoneOwner!==owner.current){setMessage('Another dictation is using the microphone. Stop it first.');setState('error');setOpen(true);return}
  microphoneOwner=owner.current;const ticket=++epoch.current;setState('requesting');setTesting(testOnly);setOpen(true);setMessage('Allow microphone access. Wait for “Listening” before speaking.');if(!testOnly)latest.current.onStart?.();
  try{
   const input=await navigator.mediaDevices.getUserMedia({audio:{...(device?{deviceId:{exact:device}}:{}),channelCount:{ideal:1},sampleRate:{ideal:48000},echoCancellation:processing,noiseSuppression:processing,autoGainControl:processing},video:false});
   if(ticket!==epoch.current){input.getTracks().forEach(t=>t.stop());return}stream.current=input;
   setInputName(input.getAudioTracks()[0]?.label||'Selected microphone');void refreshDevices();monitor(input);
   const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));
   const r=new MediaRecorder(input,{...(mime?{mimeType:mime}:{}),audioBitsPerSecond:128000});recorder.current=r;
   const chunks:Blob[]=[];let size=0;
   const fail=(text:string)=>{if(ticket!==epoch.current)return;cancel();setState('error');setMessage(text);setOpen(true)};
   input.getAudioTracks().forEach(t=>{t.onended=()=>fail('The microphone disconnected. Select an available input and try again.')});
   r.ondataavailable=e=>{if(ticket!==epoch.current||!e.data.size)return;size+=e.data.size;if(size>config.max_upload_mib*1048576){fail('Recording is too large. Try a shorter question.');return}if(!testOnly)chunks.push(e.data)};
   r.onerror=()=>fail('Microphone recording failed. Try again.');
   r.onstop=async()=>{
    release();recorder.current=null;if(ticket!==epoch.current)return;
    if(testOnly){setState('done');setMessage('Microphone check finished. No audio was saved or transcribed.');return}
    setState('transcribing');setMessage('Transcribing on this device…');
    const controller=new AbortController();request.current=controller;const deadline=setTimeout(()=>controller.abort(),((config.timeout_seconds||150)+10)*1000);
    try{
     const type=r.mimeType||mime||'audio/webm',ext=type.includes('mp4')?'m4a':type.includes('ogg')?'ogg':'webm';
     const form=new FormData();form.append('file',new Blob(chunks,{type}),'dictation.'+ext);form.append('vocabulary',vocabulary);
     const result=await api('/dictation?language='+encodeURIComponent(language),{method:'POST',body:form,signal:controller.signal});
     if(ticket!==epoch.current)return;latest.current.onTranscript(result.text);setState('done');setMessage(['Text added. Review it before searching.',...(result.warnings||[])].join(' '));
    }catch(e){if(ticket!==epoch.current)return;setState('error');setMessage((e as Error).name==='AbortError'?'Local transcription timed out. Try a shorter recording.':(e as Error).message)}finally{clearTimeout(deadline);if(ticket===epoch.current)request.current=null}
   };
   r.start(250);setState('recording');setMessage(testOnly?'Listening · check the input meter as you speak.':'Listening · speak your question, then stop.');timer.current=setTimeout(()=>{if(r.state==='recording')r.stop()},(testOnly?15:config.max_seconds)*1000);
  }catch(e){if(ticket!==epoch.current)return;release();setState('error');const name=(e as Error).name;setMessage(name==='NotAllowedError'?'Microphone access was denied. Allow it in browser settings and try again.':name==='NotFoundError'||name==='OverconstrainedError'?'The selected microphone is unavailable. Choose another input in voice settings.':'Could not start the microphone. Check your device and try again.')}
 }
 return <div className="dictation-control" ref={control}>
  <button type="button" className="submit dictation-mic" disabled={(disabled&&state!=='recording')||!config||state==='requesting'||state==='transcribing'} aria-label={state==='recording'?(testing?'Stop microphone check':'Stop dictation'):'Dictate locally'} aria-pressed={state==='recording'} title="Dictate locally" onClick={()=>state==='recording'?recorder.current?.stop():start()}>{state==='transcribing'||state==='requesting'?<Loader2 size={17} className="spin"/>:state==='recording'?<Square size={15}/>:<Mic size={18}/>}</button>
  <button type="button" className="dictation-settings" aria-label="Dictation language and settings" aria-expanded={visible} aria-controls={id} onClick={()=>setOpen(!visible)} disabled={active}><ChevronDown size={12}/></button>
  {visible&&<div className="dictation-popover" id={id} style={{maxHeight:popupHeight}} onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();cancel()}}}>
   <div className="dictation-heading"><strong>Voice · on this device</strong><button type="button" className="icon" aria-label={active?'Cancel dictation':'Close dictation settings'} onClick={cancel}><X size={16}/></button></div>
   <label>Microphone<select value={device} disabled={active} onChange={e=>{setDevice(e.target.value);setInputName('');localStorage.setItem('atlas-voice-device',e.target.value)}}><option value="">System default microphone</option>{device&&!devices.some(d=>d.deviceId===device)&&<option value={device}>Saved microphone (unavailable)</option>}{devices.map((d,i)=><option key={d.deviceId} value={d.deviceId}>{d.label||'Microphone '+(i+1)}</option>)}</select></label>
   {inputName&&<p className="voice-device">Input used: {inputName}</p>}
   <div className="voice-signal" hidden={state!=='recording'}><meter ref={meter} min={-60} max={0} low={-45} high={-3} optimum={-18} value={-60} aria-label="Microphone input level"/><span ref={signal}>Waiting for input…</span></div>
   <label>Dictation language<select value={language} disabled={active} onChange={e=>{setLanguage(e.target.value);localStorage.setItem('atlas-voice-language',e.target.value)}}>{(config?.languages||[{code:'en',label:'English'}]).map(l=><option key={l.code} value={l.code}>{l.label}</option>)}</select></label>
   <p>For English / Indian English, choose English. Automatic detection can misread short questions.</p>
   <details className="voice-options"><summary>Vocabulary & microphone processing</summary>
    <label>Important words (optional)<input value={vocabulary} maxLength={config?.max_vocabulary_chars||500} disabled={active} placeholder="e.g. DreamDiffusion, Prune, RAG" onChange={e=>{setVocabulary(e.target.value);localStorage.setItem('atlas-voice-vocabulary',e.target.value)}}/></label>
    <p>Names and terms only. Hints can bias recognition; use a short list.</p>
    <label>Microphone processing<select value={processing?'speech':'raw'} disabled={active} onChange={e=>{setProcessing(e.target.value==='speech');localStorage.setItem('atlas-voice-processing',e.target.value)}}><option value="speech">Speech · noise reduction & automatic gain</option><option value="raw">Raw input · browser filters off</option></select></label>
   </details>
   <p>{config?.model||'Local Whisper'}. Up to {config?.max_seconds||60} seconds. Recording is deleted after transcription.{question?' Dictating selects Local mode.':''} Nothing is submitted automatically.</p>
   {message&&<p className={state==='error'?'error':''} role={state==='error'?'alert':'status'}>{message}</p>}
   {state==='recording'?<button type="button" onClick={()=>recorder.current?.stop()}>{testing?'Finish microphone check':'Stop & transcribe'}</button>:!active&&<button type="button" onClick={()=>start(true)}>Check microphone</button>}
  </div>}
 </div>
}
