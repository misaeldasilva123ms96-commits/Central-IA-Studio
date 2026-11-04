import React,{useEffect,useState,useRef,useCallback} from 'react';
import {createRoot} from 'react-dom/client';
import {MessageSquare,Layers,SlidersHorizontal,ChartNoAxesCombined,Activity,Settings as SettingsIcon,Sun,Moon,Menu,X} from 'lucide-react';
import {api,bootstrap,bytes} from './api';
import {Parameters} from './Parameters';
import Chat from './Chat';
import {Settings,Models,Monitor,Benchmarks} from './Modules';
import './style.css';
const tabs=[['Conversas',MessageSquare],['Modelos',Layers],['Parâmetros',SlidersHorizontal],['Benchmarks',ChartNoAxesCombined],['Monitoramento',Activity],['Configurações',SettingsIcon]];
function App(){
 const [ready,setReady]=useState(false),[tab,setTab]=useState('Conversas'),[settings,setSettings]=useState({}),[profile,setProfile]=useState({}),[restart,setRestart]=useState([]),[engine,setEngine]=useState({}),[metrics,setMetrics]=useState(null),[selected,setSelected]=useState(''),[notice,setNotice]=useState(null),[light,setLight]=useState(localStorage.getItem('central-theme')==='light'),[menu,setMenu]=useState(false),[benchmark,setBenchmark]=useState(false),[stats,setStats]=useState(null),[defaultSystemPrompt,setDefaultSystemPrompt]=useState('');
 const contentArea=useRef();
 const notify=useCallback((text,error=false)=>setNotice({text,error}),[]);
 const refreshEngine=()=>api('/engine').then(setEngine).catch(e=>notify(e.message,true));
 useEffect(()=>{bootstrap().then(async b=>{setSettings(b.settings);setProfile(await api('/profiles'));setRestart(b.restart_fields);setDefaultSystemPrompt(b.default_system_prompt);setReady(true);if(b.warning)notify(b.warning,true);}).catch(e=>notify(e.message,true));},[]);
 useEffect(()=>{if(!ready)return;let alive=true;const poll=async()=>{try{const m=await api('/metrics');if(alive){setMetrics(m);setEngine(m.engine);}}catch(e){if(alive)notify(e.message,true);}};poll();const id=setInterval(poll,4000);return()=>{alive=false;clearInterval(id);};},[ready]);
 useEffect(()=>{document.documentElement.dataset.theme=light?'light':'dark';localStorage.setItem('central-theme',light?'light':'dark');},[light]);
 useEffect(()=>{window.scrollTo(0,0);if(contentArea.current)contentArea.current.scrollTop=0;},[tab]);
 if(!ready)return <div className="loading">{notice?.text||'Abrindo Central IA Studio…'}</div>;
 const changeTab=t=>{setTab(t);setMenu(false);};
 return <div className="app-shell"><aside className={'sidebar '+(menu?'open':'')}><a className="brand" href="#" onClick={e=>{e.preventDefault();changeTab('Conversas');}}><strong>Central IA</strong><span>Studio</span></a><nav>{tabs.map(([name,Icon])=><button key={name} className={tab===name?'active':''} onClick={()=>changeTab(name)}><Icon size={19}/>{name}</button>)}</nav><div className="sidebar-foot"><span className="dot"/>Local · 127.0.0.1<small>v0.2.1 · Prévia funcional</small></div></aside><main><header><div className="heading"><button className="mobile-menu" title="Abrir menu" onClick={()=>setMenu(!menu)}><Menu size={20}/></button><h1>{tab}</h1></div><div className="header-actions"><span className={'connection '+(engine.connected?'online':'')}><span className="dot"/>{engine.connected?'Conectado':'Desconectado'}</span><button title={light?'Ativar tema escuro':'Ativar tema claro'} onClick={()=>setLight(!light)}>{light?<Moon size={19}/>:<Sun size={19}/>}</button></div></header>
 {notice&&<div role="alert" className={'notice '+(notice.error?'error':'')}><span>{notice.text}</span><button title="Fechar aviso" onClick={()=>setNotice(null)}><X size={16}/></button></div>}
 <div className="workspace"><div className="main-content" ref={contentArea}><div className="chat-host" hidden={tab!=='Conversas'}><Chat active={tab==='Conversas'} defaultSystemPrompt={defaultSystemPrompt} engine={engine} profile={profile} notify={notify} onConfigure={()=>changeTab('Configurações')} benchmark={benchmark} onStats={setStats}/></div>
 {tab==='Modelos'&&<Models {...{settings,setSettings,profile,setProfile,selected,setSelected,engine,notify,refreshEngine}}/>}
 {tab==='Parâmetros'&&<section className="page"><h2>Controle de geração</h2><p>Perfil: {selected||'Padrão'} · ↻ exige reinício do motor gerenciado.</p>{engine.connected&&!engine.owned&&<p className="warning">Motor externo: configurações de inicialização precisam ser aplicadas no próprio KoboldCpp.</p>}<Parameters {...{profile,setProfile,restart,notify}} model={selected}/></section>}
 {tab==='Benchmarks'&&<Benchmarks notify={notify}/>}{tab==='Monitoramento'&&<Monitor metrics={metrics} notify={notify}/>}{tab==='Configurações'&&<Settings {...{settings,setSettings,notify,engine}}/>}</div>
 {tab==='Conversas'&&<aside className="inspector"><h2>Sessão</h2><label className="field"><span>Modelo</span><input readOnly value={engine.model||'Nenhum modelo'}/></label><Parameters compact {...{profile,setProfile,restart,notify}} model={selected}/><div className="session-stats"><label className="check"><input type="checkbox" checked={benchmark} onChange={e=>setBenchmark(e.target.checked)}/>Registrar benchmark</label><p>RAM disponível <strong>{bytes(metrics?.ram_available)}</strong></p><p>Tokens/s <strong>{stats?.tokens_per_second?.toFixed(2)??'—'}</strong></p>{stats&&<><p>Gerados <strong>{stats.generated_tokens??'Não informado'}</strong></p><p>Finalização <strong>{stats.finish_reason}</strong></p></>}<small>O thinking depende do modelo e do template. Parâmetros com ↻ são aplicados ao iniciar o motor.</small></div></aside>}</div></main></div>;
}
createRoot(document.getElementById('root')).render(<App/>);
