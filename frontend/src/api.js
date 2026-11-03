let token = '';
export async function api(path, data, method='POST') {
  const res=await fetch('/api'+path, data===undefined ? {} : {method,headers:{'Content-Type':'application/json','X-Central-Token':token},body:JSON.stringify(data)});
  if(!res.ok) {let e=await res.json().catch(()=>({detail:res.statusText})); throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail));}
  return res.json();
}
export async function bootstrap(){const b=await api('/bootstrap');token=b.token;return b;}
export async function generate(data,onEvent){
  const res=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json','X-Central-Token':token},body:JSON.stringify(data)});
  if(!res.ok){const e=await res.json();throw Error(e.detail||'Falha na geração');}
  const reader=res.body.getReader(), decoder=new TextDecoder();let buffer='';
  function parse(block){let kind='message',parts=[];for(const line of block.split('\n')){if(line.startsWith('event:'))kind=line.slice(6).trim();if(line.startsWith('data:'))parts.push(line.slice(5).trimStart());}if(parts.length)onEvent(kind,JSON.parse(parts.join('\n')));}
  while(true){const {done,value}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done}).replaceAll('\r\n','\n');let end;while((end=buffer.indexOf('\n\n'))>=0){parse(buffer.slice(0,end));buffer=buffer.slice(end+2);}if(done)break;}
}
export function download(name, value, type='application/json'){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export const bytes=n=>n==null?'Não disponível':(n/1024**3).toFixed(2)+' GB';
