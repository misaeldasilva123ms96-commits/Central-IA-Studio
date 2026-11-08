import React,{useEffect,useRef,useState,useCallback} from 'react';
import {createPortal} from 'react-dom';
import ConversationHistory from './ConversationHistory';
import {copyChatSelection} from './chatClipboard';
import MessageItem from './MessageItem';
import Composer from './Composer';
import Dialog from './Dialog';
import {ArrowDown,Download,SlidersHorizontal,Paperclip} from 'lucide-react';
import {api,generate,uploadFile} from './api';
export default function Chat({engine,profile,notify,onConfigure,onModels,onNavigate,historyHost,benchmark=false,onStats,defaultSystemPrompt,active=true,kind='chat',onBusy,otherBusy=false,toolsHost,extensions=[],onExtensions,automation=true}){
 const [conversations,setConversations]=useState([]),[cid,setCid]=useState(''),[messages,setMessages]=useState([]),[text,setText]=useState(''),[system,setSystem]=useState(defaultSystemPrompt),[query,setQuery]=useState(''),[busy,setBusy]=useState(false),[live,setLive]=useState(null),[limits,setLimits]=useState(null),[away,setAway]=useState(false),[editing,setEditing]=useState(null),[saving,setSaving]=useState(false),[historyLoading,setHistoryLoading]=useState(false),[historyError,setHistoryError]=useState(false),[historyVersion,setHistoryVersion]=useState(0);
 const [items,setItemsState]=useState([]),[agentMode,setAgentMode]=useState('build'),[access,setAccess]=useState('ask'),[internet,setInternet]=useState(false),[workspace,setWorkspace]=useState(''),[dragging,setDragging]=useState(false),[skills,setSkills]=useState([]),[autoSkills,setAutoSkills]=useState(true);
 const messageArea=useRef(),created=useRef(null),sending=useRef(false),follow=useRef(true),composer=useRef(),dragDepth=useRef(0),drafts=useRef({}),activeRef=useRef(active),itemsRef=useRef([]);
 const setItems=useCallback(value=>{const next=typeof value==='function'?value(itemsRef.current):value;itemsRef.current=next;setItemsState(next);},[]);
 activeRef.current=active;
 useEffect(()=>{setSkills(previous=>{const next=previous.filter(id=>extensions.some(i=>i.id===id&&i.installed&&i.enabled));return next.length===previous.length?previous:next;});},[extensions,skills.join('|')]);
 const listPath='/conversations?kind='+kind+'&q='+encodeURIComponent(query);
 useEffect(()=>{const copy=e=>copyChatSelection(e,messageArea.current);document.addEventListener('copy',copy);return()=>document.removeEventListener('copy',copy);},[]);
 const refresh=async()=>setConversations(await api(listPath));
 useEffect(()=>{let current=true;api(listPath).then(rows=>{if(current)setConversations(rows);}).catch(e=>{if(current)notify(e.message,true);});return()=>{current=false;};},[query,kind]);
 useEffect(()=>{
   let current=true;follow.current=true;setAway(false);setLimits(null);setHistoryError(false);
   if(cid&&created.current===cid){created.current=null;setHistoryLoading(false);return;}
   if(cid){
     setMessages([]);setHistoryLoading(true);
     Promise.all([api('/conversations/'+cid),api('/system-prompt/'+cid)]).then(([rows,prompt])=>{if(current){setMessages(rows);setSystem(prompt.content);const o=prompt.options||{};setAgentMode(o.agent_mode||'build');setAccess(o.access||'ask');setInternet(Boolean(o.internet));setWorkspace(o.workspace||'');setSkills(o.skills||[]);setAutoSkills(o.auto_skills!==false);}}).catch(e=>{if(current){setHistoryError(true);notify(e.message,true);}}).finally(()=>{if(current)setHistoryLoading(false);});
   }else{setMessages([]);setSystem(defaultSystemPrompt);setHistoryLoading(false);}
   return()=>{current=false;};
 },[cid,defaultSystemPrompt,historyVersion]);
 useEffect(()=>{const area=messageArea.current;if(active&&area&&follow.current)area.scrollTop=area.scrollHeight;},[live,messages,active]);
 const selectConversation=id=>{if(itemsRef.current.some(i=>i.uploading))return;drafts.current[cid||'new']={text,items};const draft=drafts.current[id]||{text:'',items:[]};setText(draft.text);setItems(draft.items);setCid(id);setHistoryVersion(n=>n+1);onNavigate?.();};
 const newConversation=()=>{if(sending.current||itemsRef.current.some(i=>i.uploading))return;drafts.current[cid||'new']={text,items};setCid('');setMessages([]);setText('');setItems([]);setAccess('ask');setInternet(false);setSkills([]);setAutoSkills(true);setSystem(defaultSystemPrompt);setLimits(null);follow.current=true;onNavigate?.();composer.current?.focus();};
 useEffect(()=>{const shortcut=e=>{if(!historyHost||document.querySelector('dialog[open]'))return;if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==='o'){e.preventDefault();newConversation();}};window.addEventListener('keydown',shortcut);return()=>window.removeEventListener('keydown',shortcut);},[historyHost,busy,text,items,defaultSystemPrompt]);
 const addFiles=async files=>{
   if(busy||otherBusy||historyLoading)return;
   if(itemsRef.current.length+files.length>6){notify('Você pode anexar até seis arquivos por mensagem.',true);return;}
   const pending=files.map(file=>({id:'upload-'+crypto.randomUUID(),name:file.name,uploading:true,file}));setItems(v=>[...v,...pending]);
   for(const item of pending){try{if(item.file.size>8*1024*1024)throw Error('Arquivo maior que 8 MiB.');const saved=await uploadFile(item.file);setItems(v=>v.map(a=>a.id===item.id?saved:a));}catch(e){setItems(v=>v.map(a=>a.id===item.id?{...a,uploading:false,error:e.message}:a));notify(e.message,true);}}
 };
 const create=async()=>{const title=(text||items[0]?.name||(kind==='agent'?'Nova tarefa':'Nova conversa'));const c=await api('/conversations',{title:Array.from(title).slice(0,60).join(''),kind});created.current=c.id;setCid(c.id);await refresh();return c.id;};
 const run=async(action='send')=>{
   if(sending.current||otherBusy||historyLoading||historyError||items.some(i=>i.uploading||i.error)||(action==='send'&&!text.trim()&&!items.length))return;
   sending.current=true;follow.current=true;setAway(false);
   const sentItems=action==='send'?items:[];
   if(action==='send'){setMessages(v=>[...v,{id:'pending-user-'+Date.now(),role:'user',content:text,attachments:sentItems,stats:{},created:Date.now()/1000}]);setText('');setItems([]);}
   setBusy(true);onBusy?.(kind);setLive({content:'',reasoning:'',activities:[],timeline:[],created:Date.now()/1000});setLimits(null);
   let currentId=cid;
   try{currentId=cid||await create();delete drafts.current[currentId];await generate({conversation:currentId,content:text,system,profile,action,benchmark,attachments:sentItems.map(a=>a.id),kind,agent_mode:agentMode,access,internet,workspace,skills,auto_skills:autoSkills},(event,data)=>{
     if(event==='limits')setLimits(data);
     if(event==='delta')setLive(v=>{const timeline=[...(v?.timeline||[])];for(const [type,content] of [['reasoning',data.reasoning],['text',data.content]]){if(!content)continue;const previous=timeline.at(-1);if(previous?.type===type)timeline[timeline.length-1]={...previous,content:previous.content+content};else timeline.push({type,content});}return {...v,content:(v?.content||'')+(data.content||''),reasoning:(v?.reasoning||'')+(data.reasoning||''),timeline};});
     if(event==='activity'){setLive(v=>{const known=v?.activities?.some(a=>a.id===data.id);return {...v,activities:known?v.activities.map(a=>a.id===data.id?data:a):[...(v?.activities||[]),data],timeline:known?v.timeline:[...(v?.timeline||[]),{type:'activity',id:data.id}]};});if(data.status==='approval'&&!activeRef.current)notify((kind==='agent'?'Agente':'Conversa')+' aguarda sua aprovação.');}
     if(event==='error')notify(data.detail,true);
     if(event==='done'){onStats?.(data);if(data.truncated)notify('A resposta atingiu o limite de saída. Você pode continuar a geração.');}
   });}
   catch(e){if(action==='send'){setText(text);setItems(sentItems);}notify(e.message,true);}
   finally{try{const [history,list]=await Promise.all([currentId?api('/conversations/'+currentId):Promise.resolve([]),api(listPath)]);setMessages(history);setConversations(list);}catch(e){notify(e.message,true);}finally{sending.current=false;setBusy(false);onBusy?.(null);setLive(null);}}
 };
 const saveEdit=async()=>{if(saving)return;setSaving(true);try{
   if(editing.type==='rename')await api('/conversations/'+editing.target.id,{title:editing.value},'PATCH');
   if(editing.type==='delete'){await api('/conversations/'+editing.target.id,{},'DELETE');if(cid===editing.target.id)newConversation();}
   if(editing.type==='message'){await api('/messages/'+editing.target.id,{content:editing.value},'PATCH');setMessages(await api('/conversations/'+cid));}
   await refresh();setEditing(null);
 }catch(e){notify(e.message,true);}finally{setSaving(false);}};
 return <div className={'chat-module '+(kind==='agent'?'agent-module':'')} onDragEnter={e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();dragDepth.current++;setDragging(true);}}} onDragOver={e=>{if(e.dataTransfer.types.includes('Files'))e.preventDefault();}} onDragLeave={e=>{if(e.dataTransfer.types.includes('Files')){dragDepth.current--;if(dragDepth.current<=0)setDragging(false);}}} onDrop={e=>{if(!e.dataTransfer.types.includes('Files'))return;e.preventDefault();dragDepth.current=0;setDragging(false);addFiles(Array.from(e.dataTransfer.files));}}>
 {dragging&&<div className="drop-overlay"><Paperclip size={36}/><strong>Solte arquivos ou imagens aqui</strong><span>Até 6 arquivos · 8 MiB por arquivo</span></div>}
 {historyHost&&createPortal(<ConversationHistory {...{conversations,cid,query,setQuery}} agent={kind==='agent'} busy={busy||items.some(i=>i.uploading)} onNew={newConversation} onSelect={selectConversation} onRename={c=>setEditing({type:'rename',target:c,value:c.title})} onDelete={c=>setEditing({type:'delete',target:c,value:''})}/>,historyHost)}
 {toolsHost&&createPortal(<div className="chat-tools"><details className="system"><summary><SlidersHorizontal size={14}/>Mensagem de sistema</summary><textarea aria-label="Mensagem de sistema" value={system} disabled={busy||historyLoading||historyError} onChange={e=>setSystem(e.target.value)} placeholder="Instruções para esta conversa (salvas ao gerar)"/></details>{cid&&<div className="export-actions"><a className="button" title="Exportar conversa em Markdown" href={'/api/conversations/'+cid+'/export?format=md'}><Download size={14}/>MD</a><a className="button" title="Exportar conversa em JSON" href={'/api/conversations/'+cid+'/export'}>JSON</a></div>}</div>,toolsHost)}
 <div className="messages" ref={messageArea} aria-live="polite" onScroll={e=>{const el=e.currentTarget;const atEnd=el.scrollHeight-el.scrollTop-el.clientHeight<70;follow.current=atEnd;setAway(!atEnd);}}><div className="message-column">{historyLoading&&<p role="status">Carregando conversa…</p>}{historyError&&<div className="history-error"><p>Não foi possível carregar a conversa.</p><button onClick={()=>setHistoryVersion(n=>n+1)}>Tentar novamente</button></div>}{messages.length===0&&!live&&!historyLoading&&!historyError&&<div className="empty-chat"><img src="/central-mark.png" alt=""/><h2>{kind==='agent'?'O que vamos construir?':'Como posso ajudar?'}</h2><p>{engine.connected?(kind==='agent'?'Escolha seu projeto e use Build para agir ou Plan para planejar.':'Seu modelo está pronto. Adicione arquivos ou comece uma conversa.'):'Escolha um modelo local para começar a conversar.'}</p>{!engine.connected&&<div className="empty-actions"><button className="primary" onClick={onModels}>Escolher modelo</button><button onClick={onConfigure}>Configurar conexão</button></div>}<div className="suggestions">{(kind==='agent'?['Revise o projeto','Planeje uma refatoração','Crie testes']:['Explique um conceito','Revise meu código','Planeje comigo']).map(s=><button key={s} onClick={()=>{setText(s==='Explique um conceito'?'Explique de forma simples: ':s==='Revise meu código'?'Revise este código e sugira melhorias:\n\n':s==='Planeje comigo'?'Ajude-me a planejar: ':s+' ');composer.current?.focus();}}>{s}</button>)}</div></div>}
 {messages.map((m,i)=><MessageItem key={m.id} message={m} {...{notify,busy}} last={i===messages.length-1} canUndo={kind==='agent'&&agentMode==='build'&&!busy&&!otherBusy} onEdit={m=>setEditing({type:'message',target:m,value:m.content})} onRegenerate={()=>run('regenerate')} onContinue={()=>run('continue')}/>)}
 {live&&<MessageItem message={{...live,role:'assistant'}} notify={notify} busy live/>}</div></div>
 <div className="composer-area">{away&&<button className="jump-latest" aria-label="Ir para a última mensagem" onClick={()=>{follow.current=true;messageArea.current.scrollTop=messageArea.current.scrollHeight;setAway(false);}}><ArrowDown size={18}/></button>}
 {limits&&<details className="limits"><summary>Contexto e limites{limits.warning&&' · Atenção'}</summary>Solicitado: {limits.requested_output} · Efetivo enviado: {limits.effective_output} · Contexto: {limits.occupied_context} / {limits.request_context} · Alocado: {limits.allocated_context}{limits.estimated_seconds!=null&&` · Estimativa para gerar TODO o limite: ${limits.estimated_seconds.toFixed(1)} s`}{limits.warning&&<p>{limits.warning}</p>}</details>}
 <Composer {...{text,setText,items,setItems,engine,kind,agentMode,setAgentMode,access,setAccess,internet,setInternet,workspace,setWorkspace,notify,extensions,skills,setSkills,onExtensions,autoSkills,setAutoSkills,automation}} inputRef={composer} busy={busy} disabled={historyLoading||historyError||otherBusy} onFiles={addFiles} onSend={()=>run()}/></div>
 {editing&&<Dialog title={editing.type==='rename'?'Renomear conversa':editing.type==='delete'?'Excluir conversa':'Editar mensagem'} onClose={()=>{if(!saving)setEditing(null);}}>{editing.type==='delete'?<p>Excluir “{editing.target.title}” e suas mensagens/anexos? Esta ação não pode ser desfeita.</p>:<label className="field"><span>{editing.type==='rename'?'Título':'Conteúdo'}</span>{editing.type==='rename'?<input autoFocus maxLength={200} value={editing.value} onChange={e=>setEditing({...editing,value:e.target.value})}/>:<textarea autoFocus value={editing.value} onChange={e=>setEditing({...editing,value:e.target.value})}/>}</label>}<div className="dialog-actions"><button disabled={saving} onClick={()=>setEditing(null)}>Cancelar</button><button className={editing.type==='delete'?'danger':'primary'} disabled={saving||(editing.type==='rename'&&!editing.value.trim())} onClick={saveEdit}>{editing.type==='delete'?'Excluir conversa':'Salvar'}</button></div></Dialog>}
 </div>;
}
