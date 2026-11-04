import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Copy} from 'lucide-react';

export async function copyText(text,onError){
  try { await navigator.clipboard.writeText(text); }
  catch { onError?.('Não foi possível copiar. Selecione o texto e use Ctrl+C.',true); }
}

const CopyErrorContext=React.createContext(null);
function CodeBlock({children}){
  const onError=React.useContext(CopyErrorContext);
  const code=React.Children.toArray(children).find(React.isValidElement);
  const text=String(code?.props.children??'');
  const language=code?.props.className?.match(/language-([\w+-]+)/)?.[1]||'Código';
  return <div className="code-block"><div className="code-toolbar" data-copy-exclude="true"><span>{language}</span><button type="button" aria-label="Copiar código" onClick={()=>copyText(text,onError)}><Copy size={14} aria-hidden="true"/>Copiar</button></div><pre>{children}</pre></div>;
}
function Code({className,children}){return <code className={className}>{children}</code>;}
const components={pre:CodeBlock,code:Code};
function MessageMarkdown({content,onError}){
  return <CopyErrorContext.Provider value={onError}><Markdown remarkPlugins={[remarkGfm]} components={components}>{content}</Markdown></CopyErrorContext.Provider>;
}


export default React.memo(MessageMarkdown);
