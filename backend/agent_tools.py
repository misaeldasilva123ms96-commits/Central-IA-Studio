"""Explicit Plan/Build tool policy and per-action consent, independent of model output."""
import asyncio
import difflib
import hashlib
import json
import os
import re
import signal
import time
import uuid
from pathlib import Path
import psutil
from .web import fetch_page,search_web
from .utility_tools import utility_definitions,execute as execute_utility,NAMES as UTILITY_NAMES

SENSITIVE={'.env','.git','.ssh','.aws','.azure','.kube','credentials','id_rsa','id_ed25519','secrets.json'}


def tool(name,description,properties,required):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}}


def definitions(kind,mode,workspace,internet,attachments=False):
    result=[]
    if attachments:
        result += [tool('read_attachment','Ler um trecho de documento já anexado nesta conversa. Offset em caracteres, começando em zero.',{'id':{'type':'string'},'offset':{'type':'integer','minimum':0}},['id']),
                   tool('search_attachment','Buscar uma palavra/frase literal em documento anexado, retornando trechos relevantes.',{'id':{'type':'string'},'query':{'type':'string'}},['id','query'])]
    if internet:
        result += [tool('web_search','Pesquisar fontes públicas na internet.',{'query':{'type':'string'}},['query']),
                   tool('web_fetch','Ler uma página pública HTTP(S), sem executar scripts.',{'url':{'type':'string'}},['url'])]
    if kind=='agent' and workspace:
        result += [tool('list_files','Listar arquivos e pastas do projeto; não é recursivo.',{'path':{'type':'string'}},['path']),
                   tool('read_file','Ler um arquivo de texto local (até 128 KiB).',{'path':{'type':'string'},'start_line':{'type':'integer','minimum':1},'end_line':{'type':'integer','minimum':1}},['path'])]
        if mode=='build':
            result += [tool('write_file','Criar ou substituir arquivo de texto. Informe o conteúdo completo.',{'path':{'type':'string'},'content':{'type':'string'}},['path','content']),
                       tool('run_command','Executar um programa no projeto; envie argv em lista, sem shell implícito. Limite 60 s.',{'argv':{'type':'array','items':{'type':'string'}}},['argv'])]
    return result+utility_definitions()


class ApprovalBroker:
    def __init__(self):self.pending={}
    def create(self,proposal):
        aid=uuid.uuid4().hex;event=asyncio.Event()
        self.pending[aid]={'proposal':proposal,'event':event,'decision':None}
        return aid
    def decide(self,aid,allow):
        row=self.pending.get(aid)
        if row is None or row['event'].is_set():raise ValueError('Esta solicitação expirou ou já foi respondida.')
        row['decision']=bool(allow);row['event'].set()
    async def wait(self,aid,abort):
        row=self.pending[aid]
        ready=asyncio.create_task(row['event'].wait());cancel=asyncio.create_task(abort.wait())
        try:
            done,_=await asyncio.wait([ready,cancel],timeout=180,return_when=asyncio.FIRST_COMPLETED)
            return ready in done and cancel not in done and row['decision'] is True
        finally:
            ready.cancel();cancel.cancel();await asyncio.gather(ready,cancel,return_exceptions=True)
            self.pending.pop(aid,None)


def resolve_path(workspace,value):
    if not isinstance(value,str) or not value or len(value)>4096 or any(ord(c)<32 for c in value):
        raise ValueError('Caminho de arquivo inválido.')
    root=Path(workspace).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('Escolha uma pasta de projeto existente.')
    candidate=Path(value).expanduser()
    target=(candidate if candidate.is_absolute() else root/candidate).resolve()
    outside=not target.is_relative_to(root)
    system_roots=[Path(v).resolve() for v in [os.environ.get('WINDIR'),os.environ.get('PROGRAMFILES'),os.environ.get('PROGRAMFILES(X86)')] if v] if os.name=='nt' else [Path(v) for v in ['/etc','/usr','/bin','/sbin','/boot','/sys','/proc','/dev']]
    sensitive=any(target.is_relative_to(root) for root in system_roots) or any(part.lower() in SENSITIVE or part.lower().endswith(('.pem','.key','.pfx','.p12')) or part.lower().startswith('.env') for part in target.parts)
    return root,target,outside,sensitive


def prepare_action(name,args,kind,mode,workspace,internet,access,attachment_ids=None):
    if name not in [t['function']['name'] for t in definitions(kind,mode,workspace,internet,bool(attachment_ids))]:
        raise ValueError('Ferramenta não disponível neste modo. Plan não edita arquivos nem executa comandos.')
    if not isinstance(args,dict):raise ValueError('Argumentos da ferramenta devem ser um objeto JSON.')
    allowed={t['function']['name']:t['function']['parameters'] for t in definitions(kind,mode,workspace,internet,bool(attachment_ids))}[name]
    if not set(allowed['required']).issubset(args) or not set(args).issubset(allowed['properties']):raise ValueError('Argumentos ausentes ou desconhecidos.')
    action={'name':name,'arguments':args,'approval':access=='ask','summary':'','preview':''}
    if name in ['read_attachment','search_attachment']:
        if args.get('id') not in (attachment_ids or []):raise ValueError('Anexo não disponível nesta conversa.')
        action.update(approval=False,summary=args['id'])
    elif name in ['web_search','web_fetch']:
        value=args['query' if name=='web_search' else 'url']
        if not isinstance(value,str) or not value or len(value)>(400 if name=='web_search' else 2048):raise ValueError('Busca ou URL inválida.')
        action.update(summary=value,approval=False)
        action['preview']='Esta busca ou URL será enviada a serviços públicos de pesquisa/leitura (Bing, DuckDuckGo ou Jina Reader, quando necessário). Anexos não são enviados automaticamente.'
    elif name in UTILITY_NAMES:
        action.update(approval=False,summary='Ferramenta local de cálculo/dados')
    elif name=='run_command':
        argv=args['argv']
        if not isinstance(argv,list) or not argv or len(argv)>32 or any(not isinstance(x,str) or not x or '\x00' in x for x in argv) or sum(map(len,argv))>16000:
            raise ValueError('Comando deve ser uma lista argv não vazia, até 16.000 caracteres.')
        root=Path(workspace).expanduser().resolve(strict=True)
        if not root.is_dir():raise ValueError('Escolha um projeto antes de executar comandos.')
        action.update(summary=json.dumps(argv,ensure_ascii=False),cwd=str(root),approval=access!='full',
                      preview='Executado nesta pasta com as permissões do seu usuário. A pasta de trabalho não é uma sandbox; o programa pode acessar arquivos e rede com suas permissões.')
    else:
        root,target,outside,sensitive=resolve_path(workspace,args['path'])
        action.update(path=str(target),summary=str(target),outside=outside,
                      approval=access!='full' and (outside or sensitive or (name=='write_file' and access=='ask')))
        if name=='write_file':
            content=args['content']
            if not isinstance(content,str) or len(content.encode('utf-8'))>128*1024:raise ValueError('Edição limitada a 128 KiB de texto UTF-8.')
            if target.exists() and not target.is_file():raise ValueError('O destino não é um arquivo comum.')
            if target.is_file() and target.stat().st_size>128*1024:raise ValueError('Arquivo existente excede 128 KiB; use uma ferramenta externa.')
            if target.is_file():
                with target.open('rb') as stream:previous=stream.read(128*1024+1)
                if len(previous)>128*1024:raise ValueError('Arquivo existente excede 128 KiB.')
            else:previous=None
            before=previous.decode('utf-8') if previous is not None else ''
            action.update(previous=previous,expected=hashlib.sha256(previous).hexdigest() if previous is not None else None,
                          preview=''.join(difflib.unified_diff(before.splitlines(True),content.splitlines(True),fromfile=str(target),tofile=str(target))))
    return action


def public_action(action):
    return {key:action[key] for key in ['name','arguments','summary','preview','cwd','path','outside'] if key in action}


async def run_command(argv,cwd,abort):
    flags={'creationflags':0x00000200} if os.name=='nt' else {'start_new_session':True}
    process=await asyncio.create_subprocess_exec(*argv,cwd=cwd,stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,**flags)
    async def stop():
        if os.name=='nt':
            if process.returncode is None:
                killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(process.pid),'/T','/F',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                await killer.wait()
        else:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if process.returncode is None:
            try:process.kill()
            except ProcessLookupError:pass
        try:await asyncio.wait_for(process.wait(),3)
        except TimeoutError:pass
    async def output():
        data=bytearray()
        while True:
            chunk=await process.stdout.read(4096)
            if not chunk:break
            data.extend(chunk)
            if len(data)>65536:
                await stop();return data[:65536].decode('utf-8',errors='replace')+'\n[Saída limitada a 64 KiB; processo interrompido.]'
        await process.wait()
        return data.decode('utf-8',errors='replace')
    task=asyncio.create_task(output());cancel=asyncio.create_task(abort.wait())
    try:
        done,_=await asyncio.wait([task,cancel],timeout=60,return_when=asyncio.FIRST_COMPLETED)
        if cancel in done:raise ValueError('Comando interrompido pelo usuário.')
        if task not in done:raise ValueError('Comando excedeu 60 segundos e foi interrompido.')
        return {'argv':argv,'cwd':cwd,'exit_code':process.returncode,'output':task.result()}
    finally:
        await stop();task.cancel();cancel.cancel();await asyncio.gather(task,cancel,return_exceptions=True)


async def execute_action(action,store,cid,abort):
    if abort.is_set():raise ValueError('Tarefa interrompida.')
    name=action['name'];args=action['arguments']
    if name in UTILITY_NAMES:return execute_utility(name,args)
    if name in ['read_attachment','search_attachment']:
        with store.db() as db:
            row=db.execute('SELECT a.name,a.text,a.warning FROM attachments a JOIN message_attachments l ON l.attachment_id=a.id JOIN messages m ON m.id=l.message_id WHERE a.id=? AND m.conversation=?',(args['id'],cid)).fetchone()
        if row is None:raise ValueError('Anexo não encontrado nesta conversa.')
        if name=='read_attachment':
            offset=args.get('offset',0)
            if not isinstance(offset,int) or isinstance(offset,bool) or offset<0:raise ValueError('Offset deve ser inteiro maior ou igual a zero.')
            return {'name':row['name'],'offset':offset,'total_characters':len(row['text']),'text':row['text'][offset:offset+4000],'warning':row['warning']}
        query=args['query']
        if not isinstance(query,str) or not 1<=len(query)<=200:raise ValueError('Busca no anexo deve ter entre 1 e 200 caracteres.')
        matches=[]
        for found in re.finditer(re.escape(query),row['text'],re.IGNORECASE):
            start=max(0,found.start()-250);end=min(len(row['text']),found.end()+450)
            matches.append({'offset':start,'text':row['text'][start:end]})
            if len(matches)>=5:break
        return {'name':row['name'],'query':query,'matches':matches,'warning':row['warning']}
    if name in ['web_search','web_fetch']:
        task=asyncio.create_task(search_web(args['query']) if name=='web_search' else fetch_page(args['url']))
        cancel=asyncio.create_task(abort.wait())
        try:
            done,_=await asyncio.wait([task,cancel],return_when=asyncio.FIRST_COMPLETED)
            if cancel in done:raise ValueError('Acesso à internet interrompido pelo usuário.')
            return task.result()
        finally:
            task.cancel();cancel.cancel();await asyncio.gather(task,cancel,return_exceptions=True)
    if name=='run_command':
        cwd=Path(action['cwd'])
        if not cwd.is_dir() or cwd.resolve()!=cwd:raise ValueError('A pasta do comando mudou após a proposta.')
        return await run_command(args['argv'],action['cwd'],abort)
    target=Path(action['path'])
    if str(target.resolve())!=str(target):raise ValueError('O caminho mudou após a proposta. Ação cancelada.')
    if name=='list_files':
        if not target.is_dir():raise ValueError('Pasta não encontrada.')
        rows=[]
        for entry in target.iterdir():
            rows.append({'name':entry.name,'directory':entry.is_dir()})
            if len(rows)>=300:break
        return {'path':str(target),'entries':sorted(rows,key=lambda x:(not x['directory'],x['name'].lower())),'limited':len(rows)>=300}
    if name=='read_file':
        if not target.is_file():raise ValueError('Arquivo não encontrado.')
        with target.open('rb') as stream:data=stream.read(128*1024+1)
        if len(data)>128*1024:raise ValueError('Arquivo maior que 128 KiB; peça um arquivo menor.')
        lines=data.decode('utf-8').splitlines(True)
        start=args.get('start_line',1);end=args.get('end_line',start+199)
        if not isinstance(start,int) or isinstance(start,bool) or not isinstance(end,int) or isinstance(end,bool) or start<1 or end<start or end-start>=200:
            raise ValueError('Use um intervalo de até 200 linhas, começando em 1.')
        return {'path':str(target),'start_line':start,'end_line':min(end,len(lines)),'total_lines':len(lines),'content':''.join(lines[start-1:end])}
    if name=='write_file':
        if target.is_file():
            with target.open('rb') as stream:current=stream.read(128*1024+1)
            if len(current)>128*1024:raise ValueError('O arquivo mudou e agora excede o limite de edição.')
        else:current=None
        digest=hashlib.sha256(current).hexdigest() if current is not None else None
        if digest!=action['expected']:raise ValueError('O arquivo mudou após a proposta. Leia novamente antes de editar.')
        content=args['content'].encode('utf-8');rid=uuid.uuid4().hex
        with store.db() as db:
            db.execute('INSERT INTO agent_revisions(id,conversation,path,previous,after_sha,created) VALUES (?,?,?,?,?,?)',(rid,cid,str(target),current,hashlib.sha256(content).hexdigest(),time.time()))
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name('.central-'+uuid.uuid4().hex+'.tmp')
        try:
            temporary.write_bytes(content)
            if target.is_file():os.chmod(temporary,target.stat().st_mode & 0o777)
            os.replace(temporary,target)
        finally:temporary.unlink(missing_ok=True)
        return {'path':str(target),'written_bytes':len(content),'revision':rid,'previous_saved':True}
    raise ValueError('Ferramenta desconhecida.')
