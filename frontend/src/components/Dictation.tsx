import{useEffect,useId,useRef,useState}from'react';
import{Mic,Square,ChevronDown,X,Loader2}from'lucide-react';
import{api}from'../api';

type SpeechConfig={ready:boolean;max_seconds:number;max_upload_mib:number;languages:{code:string;label:string}[]};
type State='idle'|'requesting'|'recording'|'transcribing'|'done'|'error';

export default function Dictation({onTranscript,onStart,disabled=false,question=false}:{onTranscript:(text:string)=>void;onStart?:()=>void;disabled?:boolean;question?:boolean}){
 const[config,setConfig]=useState<SpeechConfig|null>(null),[language,setLanguage]=useState(()=>localStorage.getItem('atlas-voice-language')||'auto'),[state,setState]=useState<State>('idle'),[open,setOpen]=useState(false),[message,setMessage]=useState('');
 const id=useId(),recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),request=useRef<AbortController|null>(null),epoch=useRef(0);
 const latest=useRef({onTranscript,onStart});latest.current={onTranscript,onStart};
 const active=state==='recording'||state==='requesting'||state==='transcribing';
 function release(){if(timer.current)clearTimeout(timer.current);timer.current=null;stream.current?.getTracks().forEach(t=>t.stop());stream.current=null}
 function cancel(){epoch.current++;request.current?.abort();request.current=null;const r=recorder.current;if(r){r.onstop=null;r.onerror=null;if(r.state!=='inactive')r.stop()}recorder.current=null;release();setState('idle');setMessage('');setOpen(false)}
 useEffect(()=>{const abort=new AbortController();api('/dictation/config',{signal:abort.signal}).then(setConfig).catch(e=>{if(e.name!=='AbortError'){setMessage('Local speech settings are unavailable. Check that Atlas is running.');setState('error')}});return()=>{abort.abort();epoch.current++;request.current?.abort();const r=recorder.current;if(r){r.onstop=null;r.onerror=null;if(r.state!=='inactive')r.stop()}release()}},[]);
 async function start(){
  if(!config)return;
  if(!config.ready){setMessage('Install the local speech model with uv run atlas setup-media, then refresh.');setState('error');setOpen(true);return}
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){setMessage('This browser cannot record audio here. Open Atlas on localhost in a recent browser.');setState('error');setOpen(true);return}
  const ticket=++epoch.current;setState('requesting');setOpen(true);setMessage('Allow microphone access to start.');latest.current.onStart?.();
  try{
   const input=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
   if(ticket!==epoch.current){input.getTracks().forEach(t=>t.stop());return}stream.current=input;
   const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));
   const r=new MediaRecorder(input,mime?{mimeType:mime}:undefined);recorder.current=r;
   const chunks:Blob[]=[];let size=0;
   r.ondataavailable=e=>{if(ticket!==epoch.current||!e.data.size)return;size+=e.data.size;if(size>config.max_upload_mib*1048576){cancel();setState('error');setMessage('Recording is too large. Try a shorter question.');setOpen(true);return}chunks.push(e.data)};
   r.onerror=()=>{if(ticket!==epoch.current)return;cancel();setState('error');setMessage('Microphone recording failed. Try again.');setOpen(true)};
   r.onstop=async()=>{
    release();recorder.current=null;if(ticket!==epoch.current)return;
    setState('transcribing');setMessage('Transcribing on this device…');
    const controller=new AbortController();request.current=controller;const deadline=setTimeout(()=>controller.abort(),100000);
    try{
     const type=r.mimeType||mime||'audio/webm',ext=type.includes('mp4')?'m4a':type.includes('ogg')?'ogg':'webm';
     const form=new FormData();form.append('file',new Blob(chunks,{type}),'dictation.'+ext);
     const result=await api('/dictation?language='+encodeURIComponent(language),{method:'POST',body:form,signal:controller.signal});
     if(ticket!==epoch.current)return;latest.current.onTranscript(result.text);setState('done');setMessage('Text added. Review it before searching.');
    }catch(e){if(ticket!==epoch.current)return;setState('error');setMessage((e as Error).name==='AbortError'?'Local transcription timed out. Try a shorter recording.':(e as Error).message)}finally{clearTimeout(deadline);if(ticket===epoch.current)request.current=null}
   };
   r.start(1000);setState('recording');setMessage('Listening locally. Stop when you finish.');timer.current=setTimeout(()=>{if(r.state==='recording')r.stop()},config.max_seconds*1000);
  }catch(e){if(ticket!==epoch.current)return;release();setState('error');const name=(e as Error).name;setMessage(name==='NotAllowedError'?'Microphone access was denied. Allow it in browser settings and try again.':name==='NotFoundError'?'No microphone found. Connect one and try again.':'Could not start the microphone. Check your device and try again.')}
 }
 const visible=open||active||state==='error';
 return <div className="dictation-control">
  <button type="button" className="submit dictation-mic" disabled={disabled||!config||state==='requesting'||state==='transcribing'} aria-label={state==='recording'?'Stop dictation':'Dictate locally'} aria-pressed={state==='recording'} title="Dictate locally" onClick={()=>state==='recording'?recorder.current?.stop():start()}>{state==='transcribing'||state==='requesting'?<Loader2 size={17} className="spin"/>:state==='recording'?<Square size={15}/>:<Mic size={18}/>}</button>
  <button type="button" className="dictation-settings" aria-label="Dictation language and settings" aria-expanded={visible} aria-controls={id} onClick={()=>setOpen(!visible)} disabled={active}><ChevronDown size={12}/></button>
  {visible&&<div className="dictation-popover" id={id}>
   <div className="dictation-heading"><strong>Voice · on this device</strong><button type="button" className="icon" aria-label={active?'Cancel dictation':'Close dictation settings'} onClick={cancel}><X size={16}/></button></div>
   <label>Dictation language<select value={language} disabled={active} onChange={e=>{setLanguage(e.target.value);localStorage.setItem('atlas-voice-language',e.target.value)}}>{(config?.languages||[{code:'auto',label:'Detect language'}]).map(l=><option key={l.code} value={l.code}>{l.label}</option>)}</select></label>
   <p>Whisper runs locally on CPU. Up to {config?.max_seconds||60} seconds. Recording is deleted after transcription.{question?' Dictating selects Local mode.':''} Nothing is submitted automatically.</p>
   {message&&<p className={state==='error'?'error':''} role={state==='error'?'alert':'status'}>{message}</p>}
   {state==='recording'&&<button type="button" onClick={()=>recorder.current?.stop()}>Stop & transcribe</button>}
  </div>}
 </div>
}
