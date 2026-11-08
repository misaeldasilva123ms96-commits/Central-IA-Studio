import React,{useEffect,useState} from 'react';
import {ChevronRight,LoaderCircle,Check} from 'lucide-react';
import MessageMarkdown from './MessageMarkdown';
import ToolActivity from './ToolActivity';
export function duration(seconds){const n=Math.max(0,Math.floor(seconds||0));return n<60?n+' s':Math.floor(n/60)+' min '+n%60+' s';}
function WorkStatus({live,hasAnswer,approval,created,elapsed}){
 const [now,setNow]=useState(Date.now());
 useEffect(()=>{if(!live)return;setNow(Date.now());const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[live]);
 const seconds=live&&created!=null?(now-created*1000)/1000:elapsed;
 return <span>{live?(approval?'Aguardando aprovação · ':hasAnswer?'Respondendo · ':'Processando há ')+(seconds!=null?duration(seconds):'…'):'Processado'+(seconds!=null?' em '+duration(seconds):'')}</span>;
}
export default function WorkPanel({blocks,activities,live,hasAnswer,created,elapsed,notify,canUndo}){
 const approval=activities.some(a=>a.status==='approval'),[open,setOpen]=useState(live&&!hasAnswer);
 useEffect(()=>{setOpen(Boolean(approval||(live&&!hasAnswer)));},[live,hasAnswer,approval]);
 const byId=new Map(activities.map(a=>[a.id,a]));
 return <details className="thinking work-panel" open={approval||open} onToggle={e=>setOpen(e.currentTarget.open)} data-copy-exclude="true"><summary><ChevronRight className="work-chevron" size={15}/>{live?<LoaderCircle size={14} className="spin"/>:<Check size={14}/>}<WorkStatus {...{live,hasAnswer,approval,created,elapsed}}/><small>{activities.length?`${activities.length} ${activities.length===1?'ferramenta':'ferramentas'}`:blocks.some(b=>b.type==='reasoning')?'Pensamento retornado pelo motor':'Modelo local'}</small></summary><div className="work-sequence">{blocks.map((block,index)=>block.type==='activity'?byId.has(block.id)&&<div data-timeline-kind="activity" key={block.id}><ToolActivity items={[byId.get(block.id)]} notify={notify} canUndo={canUndo}/></div>:<div className={block.type==='reasoning'?'reasoning work-reasoning':'work-commentary'} data-timeline-kind={block.type} key={index}><MessageMarkdown content={block.content} onError={notify}/></div>)}</div></details>;
}
