import React from 'react';
import {Copy,Pencil,RotateCcw,ArrowRight} from 'lucide-react';
import MessageMarkdown,{copyText} from './MessageMarkdown';
import AttachmentChips from './AttachmentChips';
import ToolActivity from './ToolActivity';
export default function MessageItem({message:m,notify,busy,onEdit,onRegenerate,onContinue,last=false,live=false,canUndo=false}){
 const assistant=m.role!=='user',s=m.stats;
 const date=typeof m.created==='number'&&Number.isFinite(m.created)?new Date(m.created*1000):null;
 const timestamp=date&&!Number.isNaN(date.getTime())?<time className="message-time" dateTime={date.toISOString()} title={date.toLocaleString('pt-BR')} data-copy-exclude="true">{date.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</time>:null;
 const activities=m.activities||s?.activities||[],sequence=m.timeline||s?.timeline;
 const ordered=activities.length&&sequence?.some(b=>b.type==='activity')&&sequence.filter(b=>b.type==='text').map(b=>b.content).join('')===(m.content||'');
 const byId=new Map(activities.map(a=>[a.id,a]));
 return <article className={'message '+(assistant?'assistant':'user')+(live?' live':'')}>
 {assistant&&<img className="assistant-mark" data-copy-exclude="true" src="/central-mark.png" alt="" aria-hidden="true"/>}
 <div className="message-body">{live&&<div className="live-heading">Central IA · {m.activities?.some(a=>a.status==='approval')?'aguardando aprovação':'gerando'}</div>}
 <AttachmentChips items={m.attachments} stored/>
 {m.reasoning&&<details className="thinking"><summary>Pensamento retornado pelo motor</summary><div className="reasoning">{m.reasoning}</div></details>}
 {ordered?<div className="message-timeline">{sequence.map((block,index)=>block.type==='text'?<div className="timeline-text" data-timeline-kind="text" key={index}><MessageMarkdown content={block.content} onError={notify}/></div>:byId.has(block.id)?<div className="timeline-tool" data-timeline-kind="activity" key={block.id}><ToolActivity items={[byId.get(block.id)]} notify={notify} canUndo={canUndo}/></div>:null)}</div>:<><MessageMarkdown content={m.content||(live?(m.activities?.some(a=>a.status==='approval')?'Revise a ação proposta abaixo.':m.activities?.some(a=>a.status==='running')?'Executando a ferramenta solicitada…':'Aguardando o motor…'):'')} onError={notify}/>
 <ToolActivity items={activities} notify={notify} canUndo={canUndo}/></>}
 {!live&&<div className="message-top" data-copy-exclude="true"><strong>{assistant?'Central IA':'Você'}</strong>{timestamp}<div className="actions"><button aria-label="Copiar mensagem" title="Copiar mensagem" onClick={()=>copyText(m.content,notify)}><Copy size={17} aria-hidden="true"/><span>Copiar</span></button><button disabled={busy} aria-label="Editar mensagem" title="Editar mensagem" onClick={()=>onEdit(m)}><Pencil size={17} aria-hidden="true"/><span>Editar</span></button>{assistant&&last&&!busy&&<><button onClick={onRegenerate}><RotateCcw size={17}/>Regenerar</button><button onClick={onContinue}><ArrowRight size={17}/>Continuar</button></>}</div>
 {s?.finish_reason&&<details className="generation-details"><summary>Detalhes{s.elapsed!=null&&` (${s.elapsed.toFixed(2)} s)`}</summary><footer>{s.generated_tokens??'—'} tokens · {s.elapsed?.toFixed(2)} s de geração{s.ttft!=null&&` · primeiro trecho em ${s.ttft.toFixed(2)} s`} · {s.tokens_per_second?.toFixed(2)??'—'} tokens/s no total{s.backend_timings?.predicted_per_second>0&&` · decodificação: ${s.backend_timings.predicted_per_second.toFixed(2)} tokens/s`}{s.usage?.prompt_tokens_details?.cached_tokens!=null&&` · ${s.usage.prompt_tokens_details.cached_tokens} tokens de prompt reutilizados`} · {s.finish_reason}{s.truncated&&' · Resposta possivelmente truncada'}</footer></details>}</div>}
 {live&&timestamp}
 </div></article>;
}
