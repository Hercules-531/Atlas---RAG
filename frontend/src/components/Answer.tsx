import {useState} from 'react';
import {ArrowUpRight,FileText,Shield} from 'lucide-react';

export type Citation={id:string;chunk_id?:string;document_id:string;name:string;location:string;text:string};
type Props={answer?:string;citations?:Citation[];warnings?:string[];blocked:boolean;onReceipt:()=>void;hasReceipt:boolean};

export default function Answer({answer,citations=[],warnings=[],blocked,onReceipt,hasReceipt}:Props){
  const[active,setActive]=useState('');
  const referenced=new Set(Array.from((answer||'').matchAll(/\[(S?\d+)\]/g),m=>m[1].startsWith('S')?m[1]:'S'+m[1]));
  const visible=referenced.size?citations.filter(c=>referenced.has(c.id)):citations;
  function visit(event:React.MouseEvent<HTMLAnchorElement>,id:string){
    event.preventDefault();setActive(id);
    const detail=document.getElementById('source-'+id) as HTMLDetailsElement|null;
    if(detail){detail.open=true;detail.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'nearest'});detail.focus({preventScroll:true})}
    history.replaceState(null,'','#source-'+id);
  }
  const parts=(answer||'').split(/(\[(?:S)?\d+\])/g);
  return <div className="result-layout"><article className="main-answer"><div className="answer-title"><h2>{blocked?'Nothing sent.':'Your answer'}</h2><span>Grounded in your documents</span></div><div className="answer-text">{parts.map((part,i)=>{
    const match=part.match(/^\[(S?\d+)\]$/);const id=match?(match[1].startsWith('S')?match[1]:'S'+match[1]):'';
    return id&&citations.some(c=>c.id===id)?<a key={i} className="citation" href={'#source-'+id} aria-label={'Go to source '+id.slice(1)} onClick={e=>visit(e,id)}>{id.slice(1)}</a>:<span key={i}>{part}</span>
  })}</div>{warnings.map(w=><p role="alert" className="error" key={w}>{w}</p>)}{hasReceipt&&<button className="receipt-link" onClick={onReceipt}><Shield size={16}/> What was shared?</button>}</article>
  <section className="answer-sources" aria-label="Sources"><h3>Sources <span>{visible.length}</span></h3><p className="source-hint">Select a citation to inspect its evidence.</p>{visible.map(c=>{const page=c.location.match(/page (\d+)/);const original='/api/files/'+encodeURIComponent(c.document_id)+'/content'+(page?'#page='+page[1]:'');return <details className={'source-card '+(active===c.id?'active':'')} key={c.id} id={'source-'+c.id} tabIndex={-1}><summary><span className="source-number">{c.id.slice(1)}</span><span><strong>{c.name}</strong><small>{c.location}</small></span><FileText size={16}/></summary><div className="source-evidence"><p>{c.text}</p><a href={original} target="_blank" rel="noreferrer">Open original {page?'page':'file'} <ArrowUpRight size={14}/></a></div></details>})}{!visible.length&&<p className="source-hint">No source evidence for this response.</p>}</section></div>
}
