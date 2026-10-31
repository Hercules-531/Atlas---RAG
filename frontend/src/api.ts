export async function api(path:string,options:RequestInit={}){const r=await fetch('/api'+path,options);const data=await r.json();if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;}
export function post(path:string,data:unknown={}){return api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});}
