import React,{useEffect,useRef} from 'react';
import {X} from 'lucide-react';
export default function Dialog({title,onClose,children,className=''}){
 const ref=useRef();
 useEffect(()=>{const dialog=ref.current;dialog.showModal();return()=>dialog.close();},[]);
 return <dialog ref={ref} className={'dialog '+className} aria-label={title} onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target===ref.current){const r=ref.current.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}}>
 <div className="dialog-heading"><h2>{title}</h2><button aria-label={'Fechar '+title} onClick={onClose}><X size={19}/></button></div>{children}</dialog>;
}
