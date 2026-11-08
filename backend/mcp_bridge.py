"""MCP client sessions owned by dedicated tasks (stdio and Streamable HTTP)."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
import uuid
import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

REF=re.compile(r'\$(?:\{(?:env:)?([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))')


def validate_config(config,imported=False):
    if not isinstance(config,dict):raise ValueError('Configuração MCP precisa ser um objeto.')
    transport=config.get('transport') or config.get('type') or ('stdio' if config.get('command') else 'http')
    if not isinstance(transport,str):raise ValueError('Transporte MCP inválido.')
    transport={'streamable-http':'http','streamable_http':'http'}.get(transport,transport)
    if transport not in ['stdio','http']:raise ValueError('Transporte suportado: STDIO ou Streamable HTTP.')
    result={'transport':transport}
    if transport=='stdio':
        command=config.get('command');args=config.get('args',[])
        if not isinstance(command,str) or not command or len(command)>4096 or any(ord(c)<32 for c in command):raise ValueError('Informe um programa MCP válido.')
        if not isinstance(args,list) or len(args)>64 or any(not isinstance(a,str) or len(a)>4096 or '\x00' in a for a in args):raise ValueError('Argumentos MCP inválidos.')
        result.update(command=command,args=args)
    else:
        url=config.get('url','')
        if not isinstance(url,str) or len(url)>2048:raise ValueError('URL MCP inválida.')
        try:parsed=urlsplit(url);port=parsed.port
        except ValueError as e:raise ValueError('URL MCP inválida.') from e
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.scheme not in ['https','http']:raise ValueError('Use URL HTTP(S) sem usuário, senha ou fragmento.')
        if parsed.scheme=='http' and parsed.hostname not in ['localhost','127.0.0.1','::1']:raise ValueError('HTTP sem TLS é permitido apenas para servidor neste computador.')
        result['url']=url
    env=config.get('env',{});headers=config.get('headers',{})
    if not isinstance(env,dict) or not isinstance(headers,dict) or len(env)>32 or len(headers)>16:raise ValueError('Variáveis/cabeçalhos MCP inválidos.')
    result['env']={};result['headers']={}
    for target,values in [('env',env),('headers',headers)]:
        for key,value in values.items():
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}',key) or not isinstance(value,str) or len(value)>4096 or '\r' in value or '\n' in value:raise ValueError('Variável ou cabeçalho MCP inválido.')
            if key.lower() in ['host','content-length','cookie','set-cookie']:raise ValueError('Cabeçalho reservado não permitido.')
            # Imported configuration must refer to environment variables, not embed credentials.
            if not REF.search(value):raise ValueError('Use ${NOME_DA_VARIAVEL} em env/headers; credenciais literais são informadas só ao conectar.')
            result[target][key]=value
    return result


def tool_alias(server_id,name):return 'mcp_'+server_id[:12]+'_'+hashlib.sha256(name.encode()).hexdigest()[:16]


def checked_tools(tools):
    if len(tools)>256:raise ValueError('Servidor oferece mais de 256 ferramentas; use uma configuração menor.')
    result=[]
    for tool in tools:
        item=tool.model_dump(mode='json',exclude_none=True);schema=item.get('inputSchema') or {}
        raw=json.dumps(schema)
        if len(raw)>16000:raise ValueError('Esquema de ferramenta MCP excede 16.000 caracteres.')
        def walk(value,depth=0):
            if depth>24:raise ValueError('Esquema MCP profundo demais.')
            if isinstance(value,dict):
                for key,child in value.items():
                    if key in ['$ref','$dynamicRef','$recursiveRef'] and (not isinstance(child,str) or not child.startswith('#')):raise ValueError('Referências externas em esquemas MCP não são aceitas.')
                    walk(child,depth+1)
            elif isinstance(value,list):
                for child in value:walk(child,depth+1)
        walk(schema);Draft202012Validator.check_schema(schema)
        if schema.get('type')!='object':raise ValueError('Ferramenta MCP precisa de argumentos do tipo objeto.')
        if not isinstance(item['name'],str) or not 1<=len(item['name'])<=128:raise ValueError('Nome de ferramenta MCP inválido.')
        result.append({'name':item['name'],'description':str(item.get('description',''))[:2000],'inputSchema':schema,'annotations':{'readOnlyHint':bool(item.get('annotations',{}).get('readOnlyHint'))}})
    if len({i['name'] for i in result})!=len(result):raise ValueError('Nomes de ferramenta duplicados.')
    return result


class MCPBridge:
    def __init__(self,store):self.store=store;self.connections={};self.credentials={}

    def servers(self):
        with self.store.db() as db:rows=[dict(r) for r in db.execute('SELECT * FROM mcp_servers ORDER BY name')]
        for row in rows:
            for field in ['config','selected','tools']:row[field]=json.loads(row[field])
            task=self.connections.get(row['id'],{}).get('task')
            row['connected']=bool(task and not task.done())
        return rows

    def save(self,name,config):
        if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise ValueError('Nome MCP inválido.')
        config=validate_config(config);key=uuid.uuid4().hex
        with self.store.db() as db:db.execute('INSERT INTO mcp_servers(id,name,config) VALUES (?,?,?)',(key,name.strip(),json.dumps(config)))
        return key

    def _active(self,server):
        if not server['package']:return True
        from .extensions import catalog
        return any(i['id']==server['package'] and i['installed'] and i['enabled'] for i in catalog(self.store))

    async def connect(self,key,credentials=None):
        server=next((s for s in self.servers() if s['id']==key),None)
        if not server:raise ValueError('Conexão MCP não encontrada.')
        if not self._active(server):raise ValueError('Ative o plugin antes de conectar seu servidor.')
        await self.disconnect(key)
        if credentials is not None:self.credentials[key]=credentials
        entry={'queue':asyncio.Queue(),'ready':asyncio.get_running_loop().create_future()}
        self.connections[key]=entry;entry['task']=asyncio.create_task(self._serve(server,entry))
        try:await asyncio.wait_for(asyncio.shield(entry['ready']),25)
        except TimeoutError as error:
            await self.disconnect(key)
            raise ValueError('Tempo de conexão MCP esgotado.') from error
        except BaseException:
            await self.disconnect(key)
            raise
        return self.servers()

    async def disconnect(self,key):
        entry=self.connections.pop(key,None)
        if entry:
            entry['task'].cancel()
            await asyncio.gather(entry['task'],return_exceptions=True)
            while not entry['queue'].empty():
                job=entry['queue'].get_nowait()
                if not job['future'].done():job['future'].set_exception(ValueError('Conexão MCP encerrada.'))
        self.credentials.pop(key,None)

    async def close(self):
        for key in list(self.connections):await self.disconnect(key)

    async def _serve(self,server,entry):
        cfg=server['config'];secrets=self.credentials.get(server['id'],{});root=None
        def resolve(value):
            def replace(match):
                variable=match[1] or match[2]
                if variable in ['PLUGIN_ROOT','CLAUDE_PLUGIN_ROOT'] and root:return root
                result=secrets.get('env',{}).get(variable,os.environ.get(variable))
                if result is None:raise ValueError('Variável necessária não configurada: '+variable)
                return result
            return REF.sub(replace,value)
        @asynccontextmanager
        async def transport():
            nonlocal root
            if server['package']:
                from .import_packages import materialize
                root=await asyncio.to_thread(materialize,self.store,server['package'])
            env={k:resolve(v) for k,v in cfg.get('env',{}).items()}
            env.update(secrets.get('env',{}));headers={k:resolve(v) for k,v in cfg.get('headers',{}).items()}
            headers.update(secrets.get('headers',{}))
            if secrets.get('token'):headers['Authorization']='Bearer '+secrets['token']
            if cfg['transport']=='stdio':
                command=resolve(cfg['command']);args=[resolve(a) for a in cfg.get('args',[])]
                if server['package']:
                    command=command.replace('${PLUGIN_ROOT}',root).replace('${CLAUDE_PLUGIN_ROOT}',root)
                    args=[a.replace('${PLUGIN_ROOT}',root).replace('${CLAUDE_PLUGIN_ROOT}',root) for a in args]
                    env.update(PLUGIN_ROOT=root,CLAUDE_PLUGIN_ROOT=root)
                with open(os.devnull,'w') as stderr:
                    async with stdio_client(StdioServerParameters(command=command,args=args,env=env,cwd=root),errlog=stderr) as streams:yield streams
            else:
                async with httpx.AsyncClient(headers=headers,timeout=httpx.Timeout(20,read=60),follow_redirects=False) as client:
                    async with streamable_http_client(resolve(cfg['url']),http_client=client) as streams:yield streams[:2]
        current=None
        try:
            async with transport() as (read,write):
                async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=30)) as session:
                    await session.initialize()
                    collected=[];cursor=None;seen=set()
                    for page in range(8):
                        listed=await session.list_tools(cursor=cursor);collected.extend(listed.tools)
                        if len(collected)>256:raise ValueError('Muitas ferramentas no servidor MCP.')
                        cursor=listed.nextCursor
                        if not cursor:break
                        if cursor in seen:raise ValueError('Paginação MCP repetida.')
                        seen.add(cursor)
                    else:raise ValueError('Paginação MCP excede oito páginas.')
                    tools=checked_tools(collected)
                    if len(json.dumps(tools))>1024*1024:raise ValueError('Catálogo MCP excede 1 MiB.')
                    with self.store.db() as db:db.execute('UPDATE mcp_servers SET tools=? WHERE id=?',(json.dumps(tools),server['id']))
                    entry['ready'].set_result(True)
                    while True:
                        current=await entry['queue'].get()
                        if current['future'].cancelled():current=None;continue
                        try:
                            response=await session.call_tool(current['name'],current['arguments'],read_timeout_seconds=timedelta(seconds=60))
                            data=response.model_dump(mode='json',exclude_none=True)
                            raw=json.dumps(data,ensure_ascii=False)
                            if len(raw)>40000:data={'content':[{'type':'text','text':raw[:40000]+'\n[Resultado MCP limitado.]'}],'isError':data.get('isError',False),'truncated':True}
                            if not current['future'].done():current['future'].set_result(data)
                        except Exception:
                            if not current['future'].done():current['future'].set_exception(ValueError('Servidor MCP falhou ao executar a ferramenta.'))
                            raise
                        current=None
        except BaseException as error:
            if not entry['ready'].done():entry['ready'].set_exception(ValueError('Não foi possível conectar ao MCP. Confira programa/URL, variáveis e autenticação.'))
            if current and not current['future'].done():current['future'].set_exception(ValueError('Conexão MCP encerrada durante a ferramenta.'))
            if isinstance(error,asyncio.CancelledError):raise
        finally:
            while not entry['queue'].empty():
                job=entry['queue'].get_nowait()
                if not job['future'].done():job['future'].set_exception(ValueError('Conexão MCP encerrada.'))

    def select(self,key,names):
        if not isinstance(names,list) or len(names)>8 or any(not isinstance(n,str) for n in names):raise ValueError('Escolha até oito ferramentas por conexão.')
        server=next((s for s in self.servers() if s['id']==key),None)
        if not server or not set(names).issubset({t['name'] for t in server['tools']}):raise ValueError('Ferramenta não encontrada nesta conexão.')
        with self.store.db() as db:db.execute('UPDATE mcp_servers SET selected=? WHERE id=?',(json.dumps(list(dict.fromkeys(names))),key))

    def definitions(self,kind,mode,internet):
        if kind=='agent' and mode=='plan':return []
        result=[]
        for server in self.servers():
            if not server['connected'] or not self._active(server) or (server['config']['transport']=='http' and not internet):continue
            for tool in server['tools']:
                if tool['name'] not in server['selected']:continue
                result.append({'type':'function','function':{'name':tool_alias(server['id'],tool['name']),'description':('MCP '+server['name']+' — '+tool['description'])[:1800],'parameters':tool['inputSchema']}})
        if len(result)>16:raise ValueError('Use no máximo 16 ferramentas MCP ativas por tarefa.')
        return result

    def prepare(self,name,arguments,options):
        allowed={t['function']['name'] for t in self.definitions(options['kind'],options['agent_mode'],options['internet'])}
        if name not in allowed:raise ValueError('Ferramenta MCP não conectada, não autorizada ou indisponível neste modo.')
        for server in self.servers():
            for tool in server['tools']:
                if tool_alias(server['id'],tool['name'])!=name:continue
                if len(json.dumps(arguments))>20000:raise ValueError('Argumentos MCP excedem 20.000 caracteres.')
                errors=list(Draft202012Validator(tool['inputSchema']).iter_errors(arguments))
                if errors:raise ValueError('Argumentos incompatíveis com a ferramenta MCP.')
                return {'name':name,'arguments':arguments,'approval':options['access']!='full','summary':server['name']+' · '+tool['name'],'preview':('Servidor: '+server['config'].get('url',server['config'].get('command',''))+'\n\n'+json.dumps(arguments,ensure_ascii=False,indent=2)),'provider':server['id'],'mcp_name':tool['name'],'display_name':tool['name']+' · '+server['name']}
        raise ValueError('Ferramenta MCP não encontrada.')

    async def call(self,action,abort):
        entry=self.connections.get(action['provider'])
        if not entry or entry['task'].done():raise ValueError('Reconecte o servidor MCP.')
        future=asyncio.get_running_loop().create_future()
        await entry['queue'].put({'name':action['mcp_name'],'arguments':action['arguments'],'future':future})
        cancelled=asyncio.create_task(abort.wait())
        try:
            done,_=await asyncio.wait([future,cancelled],timeout=65,return_when=asyncio.FIRST_COMPLETED)
            if cancelled in done or future not in done:
                future.cancel()
                await self.disconnect(action['provider'])
                raise ValueError('Ferramenta MCP interrompida; conexão encerrada.')
            return future.result()
        finally:
            cancelled.cancel();await asyncio.gather(cancelled,return_exceptions=True)
