import{useEffect,useState}from'react';
import{api}from'../api';
import Dictation from'./Dictation';
type Hit={id:string;name:string;kind:string;match_type:'visual'|'speech';location:string;excerpt:string;url:string;images:{url:string;timestamp?:number}[]};
function playback(url:string,location:string){const m=location.match(/time (\d+):(\d+):([\d.]+)/);return url+(m?'#t='+(Number(m[1])*3600+Number(m[2])*60+Number(m[3])):'')}
export default function MediaSearch(){
 const[q,setQ]=useState(''),[kind,setKind]=useState('all'),[content,setContent]=useState('auto'),[results,setResults]=useState<Hit[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false),[review,setReview]=useState(false);
 useEffect(()=>{const controller=new AbortController();setResults([]);if(!q.trim()||review){setBusy(false);return}setBusy(true);const timer=setTimeout(()=>api('/search?q='+encodeURIComponent(q)+'&kind='+kind+'&content='+content,{signal:controller.signal}).then(hits=>{setResults(hits);setError('')}).catch(e=>{if(e.name!=='AbortError')setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setBusy(false)}),350);return()=>{clearTimeout(timer);controller.abort()}},[q,kind,content,review]);
 return <section className="media-search">
  <p>Search what images and videos show, and what audio files say. To include words spoken in a video, change “Match content.” Descriptions can contain errors; video frames are sampled.</p>
  <label htmlFor="media-query">Search your media · English or your language</label><div className="media-query"><input id="media-query" className="filter" value={q} onChange={e=>{setQ(e.target.value);setError('')}} placeholder="e.g. blue flower, नीला फूल…"/><Dictation onStart={()=>setReview(true)} onTranscript={text=>{setQ(text);setError('')}}/></div>
  {review&&q.trim()&&<button onClick={()=>setReview(false)}>Search reviewed text</button>}
  <label>Media type<select value={kind} onChange={e=>{setKind(e.target.value);setError('')}}><option value="all">All media</option><option value="image">Images</option><option value="video">Video</option><option value="audio">Audio</option></select></label>
  <label>Match content<select value={content} onChange={e=>{setContent(e.target.value);setError('')}}><option value="auto">Visuals + audio-file speech</option><option value="visual">Visuals only</option><option value="speech">Spoken words (including videos)</option><option value="all">All indexed content</option></select></label>
  {busy&&<p role="status">Searching locally…</p>}{error&&<p role="alert" className="error">{error}</p>}
  {!review&&!busy&&q.trim()&&!results.length&&!error&&<p role="status">No strong matches in the selected content. Try another description or change “Match content.” New uploads must finish indexing first.</p>}
  {!busy&&!error&&results.map(r=><article className="media-hit" key={r.id}><h3>{r.name}</h3><small>{r.kind} · {r.location} · {r.match_type==='visual'?'Visual description match':'Spoken words match'}</small>
   {r.match_type==='speech'&&r.kind==='video'&&<p>This matches the video’s speech, not necessarily what it shows.</p>}
   {r.images[0]&&<img src={r.images[0].url} alt={'Preview from '+r.name} loading="lazy"/>}
   {r.kind==='video'&&<video controls preload="metadata" src={playback(r.url,r.location)}/ >}{r.kind==='audio'&&<audio controls preload="metadata" src={playback(r.url,r.location)}/>}
   <p>{r.excerpt}</p><a href={playback(r.url,r.location)} target="_blank" rel="noreferrer">Open local source</a></article>)}
 </section>
}
