import React from 'react';
import {FileText,Image as ImageIcon,X,LoaderCircle,Download} from 'lucide-react';
export const attachmentUrl=a=>'/api/attachments/'+a.id+'/content';
export default function AttachmentChips({items,onRemove,disabled=false,stored=false}){
 if(!items?.length)return null;
 return <div className={'attachments '+(stored?'stored-attachments':'')}>{items.map(item=><div className={'attachment '+(item.error?'attachment-error':'')} key={item.id}>
 {item.kind==='image'&&!item.uploading?<img src={attachmentUrl(item)} alt={item.name}/>:item.uploading?<LoaderCircle size={20} className="spin"/>:item.kind==='image'?<ImageIcon size={20}/>:<FileText size={20}/>}
 <div><span title={item.name}>{item.name}</span><small>{item.uploading?'Enviando e lendo…':item.error||((item.size/1024).toFixed(0)+' KB')}{item.warning&&!item.uploading&&<span title={item.warning}> · {item.kind==='image'?'Imagem':'Ver nota'}</span>}</small>{item.warning&&<details><summary>Nota do anexo</summary><p>{item.warning}</p></details>}</div>
 {stored?<a href={attachmentUrl(item)} aria-label={'Baixar '+item.name} title="Baixar original"><Download size={15}/></a>:<button type="button" disabled={disabled} aria-label={'Remover '+item.name} onClick={()=>onRemove(item)}><X size={15}/></button>}
 </div>)}</div>;
}
