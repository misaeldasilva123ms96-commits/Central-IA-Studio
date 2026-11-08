import React,{useState} from 'react';
import {Save, Download, Upload} from 'lucide-react';
import {api,download} from './api';
export const fields=[
['context','Contexto (tokens)',256,524288,1,'Memória alocada na inicialização. Mais contexto exige mais RAM.'],
['max_output','Saída máxima (tokens)',1,524288,1,'Limite solicitado. O espaço livre no contexto e o motor determinam o limite efetivo.'],
['temperature','Temperatura',0,5,.01,'Valores menores tornam a amostragem mais previsível.'],
['top_p','Top-P',0,1,.01,'Massa acumulada de probabilidade considerada.'],
['top_k','Top-K',0,10000,1,'Quantidade de candidatos; zero desativa o filtro.'],
['min_p','Min-P',0,1,.01,'Descarta candidatos pouco prováveis em relação ao mais provável.'],
['repetition_penalty','Penalidade de repetição',1,3,.01,'Um significa sem penalidade.'],
['threads','Threads CPU',1,256,1,'Comece com 2 no i5-7200U.'],
['blas_threads','Threads BLAS',1,256,1,'Threads para processamento do prompt.'],
['gpu_layers','Camadas na GPU',0,1000,1,'Use zero em máquina sem GPU dedicada.']];
export function Field({name,label,min,max,step,help,value,onChange,restart}){return <label className="field"><span>{label}{restart&&<small title="Exige reinício do motor gerenciado"> ↻</small>}</span><input type="number" aria-label={label} required min={min} max={max} step={step} value={value} onChange={e=>onChange(name,e.target.value===''?'':Number(e.target.value))}/>{help&&<small>{help}</small>}</label>}
function SessionParameters({profile,setProfile,restart,model,notify,disabled}){
 const [saving,setSaving]=useState(false),[error,setError]=useState('');
 const change=(name,value)=>{setError('');setProfile(p=>({...p,[name]:value}));};
 const renderFields=names=>fields.filter(f=>names.includes(f[0])).map(([name,label,min,max,step,help])=><Field key={name} {...{name,label,min,max,step,help}} value={profile[name]} onChange={change} restart={restart.includes(name)}/>);
 const save=async e=>{e.preventDefault();setSaving(true);setError('');try{const result=await api('/profiles?model='+encodeURIComponent(model||'default'),profile,'PUT');setProfile(result);notify('Perfil salvo para este modelo. Controles com ↻ exigem reinício do motor.');}catch(e){setError(e.message);}finally{setSaving(false);}};
 return <form className="session-parameters" onSubmit={save}><fieldset disabled={disabled||saving}>
 <section className="session-section"><h3>Resposta</h3><label className="field"><span>Modo</span><select value={profile.mode} onChange={e=>change('mode',e.target.value)}><option value="personalizado">Personalizado</option><option value="rapido">Rápido</option><option value="profundo">Profundo</option></select><small>{profile.mode==='rapido'?'Solicita pensamento desativado. O efeito depende do modelo e do template.':profile.mode==='profundo'?'Solicita pensamento ativado. Pode aumentar o tempo de resposta.':'Controle individual do pensamento e da amostragem.'}</small></label>
 <div className="session-grid">{renderFields(['max_output','temperature'])}</div>
 <label className="field"><span>Pensamento · personalizado</span><select disabled={profile.mode!=='personalizado'} value={profile.thinking} onChange={e=>change('thinking',e.target.value)}><option value="default">Padrão do modelo</option><option value="off">Desativar</option><option value="on">Ativar</option></select><small>O painel de trabalho mostra apenas o pensamento que o motor retornar.</small></label></section>
 <details className="session-section"><summary>Amostragem avançada</summary><p>Refine a seleção de tokens. Estes controles são enviados na próxima geração.</p><div className="session-grid">{renderFields(['top_p','top_k','min_p','repetition_penalty'])}</div></details>
 <details className="session-section"><summary>Contexto e desempenho</summary><p>Controles com ↻ só entram em vigor ao reiniciar o motor gerenciado. Em motores externos, ajuste a inicialização no próprio motor.</p><div className="session-grid">{renderFields(['context','threads','blas_threads','gpu_layers'])}
 <label className="field"><span>Tamanho do lote ↻</span><select value={profile.batch_size} onChange={e=>change('batch_size',Number(e.target.value))}>{[-1,16,32,64,128,256,512,1024,2048,4096].map(n=><option key={n} value={n}>{n===-1?'Automático':n}</option>)}</select></label>
 <label className="field"><span>Cache KV ↻</span><select value={profile.cache_kv} onChange={e=>change('cache_kv',e.target.value)}>{['f16','bf16','q8_0','q5_1','q4_0'].map(v=><option key={v}>{v}</option>)}</select></label>
 <label className="field"><span>Flash Attention ↻</span><select value={String(profile.flash_attention)} onChange={e=>change('flash_attention',e.target.value==='true')}><option value="true">Ativada</option><option value="false">Desativada</option></select></label>
 <label className="field"><span>Reutilizar prompt</span><select value={String(profile.prompt_cache??true)} onChange={e=>change('prompt_cache',e.target.value==='true')}><option value="true">Ativado</option><option value="false">Desativado</option></select></label>
 <Field name="cache_ram_mib" label="Cache adicional em RAM (MiB)" min={0} max={8192} step={1} value={profile.cache_ram_mib??256} onChange={change} restart help="Central Engine: snapshots de prompts, além do KV do contexto."/>
 </div></details>
 <details className="session-section"><summary>Visão e template</summary><label className="field"><span>Projetor de visão mmproj (GGUF) ↻</span><input value={profile.projector||''} onChange={e=>change('projector',e.target.value)} placeholder="Caminho do mmproj compatível"/><small>Modelo de visão e projetor devem ser compatíveis. Imagens usam contexto e RAM adicionais.</small></label><label className="field"><span>Arquivo de template Jinja ↻</span><input value={profile.template||''} onChange={e=>change('template',e.target.value)} placeholder="Vazio: padrão do modelo"/></label></details>
 {error&&<p className="warning" role="alert">{error}</p>}
 <div className="session-save"><small>{disabled?'Aguarde a tarefa terminar para alterar o perfil.':'Alterações valem para as próximas gerações; salve para reutilizar neste modelo.'}</small><button type="submit" className="primary full"><Save size={16}/>{saving?'Salvando…':'Salvar parâmetros'}</button><button type="button" className="full" onClick={()=>download('perfil-central.json',profile)}><Download size={15}/>Exportar perfil JSON</button></div>
 </fieldset></form>;
}
export function Parameters({profile,setProfile,restart,model,notify,compact=false,disabled=false}){
 if(compact)return <SessionParameters {...{profile,setProfile,restart,model,notify,disabled}}/>;
 const change=(k,v)=>setProfile(p=>({...p,[k]:v}));
 const save=async()=>{try{await api('/profiles?model='+encodeURIComponent(model||'default'),profile,'PUT');notify('Parâmetros salvos para este modelo. Alterações marcadas com ↻ exigem reinício.');}catch(e){notify(e.message,true);}};
 return <><label className="field"><span>Modo</span><select value={profile.mode} onChange={e=>change('mode',e.target.value)}><option value="personalizado">Personalizado</option><option value="rapido">Rápido</option><option value="profundo">Profundo</option></select></label>
 <div className={compact?'':'parameter-grid'}>{fields.filter((_,i)=>!compact||i<3).map(([k,l,min,max,step,help])=><Field key={k} name={k} label={l} min={min} max={max} step={step} help={compact?null:help} value={profile[k]} onChange={change} restart={restart.includes(k)}/>)}</div>
 {!compact&&<div className="parameter-grid">
 <label className="field"><span>Tamanho do lote ↻</span><select value={profile.batch_size} onChange={e=>change('batch_size',+e.target.value)}>{[-1,16,32,64,128,256,512,1024,2048,4096].map(n=><option key={n}>{n}</option>)}</select></label>
 <label className="field"><span>Cache KV ↻</span><select value={profile.cache_kv} onChange={e=>change('cache_kv',e.target.value)}>{['f16','bf16','q8_0','q5_1','q4_0'].map(n=><option key={n}>{n}</option>)}</select></label>
 <label className="field"><span>Flash Attention ↻</span><select value={String(profile.flash_attention)} onChange={e=>change('flash_attention',e.target.value==='true')}><option value="true">Ativada</option><option value="false">Desativada</option></select></label>
 <label className="field"><span>Pensamento · personalizado</span><select value={profile.thinking} onChange={e=>change('thinking',e.target.value)}><option value="default">Padrão do modelo</option><option value="off">Desativar</option><option value="on">Ativar</option></select><small>Exige Jinja e template compatível. Rápido solicita desativação; Profundo solicita ativação.</small></label>
 <label className="field"><span>Reutilizar prompt · Central Engine</span><select value={String(profile.prompt_cache??true)} onChange={e=>change('prompt_cache',e.target.value==='true')}><option value="true">Ativado</option><option value="false">Desativado</option></select><small>Reaproveita prefixos já processados. Não altera o limite de contexto.</small></label>
 <Field name="cache_ram_mib" label="Cache adicional em RAM (MiB)" min={0} max={8192} step={1} value={profile.cache_ram_mib??256} onChange={change} restart help="Central Engine: teto de snapshots de prompts. Zero desativa snapshots extras; o KV do contexto continua alocado."/>
 <label className="field wide"><span>Projetor de visão mmproj (GGUF) ↻</span><input value={profile.projector||''} placeholder="Caminho do mmproj compatível com o modelo de visão" onChange={e=>change('projector',e.target.value)}/><small>Central Engine CPU: requer modelo de visão e projetor correspondente. Nada é baixado automaticamente. Deixe vazio para texto. Imagens usam RAM adicional.</small></label>
 <label className="field wide"><span>Arquivo de template Jinja ↻</span><input value={profile.template} placeholder="Vazio: template do GGUF / padrão do motor" onChange={e=>change('template',e.target.value)}/><small>Aplicado ao iniciar o motor gerenciado. Não substitui o template de um motor externo.</small></label>
 </div>}
 <button className="primary full" onClick={save}><Save size={17}/>Salvar parâmetros</button>
 {!compact&&<div className="actions"><button onClick={()=>download('perfil-central.json',profile)}><Download size={16}/>Exportar perfil</button><label className="button"><Upload size={16}/>Importar perfil<input type="file" accept=".json" hidden onChange={async e=>{try{const v=JSON.parse(await e.target.files[0].text());const saved=await api('/profiles?model='+encodeURIComponent(model||'default'),v,'PUT');setProfile(saved);notify('Perfil importado e salvo');}catch(err){notify(err.message,true);}}}/></label></div>}
 </>;
}
