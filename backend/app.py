import asyncio
import csv
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import quote
import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from .domain import Profile, Settings, RESTART_FIELDS, bundled_engine
from .engine import Engine
from .gguf import discover
from .storage import Store
from .folders import browse_folders
from .generation_stats import DEFAULT_SYSTEM_PROMPT,backend_timings,estimate_seconds
from .attachments import MAX_FILE,extract,public_attachment,model_message
from .agent_tools import ApprovalBroker,definitions
from .extensions import catalog,change as change_extension,tools_for,apply_skills
from .turns import configure_messages,run_turn
from .revisions import undo_revision

ROOT = Path(__file__).resolve().parent.parent

class ConversationInput(BaseModel):
    title: str = Field('Nova conversa',min_length=1,max_length=200)
    kind: Literal['chat','agent'] = 'chat'

class GenerateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    conversation: str
    content: str = Field('',max_length=200000)
    system: str | None = Field(None,max_length=100000)
    profile: Profile = Field(default_factory=Profile)
    action: str = 'send'
    benchmark: bool = False
    attachments: list[str] = Field(default_factory=list,max_length=6)
    skills: list[str] = Field(default_factory=list,max_length=3)
    kind: Literal['chat','agent'] = 'chat'
    agent_mode: Literal['build','plan'] = 'build'
    access: Literal['ask','auto','full'] = 'ask'
    internet: bool = False
    workspace: str = Field('',max_length=4096)

class ExtensionInput(BaseModel):
    action: Literal['install','enable','disable','remove']

class StartInput(BaseModel):
    path: str
    profile: Profile

class UndoInput(BaseModel):
    confirmed: Literal[True]

class ApprovalInput(BaseModel):
    allow: bool

class EditInput(BaseModel):
    content: str = Field(max_length=200000)


def create_app(data_dir=None):
    store = Store(data_dir or os.environ.get('CENTRAL_DATA_DIR') or ROOT/'data')
    engine = Engine(store)
    approvals = ApprovalBroker()
    uploads = asyncio.Semaphore(2)
    token = secrets.token_urlsafe(32)
    logger = logging.getLogger('central.'+uuid.uuid4().hex)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(store.directory/'central.log',maxBytes=1048576,backupCount=3,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)

    @asynccontextmanager
    async def lifespan(app):
        logger.info('Gerenciador iniciado')
        yield
        await asyncio.to_thread(engine.stop)
        logger.info('Gerenciador encerrado')
        handler.close()
        logger.removeHandler(handler)

    app = FastAPI(title='Central IA Studio',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.state.store, app.state.engine, app.state.approvals = store, engine, approvals

    @app.middleware('http')
    async def local_security(request, call_next):
        host = request.url.hostname
        if host not in ['localhost','127.0.0.1','::1','testserver']:
            return JSONResponse({'detail':'Host não autorizado'},status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Origem não autorizada'},status_code=403)
        if request.method not in ['GET','HEAD','OPTIONS']:
            if request.headers.get('x-central-token') != token:
                return JSONResponse({'detail':'Token local inválido. Recarregue a página.'},status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail':'Requisição externa rejeitada'},status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        logger.warning('Entrada rejeitada: %s',error)
        return JSONResponse({'detail':str(error)},status_code=400)

    @app.exception_handler(httpx.HTTPError)
    async def backend_error(request, error):
        logger.warning('Falha de comunicação: %s',type(error).__name__)
        return JSONResponse({'detail':'Falha de comunicação com o motor: '+str(error)},status_code=502)

    @app.get('/api/bootstrap')
    def bootstrap():
        saved = store.get('settings',{})
        try:
            settings = Settings(**saved).model_dump()
            warning = None
        except ValidationError:
            settings = Settings().model_dump()
            warning = 'Configuração inválida preservada no banco. Salve novamente para recuperar.'
        if not settings['executable']:
            settings['executable'] = bundled_engine()
        return {'token':token,'settings':settings,'profile':Profile().model_dump(),'default_system_prompt':DEFAULT_SYSTEM_PROMPT,'restart_fields':RESTART_FIELDS,'warning':warning,'version':'0.5.0','extensions':catalog(store)}

    @app.put('/api/settings')
    def settings(value: Settings):
        try:
            previous = Settings(**store.get('settings',{}))
        except ValidationError:
            previous = None
        connection_changed = (previous is None or previous.engine_url != value.engine_url or
                              (previous.executable or bundled_engine()) != (value.executable or bundled_engine()))
        if connection_changed and (engine.generation_lock.locked() or (engine.process and engine.process.poll() is None)):
            raise ValueError('Pare a geração e o motor gerenciado antes de alterar a conexão')
        store.put('settings',value.model_dump())
        logger.info('Configuração salva')
        return value.model_dump()

    @app.get('/api/folders')
    def folders(path: str = ''):
        return browse_folders(path)

    @app.get('/api/models')
    def models():
        return discover(Settings(**store.get('settings',{})).folders)

    @app.post('/api/attachments')
    async def upload_attachment(request: Request, name: str):
        async with uploads:
            data=bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data)>MAX_FILE:raise HTTPException(413,'Cada arquivo pode ter até 8 MiB.')
            item=await asyncio.to_thread(extract,name,bytes(data))
            with store.db() as db:
                db.execute('DELETE FROM attachments WHERE created<? AND id NOT IN (SELECT attachment_id FROM message_attachments)',(time.time()-86400,))
                db.execute('INSERT INTO attachments(id,name,mime,kind,size,text,data,vision,warning,sha256,created) VALUES (?,?,?,?,?,?,?,?,?,?,?)',tuple(item[k] for k in ['id','name','mime','kind','size','text','data','vision','warning','sha256','created']))
            return public_attachment(item)

    @app.get('/api/attachments/{aid}/content')
    def attachment_content(aid: str):
        with store.db() as db:
            row=db.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
        if row is None:raise HTTPException(404,'Anexo não encontrado')
        disposition='inline' if row['kind']=='image' else 'attachment'
        return Response(bytes(row['data']),media_type=row['mime'],headers={'Content-Disposition':disposition+"; filename*=UTF-8''"+quote(row['name'],safe='')})

    @app.delete('/api/attachments/{aid}')
    def delete_attachment(aid: str):
        with store.db() as db:
            if db.execute('SELECT 1 FROM message_attachments WHERE attachment_id=?',(aid,)).fetchone():
                raise ValueError('Este anexo faz parte do histórico. Exclua a conversa para removê-lo.')
            db.execute('DELETE FROM attachments WHERE id=?',(aid,))
        return {'deleted':True}

    @app.post('/api/revisions/{rid}/restore')
    def restore_revision(rid: str, value: UndoInput):
        if engine.generation_lock.locked():raise ValueError('Aguarde a tarefa antes de desfazer uma edição.')
        return undo_revision(store,rid)

    @app.post('/api/approvals/{aid}')
    def decide_approval(aid: str, value: ApprovalInput):
        approvals.decide(aid,value.allow)
        return {'received':True}

    @app.get('/api/profiles')
    def profiles(model: str = 'default'):
        return Profile(**(store.profile(model) or {})).model_dump()

    @app.put('/api/profiles')
    def save_profile(value: Profile, model: str = 'default'):
        store.save_profile(model,value.model_dump())
        return value.model_dump()

    @app.get('/api/engine')
    async def status():
        return await engine.status()

    @app.post('/api/engine/start')
    async def start(value: StartInput):
        if engine.generation_lock.locked():
            raise ValueError('Interrompa a geração antes de iniciar o motor')
        library = discover(Settings(**store.get('settings',{})).folders)['models']
        matching = next((m for m in library if m['path'] == str(Path(value.path).resolve())),None)
        if matching and matching.get('projector'):raise ValueError('Este GGUF é um projetor. Selecione o modelo principal e configure o projetor no perfil.')
        if not matching or not matching.get('metadata'):
            raise ValueError('Escolha um GGUF válido em uma pasta cadastrada')
        async with engine.lifecycle_lock:
            result = engine.start(value.path,value.profile)
        logger.info('Motor iniciado pid=%s',result['pid'])
        return result

    @app.post('/api/engine/stop')
    async def stop():
        if engine.generation_lock.locked():
            await engine.abort()
        async with engine.lifecycle_lock:
            await asyncio.to_thread(engine.stop)
        logger.info('Parada do motor gerenciado solicitada')
        return {'stopped':True}

    @app.post('/api/abort')
    async def abort():
        result = await engine.abort()
        logger.info('Interrupção solicitada')
        return result

    @app.get('/api/conversations')
    def conversations(q: str = '', kind: Literal['chat','agent'] = 'chat'):
        with store.db() as db:
            rows = db.execute('''SELECT DISTINCT c.* FROM conversations c LEFT JOIN messages m ON m.conversation=c.id
                WHERE c.kind=? AND (c.title LIKE ? OR m.content LIKE ?) ORDER BY c.created DESC''',(kind,'%'+q+'%','%'+q+'%')).fetchall()
        return [dict(r) for r in rows]

    @app.post('/api/conversations')
    def new_conversation(value: ConversationInput):
        return {'id':store.conversation(value.title,value.kind)}

    def ensure_conversation(cid):
        with store.db() as db:
            if not db.execute('SELECT 1 FROM conversations WHERE id=?',(cid,)).fetchone():
                raise HTTPException(404,'Conversa não encontrada')

    @app.get('/api/conversations/{cid}')
    def get_conversation(cid: str):
        ensure_conversation(cid)
        return store.messages(cid)

    @app.patch('/api/conversations/{cid}')
    def rename_conversation(cid: str, value: ConversationInput):
        ensure_conversation(cid)
        title = value.title.strip()
        if not title:
            raise ValueError('O título não pode ficar vazio')
        with store.db() as db:
            db.execute('UPDATE conversations SET title=? WHERE id=?',(title,cid))
        return {'saved':True}

    @app.delete('/api/conversations/{cid}')
    def delete_conversation(cid: str):
        if engine.generation_lock.locked():
            raise ValueError('Aguarde a geração antes de excluir uma conversa')
        ensure_conversation(cid)
        with store.db() as db:
            attached=[r[0] for r in db.execute('SELECT attachment_id FROM message_attachments WHERE message_id IN (SELECT id FROM messages WHERE conversation=?)',(cid,))]
            db.execute('DELETE FROM conversations WHERE id=?',(cid,))
            for aid in attached:
                db.execute('DELETE FROM attachments WHERE id=? AND id NOT IN (SELECT attachment_id FROM message_attachments)',(aid,))
            db.execute('DELETE FROM settings WHERE key=?',('session:'+cid,))
            db.execute('DELETE FROM agent_revisions WHERE conversation=?',(cid,))
            db.execute('DELETE FROM settings WHERE key=?',('system:'+cid,))
        return {'deleted':True}

    @app.patch('/api/messages/{mid}')
    def edit(mid: int, value: EditInput):
        if engine.generation_lock.locked():
            raise ValueError('Aguarde a geração antes de editar')
        with store.db() as db:
            if not db.execute('SELECT 1 FROM messages WHERE id=?',(mid,)).fetchone():
                raise HTTPException(404,'Mensagem não encontrada')
            db.execute('UPDATE messages SET content=? WHERE id=?',(value.content,mid))
        return {'saved':True}

    @app.get('/api/conversations/{cid}/export')
    def export(cid: str, format: str = 'json'):
        ensure_conversation(cid)
        messages = store.messages(cid)
        if format == 'md':
            body = '\n\n'.join('## '+{'user':'Você','assistant':'Assistente','system':'Sistema'}.get(m['role'],m['role'])+'\n\n'+m['content']+''.join('\n\nAnexo: '+a['name']+' (SHA256 '+a['sha256']+')' for a in m.get('attachments',[])) for m in messages)
            return Response(body,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="conversa.md"'})
        return Response(json.dumps(messages,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="conversa.json"'})

    @app.get('/api/extensions')
    def extensions_catalog():
        return {'items':catalog(store)}

    @app.patch('/api/extensions/{key}')
    def update_extension(key: str,value: ExtensionInput):
        if engine.generation_lock.locked():raise HTTPException(409,'Aguarde a tarefa terminar antes de alterar extensões.')
        return {'items':change_extension(store,key,value.action)}

    @app.post('/api/generate')
    async def generate(value: GenerateInput, request: Request):
        ensure_conversation(value.conversation)
        with store.db() as db:
            saved_kind=db.execute('SELECT kind FROM conversations WHERE id=?',(value.conversation,)).fetchone()[0]
        if saved_kind!=value.kind:raise ValueError('Esta conversa pertence a outro modo.')
        if value.kind=='agent' and value.workspace and not Path(value.workspace).expanduser().is_dir():
            raise ValueError('Escolha uma pasta de projeto existente.')
        if value.action not in ['send','regenerate','continue']:
            raise ValueError('Ação desconhecida')
        if engine.generation_lock.locked():
            raise HTTPException(409,'Já existe uma geração em andamento')
        await engine.generation_lock.acquire()
        try:
            history = store.messages(value.conversation)
            removed = None
            if value.action == 'regenerate':
                if not history or history[-1]['role'] != 'assistant':
                    raise ValueError('Não há resposta para regenerar')
                removed = history.pop()
            if value.action == 'continue' and (not history or history[-1]['role'] != 'assistant'):
                raise ValueError('Não há resposta para continuar')
            image_count=sum(a['kind']=='image' for m in history for a in m.get('attachments',[]))
            if image_count>8:raise ValueError('Esta conversa contém mais de oito imagens. Use uma nova conversa para manter o processamento limitado.')
            messages = [model_message(store,m) for m in history]
            system = value.system if value.system is not None else store.get('system:'+value.conversation,DEFAULT_SYSTEM_PROMPT)
            if system:
                messages.insert(0,{'role':'system','content':system})
            if value.action == 'send':
                if not value.content.strip() and not value.attachments:
                    raise ValueError('Escreva uma mensagem ou anexe um arquivo')
                value.content=value.content or 'Analise os anexos.'
                selected_attachments=[]
                for aid in dict.fromkeys(value.attachments):
                    with store.db() as db:
                        row=db.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
                    if row is None:raise ValueError('Um anexo não foi encontrado. Envie-o novamente.')
                    selected_attachments.append(public_attachment(row))
                if image_count+sum(a['kind']=='image' for a in selected_attachments)>8:
                    raise ValueError('Esta conversa excederia oito imagens. Use uma nova conversa.')
                messages.append(model_message(store,{'role':'user','content':value.content,'attachments':selected_attachments}))
            options={k:getattr(value,k) for k in ['kind','agent_mode','access','internet','workspace','skills']}
            document_ids=list(dict.fromkeys(a['id'] for m in history for a in m.get('attachments',[]) if a['kind']=='document'))
            if value.action=='send':document_ids+= [a['id'] for a in selected_attachments if a['kind']=='document' and a['id'] not in document_ids]
            messages=apply_skills(store,messages,value.skills)
            tool_defs=tools_for(store,definitions(value.kind,value.agent_mode,value.workspace,value.internet,bool(document_ids)))
            tool_options=options | {'attachment_ids':document_ids}
            native_tools=(await engine.status()).get('tools') is True if tool_defs else False
            messages=configure_messages(messages,tool_defs,native_tools,value.agent_mode if value.kind=='agent' else 'conversa')
            payload, limits = await engine.prepare(messages,value.profile,tool_defs if native_tools else None)
            with store.db() as db:
                prior = db.execute("SELECT stats FROM messages WHERE role='assistant' ORDER BY id DESC LIMIT 200").fetchall()
            limits['estimated_seconds'],limits['estimate_samples'] = estimate_seconds(
                [json.loads(row['stats']) for row in prior],limits['model'],engine.kind,
                value.profile.model_dump(),limits['effective_output'])
            payload['genkey'] = uuid.uuid4().hex
            engine.request_key, engine.cancelled = payload['genkey'], False
            engine.abort_event.clear()
            if value.action == 'send':
                store.add_message(value.conversation,'user',value.content,attachments=list(dict.fromkeys(value.attachments)))
            if removed:
                with store.db() as db:
                    # Preserve o resultado anterior em avaliação antes de regenerar.
                    db.execute('INSERT INTO benchmarks VALUES (?,?,?)',(uuid.uuid4().hex,time.time(),json.dumps({'kind':'regenerated_previous','result':removed['content'],'stats':removed['stats']})))
                    db.execute('DELETE FROM messages WHERE id=?',(removed['id'],))
            store.put('system:'+value.conversation,system)
            store.put('session:'+value.conversation,options)
        except BaseException:
            engine.request_key = None
            engine.generation_lock.release()
            raise

        def sse(kind, data):
            return 'event: '+kind+'\ndata: '+json.dumps(data,ensure_ascii=False)+'\n\n'

        async def events():
            start_time, first = time.perf_counter(), None
            content, reasoning, finish, usage = '', '', None, {}
            timings = {}
            activities = {}
            timeline = []
            error = None
            try:
                yield sse('limits',limits)
                async for event,chunk in run_turn(engine,store,approvals,value.conversation,messages,value.profile,payload,tool_defs,native_tools,tool_options):
                    if event=='activity':
                        if chunk['id'] not in activities:timeline.append({'type':'activity','id':chunk['id']})
                        activities[chunk['id']]=chunk
                        yield sse('activity',chunk)
                        continue
                    if event=='limits':
                        yield sse('limits',chunk)
                        continue
                    if await request.is_disconnected():
                        await engine.abort()
                        finish = 'interrompida'
                        break
                    if chunk.get('error'):
                        raise ValueError(str(chunk['error']))
                    if chunk.get('usage'):
                        usage = chunk['usage']
                    if chunk.get('timings'):
                        timings = backend_timings(chunk['timings'])
                    for choice in chunk.get('choices',[]):
                        delta = choice.get('delta',{})
                        c, r = delta.get('content') or '', delta.get('reasoning_content') or ''
                        if c or r:
                            first = first or time.perf_counter()
                            content += c
                            if c:
                                if timeline and timeline[-1]['type']=='text':timeline[-1]['content']+=c
                                else:timeline.append({'type':'text','content':c})
                            reasoning += r
                            yield sse('delta',{'content':c,'reasoning':r})
                        finish = choice.get('finish_reason') or finish
                if engine.cancelled:
                    finish = 'interrompida'
                elif not finish:
                    finish = 'conexão_encerrada_sem_motivo'
            except asyncio.CancelledError:
                finish = 'cliente_desconectado'
                try:
                    await asyncio.shield(engine.abort())
                except Exception:
                    logger.warning('Falha ao interromper após desconexão')
                raise
            except Exception as e:
                error, finish = str(e), 'erro'
                logger.warning('Geração falhou: %s',type(e).__name__)
                yield sse('error',{'detail':error})
            finally:
                elapsed = time.perf_counter()-start_time
                count = usage.get('completion_tokens')
                stats = limits | {'usage':usage,'generated_tokens':count,'finish_reason':finish,
                    'elapsed':elapsed,'ttft':first-start_time if first else None,
                    'tokens_per_second':count/elapsed if count is not None and elapsed else None,
                    'truncated':finish=='length','error':error,'backend_timings':timings,
                    'engine_kind':engine.kind,'profile':value.profile.model_dump(),'activities':list(activities.values()),'timeline':timeline,'session':options}
                try:
                    store.add_message(value.conversation,'assistant',content,reasoning,stats)
                    if value.benchmark:
                        library = discover(Settings(**store.get('settings',{})).folders)['models']
                        active = next((m for m in library if m['path']==engine.active_path),{})
                        result = {'kind':'benchmark','model':limits['model'],'quantization':active.get('metadata',{}).get('quantization'),
                            'prompt':messages,'profile':value.profile.model_dump(),'stats':stats,'result':content,'reasoning':reasoning,
                            'ram_available':psutil.virtual_memory().available,'engine_ram':process_memory(engine)}
                        with store.db() as db:
                            db.execute('INSERT INTO benchmarks VALUES (?,?,?)',(uuid.uuid4().hex,time.time(),json.dumps(result,ensure_ascii=False)))
                    logger.info('Geração finalizada: %s; tokens=%s',finish,count)
                finally:
                    engine.request_key = None
                    engine.generation_lock.release()
            yield sse('done',stats)
        return StreamingResponse(events(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

    @app.get('/api/system-prompt/{cid}')
    def system_prompt(cid: str):
        return {'content':store.get('system:'+cid,DEFAULT_SYSTEM_PROMPT),'options':store.get('session:'+cid,{})}

    @app.get('/api/metrics')
    async def metrics():
        mem, swap = psutil.virtual_memory(), psutil.swap_memory()
        return {'ram_total':mem.total,'ram_available':mem.available,'ram_used':mem.used,
                'cpu_percent':psutil.cpu_percent(),'engine_ram':process_memory(engine),
                'swap_used':swap.used,'paging_in_bytes':getattr(swap,'sin',None),
                'paging_out_bytes':getattr(swap,'sout',None),'engine':await engine.status(),
                'generating':engine.generation_lock.locked()}

    @app.get('/api/benchmarks')
    def benchmarks(format: str = 'json'):
        with store.db() as db:
            rows = [dict(r) | {'value':json.loads(r['value'])} for r in db.execute('SELECT * FROM benchmarks ORDER BY created DESC')]
        if format == 'csv':
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(['id','data','tipo','modelo','resultado','estatisticas_json','perfil_json','prompt_json'])
            for r in rows:
                v = r['value']
                cells = [r['id'],r['created'],v.get('kind'),v.get('model'),v.get('result'),json.dumps(v.get('stats')),json.dumps(v.get('profile')),json.dumps(v.get('prompt'),ensure_ascii=False)]
                writer.writerow(["'"+str(c) if str(c).startswith(('=','+','-','@')) else c for c in cells])
            return Response('\ufeff'+buffer.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="benchmarks.csv"'})
        return rows

    @app.get('/api/logs')
    def logs():
        result = {}
        for name in ['central.log','engine.log']:
            path = store.directory/name
            if path.exists():
                with path.open('rb') as f:
                    f.seek(max(0,path.stat().st_size-65536))
                    result[name] = f.read().decode('utf-8',errors='replace')
            else:
                result[name] = ''
        return result

    @app.post('/api/backup')
    def backup():
        return {'file':store.backup().name}

    @app.get('/api/source')
    def source():
        path = ROOT/'central-ia-studio-source.zip'
        if not path.is_file():
            from scripts.package_source import source_files
            from zipfile import ZipFile, ZIP_DEFLATED
            buffer = io.BytesIO()
            with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
                for item, relative in source_files():
                    archive.write(item,str(relative))
            return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename=central-ia-studio-source.zip'})
        return FileResponse(path,filename=path.name)

    dist = ROOT/'frontend'/'dist'
    if dist.is_dir():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app


def process_memory(engine):
    if engine.process and engine.process.poll() is None:
        try:
            return psutil.Process(engine.process.pid).memory_info().rss
        except psutil.Error:
            pass
    return None
