import React,{useEffect,useRef,useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Send,Square,Link,Copy,Pencil,RotateCcw,ArrowRight,Download,Plus,Search} from 'lucide-react';
import {api,generate} from './api';
function Code({className,children}){const text=String(children);return <span className="code-wrap"><code className={className}>{children}</code>{className&&<button className="copy-code" title="Copiar código" onClick={()=>navigator.clipboard.writeText(text)}><Copy size={14}/></button>}</span>;}
export default function Chat({engine,profile,notify,onConfigure,benchmark=false,onStats}){
 const [conversations,setConversations]=useState([]),[cid,setCid]=useState(''),[messages,setMessages]=useState([]),[text,setText]=useState(''),[system,setSystem]=useState(''),[query,setQuery]=useState(''),[busy,setBusy]=useState(false),[live,setLive]=useState(null),[limits,setLimits]=useState(null);
 const bottom=useRef();
 const refresh=async()=>setConversations(await api('/conversations?q='+encodeURIComponent(query)));
 useEffect(()=>{refresh().catch(e=>notify(e.message,true));},[query]);
 useEffect(()=>{if(cid){api('/conversations/'+cid).then(setMessages).catch(e=>notify(e.message,true));api('/system-prompt/'+cid).then(v=>setSystem(v.content));}else{setMessages([]);setSystem('');}},[cid]);
 useEffect(()=>{const area=bottom.current?.parentElement;if(area)area.scrollTop=area.scrollHeight;},[live,messages]);
 const create=async()=>{const c=await api('/conversations',{title:(text||'Nova conversa').slice(0,60)});setCid(c.id);await refresh();return c.id;};
 const run=async(action='send')=>{
   setBusy(true);setLive({content:'',reasoning:''});setLimits(null);
   let active=cid;
   try{active=cid||await create();await generate({conversation:active,content:text,system,profile,action,benchmark},(kind,data)=>{
     if(kind==='limits')setLimits(data);
     if(kind==='delta')setLive(v=>({content:(v?.content||'')+data.content,reasoning:(v?.reasoning||'')+data.reasoning}));
     if(kind==='error')notify(data.detail,true);
     if(kind==='done'){onStats(data);if(data.truncated)notify('A resposta atingiu o limite de saída. Você pode continuar a geração.');}
   });if(action==='send')setText('');}
   catch(e){notify(e.message,true);}
   finally{setBusy(false);setLive(null);if(active)setMessages(await api('/conversations/'+active));refresh();}
 };
 return <div className="chat-module">
 <div className="conversation-bar"><label className="search"><Search size={16}/><input aria-label="Pesquisar histórico" value={query} placeholder="Pesquisar histórico" onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Conversa" value={cid} disabled={busy} onChange={e=>setCid(e.target.value)}><option value="">Nova conversa</option>{conversations.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select><button title="Nova conversa" disabled={busy} onClick={()=>{setCid('');setMessages([]);setText('');}}><Plus size={16}/></button>{cid&&<><a className="button" href={'/api/conversations/'+cid+'/export?format=md'}><Download size={16}/>MD</a><a className="button" href={'/api/conversations/'+cid+'/export'}>JSON</a></>}</div>
 <details className="system"><summary>Mensagem de sistema</summary><textarea aria-label="Mensagem de sistema" value={system} disabled={busy} onChange={e=>setSystem(e.target.value)} placeholder="Instruções para esta conversa (salvas ao gerar)"/></details>
 <div className="messages" aria-live="polite">{messages.length===0&&!live&&<div className="empty-chat"><h2>Sua IA, no seu computador.</h2><p>Conecte o KoboldCpp e escolha um modelo para começar.</p><button className="primary" onClick={onConfigure}><Link size={18}/>Configurar conexão</button></div>}
 {messages.map(m=><article className={'message '+m.role} key={m.id}><div className="message-top"><strong>{m.role==='user'?'Você':'Assistente'}</strong><div className="actions"><button title="Copiar mensagem" onClick={()=>navigator.clipboard.writeText(m.content)}><Copy size={14}/></button><button disabled={busy} title="Editar mensagem" onClick={async()=>{const content=window.prompt('Editar mensagem',m.content);if(content!==null){await api('/messages/'+m.id,{content},'PATCH');setMessages(await api('/conversations/'+cid));}}}><Pencil size={14}/></button></div></div>{m.reasoning&&<details><summary>Pensamento retornado pelo motor</summary><div className="reasoning">{m.reasoning}</div></details>}<Markdown remarkPlugins={[remarkGfm]} components={{code:Code}}>{m.content}</Markdown>{m.stats?.finish_reason&&<footer>{m.stats.generated_tokens??'—'} tokens · {m.stats.elapsed?.toFixed(2)} s · {m.stats.tokens_per_second?.toFixed(2)??'—'} tokens/s · {m.stats.finish_reason}{m.stats.truncated&&' · Resposta possivelmente truncada'}</footer>}</article>)}
 {live&&<article className="message"><strong>Assistente · gerando</strong>{live.reasoning&&<details open><summary>Pensamento retornado pelo motor</summary><div className="reasoning">{live.reasoning}</div></details>}<Markdown components={{code:Code}}>{live.content||'Aguardando o motor…'}</Markdown></article>}<div ref={bottom}/></div>
 {limits&&<div className="limits">Solicitado: {limits.requested_output} · Efetivo enviado: {limits.effective_output} · Contexto: {limits.occupied_context} / {limits.request_context} · Alocado: {limits.allocated_context}{limits.estimated_seconds!=null&&` · Estimativa até o limite: ${limits.estimated_seconds.toFixed(1)} s`}{limits.warning&&<p>{limits.warning}</p>}</div>}
 {messages.at(-1)?.role==='assistant'&&!busy&&<div className="reply-actions"><button onClick={()=>run('regenerate')}><RotateCcw size={14}/>Regenerar</button><button onClick={()=>run('continue')}><ArrowRight size={14}/>Continuar</button></div>}
 <form className="composer" onSubmit={e=>{e.preventDefault();run();}}><textarea aria-label="Mensagem" placeholder="Escreva sua mensagem…" value={text} disabled={busy} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();if(text.trim()&&engine.connected&&!busy)run();}}}/>{busy?<button type="button" onClick={()=>api('/abort',{}).catch(e=>notify(e.message,true))}><Square size={16}/>Interromper</button>:<button className="primary" disabled={!text.trim()||!engine.connected} type="submit"><Send size={16}/>Enviar</button>}</form>
 </div>;
}
