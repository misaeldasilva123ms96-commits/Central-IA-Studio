import React,{useEffect,useState,useRef} from 'react';
import {Folder,ArrowUp,ArrowRight,Check} from 'lucide-react';
import {api} from './api';
import Dialog from './Dialog';
export default function FolderPicker({initial='',onSelect,onClose,title='Selecionar pasta de modelos',description='Navegue pelas pastas deste computador. Os arquivos permanecem no disco.'}){
 const [listing,setListing]=useState(null),[path,setPath]=useState(initial),[busy,setBusy]=useState(true),[error,setError]=useState('');
 const request=useRef(0);
 const load=async value=>{const id=++request.current;setBusy(true);setError('');try{const result=await api('/folders?path='+encodeURIComponent(value));if(id===request.current){setListing(result);setPath(result.path);}}catch(e){if(id===request.current)setError(e.message);}finally{if(id===request.current)setBusy(false);}};
 useEffect(()=>{load(initial);return()=>{request.current++;};},[]);
 return <Dialog title={title} onClose={onClose} className="folder-picker"><p>{description}</p>
 <form className="folder-location" onSubmit={e=>{e.preventDefault();load(path);}}><input disabled={busy} aria-label="Caminho da pasta" value={path} onChange={e=>setPath(e.target.value)}/><button disabled={busy} aria-label="Abrir caminho"><ArrowRight size={17}/></button></form>
 <div className="folder-roots"><button disabled={busy} onClick={()=>load('')}><Folder size={15}/>Pasta pessoal</button>{listing?.roots.map(r=><button disabled={busy} key={r.path} onClick={()=>load(r.path)}><Folder size={15}/>{r.name}</button>)}</div>
 {error&&<p role="alert" className="warning">{error}</p>}
 <div className="directory-list" role="region" aria-label={'Pastas em '+(listing?.path||'carregamento')} aria-busy={busy}>{listing?.parent&&<button disabled={busy} onClick={()=>load(listing.parent)}><ArrowUp size={17}/>Pasta acima</button>}{listing?.directories.map(d=><button key={d.path} disabled={busy} onClick={()=>load(d.path)}><Folder size={18}/>{d.name}</button>)}{busy&&<p>Carregando pastas…</p>}{listing&&!listing.directories.length&&!busy&&<p>Nenhuma subpasta. Você pode selecionar esta pasta.</p>}</div>
 <div className="dialog-actions"><button onClick={onClose}>Cancelar</button><button className="primary" disabled={busy||!listing||Boolean(error)} onClick={()=>onSelect(listing.path)}><Check size={17}/>Usar esta pasta</button></div></Dialog>;
}
