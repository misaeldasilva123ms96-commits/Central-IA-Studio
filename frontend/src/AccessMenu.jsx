import React,{useEffect,useRef,useState,useLayoutEffect} from 'react';
import {createPortal} from 'react-dom';
import {Hand,ShieldCheck,ShieldAlert,Check} from 'lucide-react';
export const accessOptions=[
 ['ask','Solicitar aprovação','Confirmar edições, comandos, acesso fora do projeto e uso da internet.',Hand],
 ['auto','Aprovar por mim','Permitir leitura, internet e edições comuns no projeto. Comandos e itens sensíveis pedem confirmação.',ShieldCheck],
 ['full','Acesso completo','Usar as ferramentas sem confirmação. No Agente Build, inclui comandos e arquivos fora do projeto, com suas permissões. Comandos também podem usar rede própria.',ShieldAlert]
];
export default function AccessMenu({value,onChange,disabled}){
 const [open,setOpen]=useState(false),[placement,setPlacement]=useState({}),ref=useRef(),popup=useRef();
 useLayoutEffect(()=>{if(!open)return;const position=()=>{const r=ref.current.getBoundingClientRect();const width=Math.min(470,innerWidth-24);setPlacement({position:'fixed',left:Math.max(12,Math.min(r.left,innerWidth-width-12)),right:'auto',bottom:Math.max(12,innerHeight-r.top+10),width,maxHeight:Math.max(100,r.top-24),overflowY:'auto'});};position();window.addEventListener('resize',position);return()=>window.removeEventListener('resize',position);},[open]);
 useEffect(()=>{const close=e=>{if(!ref.current?.contains(e.target)&&!popup.current?.contains(e.target))setOpen(false);};const key=e=>{if(e.key==='Escape')setOpen(false);};document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key);};},[]);
 const current=accessOptions.find(o=>o[0]===value)||accessOptions[0],Icon=current[3];
 return <div ref={ref} className={'access-control '+(value==='full'?'full-access':'')}><button type="button" className="access-trigger" disabled={disabled} aria-label={'Permissões: '+current[1]} aria-haspopup="menu" aria-expanded={open} onClick={()=>setOpen(!open)}><Icon size={16}/><span>{current[1]}</span></button>{open&&createPortal(<div ref={popup} style={placement} className="access-menu" role="menu" aria-label="Como as ações devem ser aprovadas?"><p>Como as ações devem ser aprovadas?</p>{accessOptions.map(([key,title,description,OptionIcon])=><button type="button" key={key} role="menuitemradio" aria-checked={key===value} onClick={()=>{onChange(key);setOpen(false);}}><OptionIcon size={18}/><div><strong>{title}</strong><small>{description}</small></div>{key===value&&<Check size={17}/>}</button>)}<small className="access-footnote">Plan permanece somente leitura. Comandos não têm isolamento do sistema.</small></div>,document.body)}</div>;
}
