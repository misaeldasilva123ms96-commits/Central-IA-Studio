import React from 'react';
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
export function Field({name,label,min,max,step,help,value,onChange,restart}){return <label className="field"><span>{label}{restart&&<small title="Exige reinício do motor gerenciado"> ↻</small>}</span><input type="number" min={min} max={max} step={step} value={value} onChange={e=>onChange(name,e.target.value===''?'':Number(e.target.value))}/>{help&&<small>{help}</small>}</label>}
export function Parameters({profile,setProfile,restart,model,notify,compact=false}){
 const change=(k,v)=>setProfile(p=>({...p,[k]:v}));
 const save=async()=>{try{await api('/profiles?model='+encodeURIComponent(model||'default'),profile,'PUT');notify('Parâmetros salvos para este modelo. Alterações marcadas com ↻ exigem reinício.');}catch(e){notify(e.message,true);}};
 return <><label className="field"><span>Modo</span><select value={profile.mode} onChange={e=>change('mode',e.target.value)}><option value="personalizado">Personalizado</option><option value="rapido">Rápido</option><option value="profundo">Profundo</option></select></label>
 <div className={compact?'':'parameter-grid'}>{fields.filter((_,i)=>!compact||i<3).map(([k,l,min,max,step,help])=><Field key={k} name={k} label={l} min={min} max={max} step={step} help={compact?null:help} value={profile[k]} onChange={change} restart={restart.includes(k)}/>)}</div>
 {!compact&&<div className="parameter-grid">
 <label className="field"><span>Tamanho do lote ↻</span><select value={profile.batch_size} onChange={e=>change('batch_size',+e.target.value)}>{[-1,16,32,64,128,256,512,1024,2048,4096].map(n=><option key={n}>{n}</option>)}</select></label>
 <label className="field"><span>Cache KV ↻</span><select value={profile.cache_kv} onChange={e=>change('cache_kv',e.target.value)}>{['f16','bf16','q8_0','q5_1','q4_0'].map(n=><option key={n}>{n}</option>)}</select></label>
 <label className="field"><span>Flash Attention ↻</span><select value={String(profile.flash_attention)} onChange={e=>change('flash_attention',e.target.value==='true')}><option value="true">Ativada</option><option value="false">Desativada</option></select></label>
 <label className="field"><span>Pensamento · personalizado</span><select value={profile.thinking} onChange={e=>change('thinking',e.target.value)}><option value="default">Padrão do modelo</option><option value="off">Desativar</option><option value="on">Ativar</option></select><small>Exige Jinja e template compatível. Rápido solicita desativação; Profundo solicita ativação.</small></label>
 <label className="field wide"><span>Arquivo de template Jinja ↻</span><input value={profile.template} placeholder="Vazio: template do GGUF / padrão do motor" onChange={e=>change('template',e.target.value)}/><small>Aplicado ao iniciar o motor gerenciado. Não substitui o template de um motor externo.</small></label>
 </div>}
 <button className="primary full" onClick={save}><Save size={17}/>Salvar parâmetros</button>
 {!compact&&<div className="actions"><button onClick={()=>download('perfil-central.json',profile)}><Download size={16}/>Exportar perfil</button><label className="button"><Upload size={16}/>Importar perfil<input type="file" accept=".json" hidden onChange={async e=>{try{const v=JSON.parse(await e.target.files[0].text());const saved=await api('/profiles?model='+encodeURIComponent(model||'default'),v,'PUT');setProfile(saved);notify('Perfil importado e salvo');}catch(err){notify(err.message,true);}}}/></label></div>}
 </>;
}
