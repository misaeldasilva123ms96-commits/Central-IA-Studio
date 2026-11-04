import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import MessageMarkdown,{copyText} from './MessageMarkdown';
import {copyChatSelection} from './chatClipboard';
import ConversationHistory from './ConversationHistory';
import Dialog from './Dialog';
import {ArrowUp,ArrowDown,Square,Copy,Pencil,RotateCcw,ArrowRight,Download,SlidersHorizontal} from 'lucide-react';
import {api,generate} from './api';
export default function Chat({engine,profile,notify,onConfigure,onModels,onNavigate,historyHost,benchmark=false,onStats,defaultSystemPrompt,active=true}){
 const [conversations,setConversations]=useState([]),[cid,setCid]=useState(''),[messages,setMessages]=useState([]),[text,setText]=useState(''),[system,setSystem]=useState(defaultSystemPrompt),[query,setQuery]=useState(''),[busy,setBusy]=useState(false),[live,setLive]=useState(null),[limits,setLimits]=useState(null),[away,setAway]=useState(false),[editing,setEditing]=useState(null),[saving,setSaving]=useState(false),[historyLoading,setHistoryLoading]=useState(false),[historyError,setHistoryError]=useState(false),[historyVersion,setHistoryVersion]=useState(0);
 const bottom=useRef(),messageArea=useRef(),created=useRef(null),sending=useRef(false),follow=useRef(true),composer=useRef();
 useEffect(()=>{const copy=e=>copyChatSelection(e,messageArea.current);document.addEventListener('copy',copy);return()=>document.removeEventListener('copy',copy);},[]);
 const refresh=async()=>setConversations(await api('/conversations?q='+encodeURIComponent(query)));
 useEffect(()=>{let current=true;api('/conversations?q='+encodeURIComponent(query)).then(rows=>{if(current)setConversations(rows);}).catch(e=>{if(current)notify(e.message,true);});return()=>{current=false;};},[query]);
 useEffect(()=>{
   let current=true;follow.current=true;setAway(false);setLimits(null);setHistoryError(false);
   if(cid&&created.current===cid){created.current=null;setHistoryLoading(false);return;}
   if(cid){
     setMessages([]);setHistoryLoading(true);
     Promise.all([api('/conversations/'+cid),api('/system-prompt/'+cid)]).then(([rows,prompt])=>{if(current){setMessages(rows);setSystem(prompt.content);}}).catch(e=>{if(current){setHistoryError(true);notify(e.message,true);}}).finally(()=>{if(current)setHistoryLoading(false);});
   }else{setMessages([]);setSystem(defaultSystemPrompt);setHistoryLoading(false);}
   return()=>{current=false;};
 },[cid,defaultSystemPrompt,historyVersion]);
 useEffect(()=>{const area=messageArea.current;if(active&&area&&follow.current)area.scrollTop=area.scrollHeight;},[live,messages,active]);
 useEffect(()=>{const el=composer.current;if(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,140)+'px';}},[text]);
 const newConversation=()=>{if(sending.current)return;setCid('');setMessages([]);setText('');setSystem(defaultSystemPrompt);setLimits(null);follow.current=true;onNavigate?.();composer.current?.focus();};
 useEffect(()=>{const shortcut=e=>{if(document.querySelector('dialog[open]'))return;if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==='o'){e.preventDefault();newConversation();}};window.addEventListener('keydown',shortcut);return()=>window.removeEventListener('keydown',shortcut);},[busy,defaultSystemPrompt]);
 const create=async()=>{const c=await api('/conversations',{title:(text||'Nova conversa').slice(0,60)});created.current=c.id;setCid(c.id);await refresh();return c.id;};
 const run=async(action='send')=>{
   if(sending.current||historyLoading||historyError||(action==='send'&&!text.trim()))return;
   sending.current=true;follow.current=true;setAway(false);
   if(action==='send'){setMessages(v=>[...v,{id:'pending-user-'+Date.now(),role:'user',content:text,stats:{}}]);setText('');}
   setBusy(true);setLive({content:'',reasoning:''});setLimits(null);
   let currentId=cid;
   try{currentId=cid||await create();await generate({conversation:currentId,content:text,system,profile,action,benchmark},(kind,data)=>{
     if(kind==='limits')setLimits(data);
     if(kind==='delta')setLive(v=>({content:(v?.content||'')+data.content,reasoning:(v?.reasoning||'')+data.reasoning}));
     if(kind==='error')notify(data.detail,true);
     if(kind==='done'){onStats(data);if(data.truncated)notify('A resposta atingiu o limite de saída. Você pode continuar a geração.');}
   });}
   catch(e){if(action==='send')setText(text);notify(e.message,true);}
   finally{try{const [history,list]=await Promise.all([currentId?api('/conversations/'+currentId):Promise.resolve([]),api('/conversations?q='+encodeURIComponent(query))]);setMessages(history);setConversations(list);}catch(e){notify(e.message,true);}finally{sending.current=false;setBusy(false);setLive(null);composer.current?.focus();}}
 };
 const saveEdit=async()=>{if(saving)return;setSaving(true);try{
   if(editing.type==='rename')await api('/conversations/'+editing.target.id,{title:editing.value},'PATCH');
   if(editing.type==='delete'){await api('/conversations/'+editing.target.id,{},'DELETE');if(cid===editing.target.id)newConversation();}
   if(editing.type==='message'){await api('/messages/'+editing.target.id,{content:editing.value},'PATCH');setMessages(await api('/conversations/'+cid));}
   await refresh();setEditing(null);
 }catch(e){notify(e.message,true);}finally{setSaving(false);}};
 return <div className="chat-module">
 {historyHost&&createPortal(<ConversationHistory {...{conversations,cid,query,setQuery,busy}} onNew={newConversation} onSelect={id=>{setCid(id);setHistoryVersion(n=>n+1);onNavigate?.();}} onRename={c=>setEditing({type:'rename',target:c,value:c.title})} onDelete={c=>setEditing({type:'delete',target:c,value:''})}/>,historyHost)}
 <div className="chat-tools"><details className="system"><summary><SlidersHorizontal size={13}/>Mensagem de sistema</summary><textarea aria-label="Mensagem de sistema" value={system} disabled={busy||historyLoading||historyError} onChange={e=>setSystem(e.target.value)} placeholder="Instruções para esta conversa (salvas ao gerar)"/></details>{cid&&<div className="export-actions"><a className="button" title="Exportar conversa em Markdown" href={'/api/conversations/'+cid+'/export?format=md'}><Download size={14}/>MD</a><a className="button" title="Exportar conversa em JSON" href={'/api/conversations/'+cid+'/export'}>JSON</a></div>}</div>
 <div className="messages" ref={messageArea} aria-live="polite" onScroll={e=>{const el=e.currentTarget;const atEnd=el.scrollHeight-el.scrollTop-el.clientHeight<70;follow.current=atEnd;setAway(!atEnd);}}><div className="message-column">{historyLoading&&<p role="status">Carregando conversa…</p>}{historyError&&<div className="history-error"><p>Não foi possível carregar a conversa.</p><button onClick={()=>setHistoryVersion(n=>n+1)}>Tentar novamente</button></div>}{messages.length===0&&!live&&!historyLoading&&!historyError&&<div className="empty-chat"><h2>Como posso ajudar?</h2><p>{engine.connected?'Seu modelo está pronto. A conversa fica neste computador.':'Escolha um modelo local para começar a conversar.'}</p>{!engine.connected&&<div className="empty-actions"><button className="primary" onClick={onModels}>Escolher modelo</button><button onClick={onConfigure}>Configurar conexão</button></div>}<div className="suggestions">{['Explique um conceito','Revise meu código','Planeje comigo'].map(s=><button key={s} onClick={()=>{setText(s==='Explique um conceito'?'Explique de forma simples: ':s==='Revise meu código'?'Revise este código e sugira melhorias:\n\n':'Ajude-me a planejar: ');composer.current?.focus();}}>{s}</button>)}</div></div>}
 {messages.map(m=><article className={'message '+m.role} key={m.id}><div className="message-top"><strong>{m.role==='user'?'Você':'Central IA'}</strong><div className="actions" data-copy-exclude="true"><button aria-label="Copiar mensagem" title="Copiar mensagem" onClick={()=>copyText(m.content,notify)}><Copy size={15} aria-hidden="true"/></button><button disabled={busy} aria-label="Editar mensagem" title="Editar mensagem" onClick={()=>setEditing({type:'message',target:m,value:m.content})}><Pencil size={15} aria-hidden="true"/></button></div></div>{m.reasoning&&<details><summary>Pensamento retornado pelo motor</summary><div className="reasoning">{m.reasoning}</div></details>}<MessageMarkdown content={m.content} onError={notify}/>{m.stats?.finish_reason&&<details className="generation-details" data-copy-exclude="true"><summary>Detalhes da geração</summary><footer>{m.stats.generated_tokens??'—'} tokens · {m.stats.elapsed?.toFixed(2)} s de geração{m.stats.ttft!=null&&` · primeiro trecho em ${m.stats.ttft.toFixed(2)} s`} · {m.stats.tokens_per_second?.toFixed(2)??'—'} tokens/s no total{m.stats.backend_timings?.predicted_per_second>0&&` · decodificação: ${m.stats.backend_timings.predicted_per_second.toFixed(2)} tokens/s`}{m.stats.usage?.prompt_tokens_details?.cached_tokens!=null&&` · ${m.stats.usage.prompt_tokens_details.cached_tokens} tokens de prompt reutilizados`} · {m.stats.finish_reason}{m.stats.truncated&&' · Resposta possivelmente truncada'}</footer></details>}</article>)}
 {live&&<article className="message live"><div className="live-heading"><span className="dot"/>Central IA · gerando</div>{live.reasoning&&<details open><summary>Pensamento retornado pelo motor</summary><div className="reasoning">{live.reasoning}</div></details>}<MessageMarkdown content={live.content||'Aguardando o motor…'} onError={notify}/></article>}<div ref={bottom}/></div></div>
 <div className="composer-area">{away&&<button className="jump-latest" aria-label="Ir para a última mensagem" onClick={()=>{follow.current=true;messageArea.current.scrollTop=messageArea.current.scrollHeight;setAway(false);}}><ArrowDown size={18}/></button>}
 {limits&&<details className="limits"><summary>Contexto e limites{limits.warning&&' · Atenção'}</summary>Solicitado: {limits.requested_output} · Efetivo enviado: {limits.effective_output} · Contexto: {limits.occupied_context} / {limits.request_context} · Alocado: {limits.allocated_context}{limits.estimated_seconds!=null&&` · Estimativa para gerar TODO o limite: ${limits.estimated_seconds.toFixed(1)} s`}{limits.warning&&<p>{limits.warning}</p>}</details>}
 {messages.at(-1)?.role==='assistant'&&!busy&&<div className="reply-actions"><button onClick={()=>run('regenerate')}><RotateCcw size={14}/>Regenerar</button><button onClick={()=>run('continue')}><ArrowRight size={14}/>Continuar</button></div>}
 <form className="composer" onSubmit={e=>{e.preventDefault();run();}}><textarea ref={composer} rows={1} aria-label="Mensagem" placeholder="Pergunte ao Central IA…" value={text} disabled={busy||historyLoading||historyError} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();if(text.trim()&&engine.connected&&!busy)run();}}}/><div className="composer-bottom"><span>Local · Seus dados neste computador</span>{busy?<button type="button" aria-label="Interromper" title="Interromper" onClick={()=>api('/abort',{}).catch(e=>notify(e.message,true))}><Square size={17}/></button>:<button className="primary" aria-label="Enviar" title="Enviar (Enter) · Nova linha (Shift+Enter)" disabled={!text.trim()||!engine.connected||historyLoading||historyError} type="submit"><ArrowUp size={21}/></button>}</div></form><p className="composer-disclaimer">A IA pode cometer erros. Confira informações importantes.</p></div>
 {editing&&<Dialog title={editing.type==='rename'?'Renomear conversa':editing.type==='delete'?'Excluir conversa':'Editar mensagem'} onClose={()=>{if(!saving)setEditing(null);}}>{editing.type==='delete'?<p>Excluir “{editing.target.title}” e suas mensagens? Esta ação não pode ser desfeita.</p>:<label className="field"><span>{editing.type==='rename'?'Título':'Conteúdo'}</span>{editing.type==='rename'?<input autoFocus maxLength={200} value={editing.value} onChange={e=>setEditing({...editing,value:e.target.value})}/>:<textarea autoFocus value={editing.value} onChange={e=>setEditing({...editing,value:e.target.value})}/>}</label>}<div className="dialog-actions"><button disabled={saving} onClick={()=>setEditing(null)}>Cancelar</button><button className={editing.type==='delete'?'danger':'primary'} disabled={saving||(editing.type==='rename'&&!editing.value.trim())} onClick={saveEdit}>{editing.type==='delete'?'Excluir conversa':'Salvar'}</button></div></Dialog>}
 </div>;
}
