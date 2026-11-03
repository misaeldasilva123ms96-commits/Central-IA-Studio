import asyncio
import json
import socket
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.domain import Profile, Settings, build_command
from backend.gguf import metadata, discover
from backend.storage import Store


def gguf(path, template='{{ enable_thinking }}'):
    entries={'general.name':'Teste','general.architecture':'qwen2','general.file_type':15,'tokenizer.chat_template':template}
    def s(v):
        b=v.encode();return struct.pack('<Q',len(b))+b
    data=b'GGUF'+struct.pack('<IQQ',3,0,len(entries))
    for k,v in entries.items():
        data+=s(k)+struct.pack('<I',4 if isinstance(v,int) else 8)+(struct.pack('<I',v) if isinstance(v,int) else s(v))
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path

@pytest.fixture
def fake_engine():
    class Handler(BaseHTTPRequestHandler):
        payloads=[];aborts=[];fail=False;prompt_tokens=40;slow=False
        def log_message(self,*args): pass
        def send(self,data):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
        def do_GET(self):
            data={'/api/extra/version':{'result':'KoboldCpp','version':'1.124.2','jinja':True},'/api/v1/model':{'result':'modelo-fixture'},'/api/extra/true_max_context_length':{'value':8192}}
            self.send(data.get(self.path,{}))
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            if self.path=='/api/extra/tokencount':
                Handler.payloads.append(('count',data));return self.send({'value':Handler.prompt_tokens})
            if self.path=='/api/extra/abort':
                Handler.aborts.append(data);return self.send({'success':True})
            Handler.payloads.append(('generate',data))
            if Handler.fail:
                self.send_error(503);return
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            if Handler.slow: time.sleep(.25)
            chunks=[{'choices':[{'delta':{'reasoning_content':'Teste separado. '},'finish_reason':None}]},
                    {'choices':[{'delta':{'content':'Olá, mundo!'},'finish_reason':None}]},
                    {'choices':[{'delta':{},'finish_reason':'length'}]},
                    {'choices':[],'usage':{'prompt_tokens':40,'completion_tokens':3,'total_tokens':43}}]
            for c in chunks:
                self.wfile.write(('data: '+json.dumps(c)+'\n\n').encode());self.wfile.flush()
            self.wfile.write(b'data: [DONE]\n\n')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',Handler
    server.shutdown();server.server_close();thread.join()

@pytest.fixture
def client(tmp_path,fake_engine):
    app=create_app(tmp_path/'data')
    with TestClient(app) as c:
        token=c.get('/api/bootstrap').json()['token']
        c.headers['X-Central-Token']=token
        assert c.put('/api/settings',json={'engine_url':fake_engine[0],'folders':[],'executable':''}).status_code==200
        yield c


def test_gguf_recursive_dedup_and_invalid(tmp_path):
    model=gguf(tmp_path/'models'/'nested'/'one.gguf')
    (model.parent/'bad.gguf').write_bytes(b'not gguf')
    result=discover([str(tmp_path/'models'),str(model.parent)])
    assert len(result['models'])==2
    meta=metadata(model)
    assert meta['general.architecture']=='qwen2'
    assert meta['quantization']=='Q4_K_M'
    assert meta['thinking_switch_in_template'] is True
    assert 'inválido' in result['models'][0]['status']
    assert discover([str(tmp_path/'missing')])['errors']


def test_malicious_gguf_limits(tmp_path):
    p=tmp_path/'bad.gguf';p.write_bytes(b'GGUF'+struct.pack('<IQQQ',3,0,1,2**50))
    with pytest.raises(ValueError): metadata(p)


def test_settings_profile_recovery_and_backup(client):
    profile=Profile(max_output=12000,context=32768).model_dump()
    assert client.put('/api/profiles?model=model-a',json=profile).status_code==200
    assert client.get('/api/profiles?model=model-a').json()['max_output']==12000
    store=client.app.state.store
    reopened=Store(store.directory)
    assert reopened.profile('model-a')['context']==32768
    assert Path(store.directory/client.post('/api/backup',json={}).json()['file']).is_file()
    store.put('settings',{'engine_url':'https://evil.example'})
    assert client.get('/api/bootstrap').json()['warning']
    assert reopened.get('settings')['engine_url']=='https://evil.example'


def test_chat_streaming_above_2048_thinking_export(client,fake_engine):
    cid=client.post('/api/conversations',json={'title':'Minha conversa'}).json()['id']
    p=Profile(context=8192,max_output=5000,thinking='on').model_dump()
    r=client.post('/api/generate',json={'conversation':cid,'content':'Oi','system':'Seja útil','profile':p,'benchmark':True})
    assert r.status_code==200
    assert 'event: limits' in r.text and 'event: delta' in r.text and 'event: done' in r.text
    payload=fake_engine[1].payloads[-1][1]
    assert payload['max_tokens']==5000
    assert payload['chat_template_kwargs']=={'enable_thinking':True}
    assert fake_engine[1].payloads[-2][1]['messages'][0]['role']=='system'
    messages=client.get('/api/conversations/'+cid).json()
    assert messages[-1]['content']=='Olá, mundo!'
    assert messages[-1]['reasoning']=='Teste separado. '
    assert messages[-1]['stats']['generated_tokens']==3
    assert messages[-1]['stats']['truncated'] is True
    assert messages[-1]['stats']['thinking_confirmed'] is False
    assert 'Olá, mundo!' in client.get('/api/conversations/'+cid+'/export?format=md').text
    assert client.get('/api/conversations?q=Oi').json()[0]['id']==cid
    bench=client.get('/api/benchmarks').json()[0]['value']
    assert bench['model']=='modelo-fixture' and bench['stats']['ttft']>=0
    assert 'estatisticas_json' in client.get('/api/benchmarks?format=csv').text
    assert 'Geração finalizada' in client.get('/api/logs').json()['central.log']
    assert client.get('/api/system-prompt/'+cid).json()['content']=='Seja útil'

@pytest.mark.parametrize('mode,thinking,expected',[('rapido','on',False),('profundo','off',True),('personalizado','off',False)])
def test_thinking_modes(client,fake_engine,mode,thinking,expected):
    cid=client.post('/api/conversations',json={}).json()['id']
    p=Profile(mode=mode,thinking=thinking).model_dump()
    assert client.post('/api/generate',json={'conversation':cid,'content':'Oi','profile':p}).status_code==200
    assert fake_engine[1].payloads[-1][1]['chat_template_kwargs']['enable_thinking'] is expected


def test_context_clamping_and_exhaustion(client,fake_engine):
    cid=client.post('/api/conversations',json={}).json()['id']
    fake_engine[1].prompt_tokens=7800
    r=client.post('/api/generate',json={'conversation':cid,'content':'Longo','profile':Profile(context=8192,max_output=10000).model_dump()})
    assert r.status_code==200
    assert fake_engine[1].payloads[-1][1]['max_tokens']==384
    fake_engine[1].prompt_tokens=8190
    assert client.post('/api/generate',json={'conversation':cid,'content':'Muito longo','profile':Profile(context=8192).model_dump()}).status_code==400
    assert len(client.get('/api/conversations/'+cid).json())==2
    assert not client.app.state.engine.generation_lock.locked()


def test_failure_persists_partial_and_unlocks(client,fake_engine):
    cid=client.post('/api/conversations',json={}).json()['id'];fake_engine[1].fail=True
    r=client.post('/api/generate',json={'conversation':cid,'content':'falha'})
    assert 'event: error' in r.text
    assert client.get('/api/conversations/'+cid).json()[-1]['stats']['finish_reason']=='erro'
    assert not client.app.state.engine.generation_lock.locked()
    fake_engine[1].fail=False
    assert 'event: done' in client.post('/api/generate',json={'conversation':cid,'action':'regenerate'}).text
    assert len(client.get('/api/conversations/'+cid).json())==2
    assert client.get('/api/benchmarks').json()[0]['value']['kind']=='regenerated_previous'
    assert 'event: done' in client.post('/api/generate',json={'conversation':cid,'action':'continue'}).text


def test_edit_integrity(client):
    cid=client.post('/api/conversations',json={}).json()['id']
    store=client.app.state.store;mid=store.add_message(cid,'user','Original')
    assert client.patch('/api/messages/'+str(mid),json={'content':'Corrigida'}).status_code==200
    assert client.get('/api/conversations/'+cid).json()[0]['content']=='Corrigida'
    assert client.post('/api/generate',json={'conversation':'ausente','content':'Oi'}).status_code==404
    with store.db() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        with pytest.raises(Exception):
            db.execute("INSERT INTO messages(conversation,role,content) VALUES ('missing','user','oi')")


def test_csrf_origin_host_validation(client):
    assert client.post('/api/abort',json={},headers={'X-Central-Token':'bad'}).status_code==403
    assert client.post('/api/abort',json={},headers={'Origin':'http://evil.example'}).status_code==403
    assert client.get('/api/bootstrap',headers={'Host':'evil.example'}).status_code==403
    for url in ['http://evil.example:5001','http://localhost:5001/redirect','http://user@localhost:5001','file:///tmp/x','http://127.0.0.1:22']:
        assert client.put('/api/settings',json={'engine_url':url}).status_code==422
    assert client.put('/api/profiles',json={'threads':'; rm -rf /'}).status_code==422
    assert client.put('/api/profiles',json={'batch_size':123}).status_code==422
    assert client.put('/api/profiles',json={'extra_args':'--host 0.0.0.0'}).status_code==422


@pytest.mark.skipif(sys.platform == "win32", reason="Fixture executável POSIX; Windows tem smoke test do pacote no workflow")
def test_process_lifecycle_owned_only(client,tmp_path):
    from backend.engine import Engine
    model=gguf(tmp_path/'a b'/'test.gguf')
    # Fixture executável controlada: não é KoboldCpp e não é um teste de inferência.
    exe=tmp_path/'fake engine'
    exe.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(60)\n');exe.chmod(0o755)
    p=Profile(template='')
    args=build_command(str(exe),str(model),p,5001)
    assert args[args.index('--model')+1]==str(model)
    assert '--host' in args and args[args.index('--host')+1]=='127.0.0.1'
    store=client.app.state.store
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    store.put('settings',{'engine_url':f'http://127.0.0.1:{port}','executable':str(exe)})
    engine=client.app.state.engine
    result=engine.start(model,p)
    assert result['pid'] and engine.process.poll() is None
    with pytest.raises(ValueError):engine.start(model,p)
    engine.stop();assert engine.process.poll() is not None
    engine.stop()
    # Porta ocupada deve ser detectada antes da execução.
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',port));occupied.listen()
        with pytest.raises(ValueError,match='Porta ocupada'):engine.start(model,p)
    template=tmp_path/'custom.jinja';template.write_text('{{ messages }}')
    assert '--jinjatemplate' in build_command(str(exe),str(model),Profile(template=str(template)),5001)
    with pytest.raises(ValueError):build_command(str(exe),str(model),Profile(template='--host evil'),5001)


def test_abort_request_key(client,fake_engine):
    engine=client.app.state.engine
    engine.request_key='owned-generation'
    assert client.post('/api/abort',json={}).status_code==200
    assert fake_engine[1].aborts[-1]=={'genkey':'owned-generation'}
    assert engine.cancelled
    engine.request_key=None
    assert client.post('/api/abort',json={}).json()=={'interrupted':False}


def test_unavailable_engine_metrics(client,tmp_path):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    client.put('/api/settings',json={'engine_url':f'http://127.0.0.1:{port}'})
    assert client.get('/api/engine').json()['connected'] is False
    metrics=client.get('/api/metrics').json()
    assert metrics['ram_total']>0 and metrics['engine_ram'] is None


def test_jinja_capability_gate(client,fake_engine):
    engine=client.app.state.engine
    async def no_jinja():
        return {'connected':True,'context':8192,'capabilities':{'jinja':False}}
    original=engine.status;engine.status=no_jinja
    cid=client.post('/api/conversations',json={}).json()['id']
    try:
        r=client.post('/api/generate',json={'conversation':cid,'content':'Oi','profile':Profile(thinking='on').model_dump()})
        assert r.status_code==400 and 'Jinja' in r.json()['detail']
        assert client.get('/api/conversations/'+cid).json()==[]
    finally: engine.status=original


def test_concurrent_generation_rejected(client):
    engine=client.app.state.engine
    asyncio.run(engine.generation_lock.acquire())
    cid=client.post('/api/conversations',json={}).json()['id']
    try:
        assert client.post('/api/generate',json={'conversation':cid,'content':'Oi'}).status_code==409
        assert client.put('/api/settings',json={'engine_url':'http://127.0.0.1:5001'}).status_code==400
    finally:engine.generation_lock.release()


def test_start_requires_registered_model(client,tmp_path):
    model=gguf(tmp_path/'unregistered.gguf')
    r=client.post('/api/engine/start',json={'path':str(model),'profile':Profile().model_dump()})
    assert r.status_code==400 and 'pasta cadastrada' in r.json()['detail']


def test_real_launch_arguments(tmp_path):
    exe=tmp_path/'engine.exe';exe.write_bytes(b'fixture only, never executed')
    model=gguf(tmp_path/'test.gguf')
    p=Profile(context=16384,threads=3,blas_threads=4,batch_size=256,gpu_layers=0,cache_kv='q4_0',flash_attention=False)
    command=build_command(str(exe),str(model),p,5001)
    for flag,value in [('--contextsize','16384'),('--threads','3'),('--blasthreads','4'),('--blasbatchsize','256'),('--gpulayers','0'),('--quantkv','q4_0')]:
        assert command[command.index(flag)+1]==value
    assert '--noflashattention' in command and '--jinja' in command


def test_corresponding_source_access(client):
    import io
    from zipfile import ZipFile
    response=client.get('/api/source')
    assert response.status_code==200
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert 'backend/app.py' in archive.namelist()
        assert not any(n.startswith(('data/','work/')) or n.endswith(('.exe','.gguf')) for n in archive.namelist())
