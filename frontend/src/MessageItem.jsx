import React from 'react';
import {Copy,Pencil,RotateCcw,ArrowRight} from 'lucide-react';
import MessageMarkdown,{copyText} from './MessageMarkdown';
import AttachmentChips from './AttachmentChips';
import WorkPanel from './WorkPanel';
export default function MessageItem({message:m,notify,busy,onEdit,onRegenerate,onContinue,last=false,live=false,canUndo=false}){
 const assistant=m.role!=='user',s=m.stats;
 const date=typeof m.created==='number'&&Number.isFinite(m.created)?new Date(m.created*1000):null;
 const timestamp=date&&!Number.isNaN(date.getTime())?<time className="message-time" dateTime={date.toISOString()} title={date.toLocaleString('pt-BR')} data-copy-exclude="true">{date.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</time>:null;
 const activities=m.activities||s?.activities||[],sequence=m.timeline||s?.timeline;
 const validSequence=sequence?.length&&sequence.filter(b=>b.type==='text').map(b=>b.content).join('')===(m.content||'');
 let blocks=validSequence?sequence:[...(m.content?[{type:'text',content:m.content}]:[]),...activities.map(a=>({type:'activity',id:a.id}))];
 // Older histories stored aggregate reasoning without its position in the sequence.
 if(m.reasoning&&!blocks.some(b=>b.type==='reasoning'))blocks=[{type:'reasoning',content:m.reasoning},...blocks];
 if(!validSequence&&m.content)blocks=[...blocks.filter(b=>b.type!=='text'),{type:'text',content:m.content}];
 let boundary=-1;blocks.forEach((b,i)=>{if(b.type==='activity'||b.type==='reasoning')boundary=i;});
 const work=blocks.slice(0,boundary+1),answer=blocks.slice(boundary+1).filter(b=>b.type==='text');
 const hasAnswer=answer.some(b=>b.content?.trim());
 return <article className={'message '+(assistant?'assistant':'user')+(live?' live':'')}>
 {assistant&&<img className="assistant-mark" data-copy-exclude="true" src="/central-mark.png" alt="" aria-hidden="true"/>}
 <div className="message-body">
 {!assistant?<div className="user-bubble"><AttachmentChips items={m.attachments} stored/><MessageMarkdown content={m.content} onError={notify}/></div>:<>
 <AttachmentChips items={m.attachments} stored/>
 {(work.length>0||live)&&<WorkPanel blocks={work} {...{activities,live,hasAnswer,notify,canUndo}} created={m.created} elapsed={s?.total_elapsed??s?.elapsed}/>}
 <div className="message-answer">{answer.map((block,index)=><div className="timeline-text" data-timeline-kind="text" key={index}><MessageMarkdown content={block.content} onError={notify}/></div>)}</div>
 </>}
 {!live&&<div className="message-top" data-copy-exclude="true"><strong>{assistant?'Central IA':'Você'}</strong>{timestamp}<div className="actions"><button aria-label="Copiar mensagem" title="Copiar mensagem" onClick={()=>copyText(m.content,notify)}><Copy size={17} aria-hidden="true"/><span>Copiar</span></button><button disabled={busy} aria-label="Editar mensagem" title="Editar mensagem" onClick={()=>onEdit(m)}><Pencil size={17} aria-hidden="true"/><span>Editar</span></button>{assistant&&last&&!busy&&<><button onClick={onRegenerate}><RotateCcw size={17}/>Regenerar</button><button onClick={onContinue}><ArrowRight size={17}/>Continuar</button></>}</div>
 {s?.finish_reason&&<details className="generation-details"><summary>Detalhes{s.elapsed!=null&&` (${s.elapsed.toFixed(2)} s)`}</summary><footer>{s.generated_tokens??'—'} tokens · {s.elapsed?.toFixed(2)} s de geração{s.compaction?.new&&` · compactação: ${s.compaction.elapsed.toFixed(2)} s`}{s.ttft!=null&&` · primeiro trecho em ${s.ttft.toFixed(2)} s`} · {s.tokens_per_second?.toFixed(2)??'—'} tokens/s no total{s.backend_timings?.predicted_per_second>0&&` · decodificação: ${s.backend_timings.predicted_per_second.toFixed(2)} tokens/s`}{s.usage?.prompt_tokens_details?.cached_tokens!=null&&` · ${s.usage.prompt_tokens_details.cached_tokens} tokens de prompt reutilizados`} · {s.finish_reason}{s.truncated&&' · Resposta possivelmente truncada'}</footer></details>}</div>}
 {live&&timestamp}
 </div></article>;
}
