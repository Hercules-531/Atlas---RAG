import {useEffect,useState} from 'react';
import {ArrowUpRight,FileText,Shield} from 'lucide-react';
import {api} from '../api';

export type SourceImage={id:string;url:string;location:string;kind:string;width:number;height:number};
export type Citation={id:string;chunk_id?:string;document_id:string;name:string;location:string;text:string;images?:SourceImage[]};
type Props={answer?:string;citations?:Citation[];warnings?:string[];blocked:boolean;onReceipt:()=>void;hasReceipt:boolean};

export default function Answer({answer,citations=[],warnings=[],blocked,onReceipt,hasReceipt}:Props){
  const[active,setActive]=useState('');
  const formatted=(answer||'').replace(/\[((?:S\d+)(?:\s*,\s*S?\d+)+)\]/g,(_,group:string)=>group.split(',').map(token=>'['+token.trim()+']').join(' '));
  const referenced=new Set(Array.from(formatted.matchAll(/\[(S?\d+)\]/g),m=>m[1].startsWith('S')?m[1]:'S'+m[1]));
  const visible=referenced.size?citations.filter(c=>referenced.has(c.id)):citations;
  const[loadedImages,setLoadedImages]=useState<Record<string,SourceImage[]>>({});
  const[allImages,setAllImages]=useState(false);
  const citationKey=JSON.stringify(visible.map(c=>[c.document_id,c.location,c.images]));
  useEffect(()=>{let cancelled=false;setAllImages(false);setLoadedImages({});Promise.all(visible.filter(c=>!c.images).map(async c=>{try{return [c.id,await api('/files/'+encodeURIComponent(c.document_id)+'/images?location='+encodeURIComponent(c.location))] as const}catch{return [c.id,[]] as const}})).then(entries=>{if(!cancelled)setLoadedImages(Object.fromEntries(entries))});return()=>{cancelled=true}},[citationKey]);
  const images=visible.flatMap(c=>(c.images||loadedImages[c.id]||[]).map(image=>({...image,citation:c})));
  const uniqueImages=Array.from(new Map(images.map(i=>[i.url,i])).values());
  function visit(event:React.MouseEvent<HTMLAnchorElement>,id:string){
    event.preventDefault();setActive(id);
    const detail=document.getElementById('source-'+id) as HTMLDetailsElement|null;
    if(detail){detail.open=true;detail.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'nearest'});detail.focus({preventScroll:true})}
    history.replaceState(null,'','#source-'+id);
  }
  const parts=formatted.split(/(\[(?:S)?\d+\])/g);
  return <div className="result-layout"><article className="main-answer"><div className="answer-title"><h2>{blocked?'Nothing sent.':'Your answer'}</h2><span>Grounded in your documents</span></div><div className="answer-text">{parts.map((part,i)=>{
    const match=part.match(/^\[(S?\d+)\]$/);const id=match?(match[1].startsWith('S')?match[1]:'S'+match[1]):'';
    return id&&citations.some(c=>c.id===id)?<a key={i} className="citation" href={'#source-'+id} aria-label={'Go to source '+id.slice(1)} onClick={e=>visit(e,id)}>{id.slice(1)}</a>:<span key={i}>{part}</span>
  })}</div>{uniqueImages.length>0&&<section className="source-image-gallery" aria-label="Images from your sources"><h3>From the source</h3><p>Local source previews. Uploaded images and video frames may have machine-generated descriptions; cloud answers receive selected text only.</p><div className="source-image-grid">{uniqueImages.slice(0,allImages?undefined:4).map(image=><figure key={image.url}><a href={image.url} target="_blank" rel="noreferrer" aria-label={'Open source image from '+image.citation.name+', '+image.location}><img src={image.url} loading="lazy" decoding="async" alt={'Source preview from '+image.citation.name+', '+image.location}/></a><figcaption>Source {image.citation.id.slice(1)} · {image.location}{image.kind==='page_preview'?' · page preview':''}</figcaption></figure>)}</div>{uniqueImages.length>4&&<button onClick={()=>setAllImages(!allImages)}>{allImages?'Show fewer images':'Show all '+uniqueImages.length+' images'}</button>}</section>}{warnings.map(w=><p role="alert" className="error" key={w}>{w}</p>)}{hasReceipt&&<button className="receipt-link" onClick={onReceipt}><Shield size={16}/> What was shared?</button>}</article>
  <section className="answer-sources" aria-label="Sources"><h3>Sources <span>{visible.length}</span></h3><p className="source-hint">Select a citation to inspect its evidence.</p>{visible.map(c=>{const page=c.location.match(/page (\d+)/);const time=c.location.match(/time (\d+):(\d+):([\d.]+)/);const original='/api/files/'+encodeURIComponent(c.document_id)+'/content'+(page?'#page='+page[1]:time?'#t='+(Number(time[1])*3600+Number(time[2])*60+Number(time[3])):'');return <details className={'source-card '+(active===c.id?'active':'')} key={c.id} id={'source-'+c.id} tabIndex={-1}><summary><span className="source-number">{c.id.slice(1)}</span><span><strong>{c.name}</strong><small>{c.location}</small></span><FileText size={16}/></summary><div className="source-evidence"><p>{c.text}</p>{/\.(mp4|webm|mov|mkv)$/i.test(c.name)&&<video controls preload="metadata" src={original}/ >}{/\.(wav|mp3|m4a|ogg|flac|aac)$/i.test(c.name)&&<audio controls preload="metadata" src={original}/>}<a href={original} target="_blank" rel="noreferrer">Open original {page?'page':'file'} <ArrowUpRight size={14}/></a></div></details>})}{!visible.length&&<p className="source-hint">No source evidence for this response.</p>}</section></div>
}
