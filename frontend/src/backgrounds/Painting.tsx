import {useEffect,useRef} from 'react';

/** Scroll intent affects only the composited painting layer, never text layout. */
export default function Painting(){
 const root=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  let frame=0,current=1,target=1,touchY=0;const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const animate=()=>{current+=(target-current)*.075;if(Math.abs(target-current)<.0002)current=target;root.current?.style.setProperty('--scroll-zoom',String(current));frame=current===target?0:requestAnimationFrame(animate)};
  const wheel=(e:WheelEvent)=>{if(document.hidden||reduced.matches||(e.target as Element).closest('.side-panel,.answer-content'))return;target=Math.min(1.13,Math.max(1,target-e.deltaY*.00018));if(!frame)frame=requestAnimationFrame(animate)};
  const touchStart=(e:TouchEvent)=>{touchY=e.touches[0].clientY};const touchMove=(e:TouchEvent)=>{const delta=touchY-e.touches[0].clientY;touchY=e.touches[0].clientY;if(document.hidden||reduced.matches||(e.target as Element).closest('.side-panel,.answer-drawer'))return;target=Math.min(1.13,Math.max(1,target-delta*.0004));if(!frame)frame=requestAnimationFrame(animate)};
  const visibility=()=>{root.current?.classList.toggle('paused',document.hidden);if(document.hidden){cancelAnimationFrame(frame);frame=0}else if(current!==target&&!reduced.matches)frame=requestAnimationFrame(animate)};
  const preference=()=>{if(reduced.matches){cancelAnimationFrame(frame);frame=0;current=target=1;root.current?.style.setProperty('--scroll-zoom','1')}};
  window.addEventListener('wheel',wheel,{passive:true});window.addEventListener('touchstart',touchStart,{passive:true});window.addEventListener('touchmove',touchMove,{passive:true});document.addEventListener('visibilitychange',visibility);reduced.addEventListener('change',preference);visibility();
  return()=>{cancelAnimationFrame(frame);window.removeEventListener('wheel',wheel);window.removeEventListener('touchstart',touchStart);window.removeEventListener('touchmove',touchMove);document.removeEventListener('visibilitychange',visibility);reduced.removeEventListener('change',preference)};
 },[]);
 return <div ref={root} className="painting" aria-hidden="true"><div className="painting-zoom"><div className="painting-image"/></div><div className="veil"/></div>
}
