import asyncio
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
from zipfile import ZipFile
import pytest
from PIL import Image
from pypdf import PdfWriter
from test_central import client,fake_engine
from backend.storage import Store
from backend.agent_tools import prepare_action,execute_action,ApprovalBroker,run_command
from backend.attachments import ingest
from backend import web


def upload(client,name,data):
    response=client.post('/api/attachments',params={'name':name},content=data,headers={'Content-Type':'application/octet-stream'})
    assert response.status_code==200,response.text
    return response.json()


def test_old_database_migrates_without_losing_conversations(tmp_path):
    directory=tmp_path/'old';directory.mkdir()
    with sqlite3.connect(directory/'central.sqlite3') as db:
        db.execute('CREATE TABLE conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,created REAL NOT NULL)')
        db.execute('INSERT INTO conversations VALUES (?,?,?)',('old','Preservada',123.))
    store=Store(directory)
    with store.db() as db:
        assert dict(db.execute('SELECT * FROM conversations').fetchone())=={'id':'old','title':'Preservada','created':123.,'kind':'chat'}
    assert Store(directory).conversation('Agente','agent')


def test_document_ingestion_history_backup_and_export(client,fake_engine):
    original='Fornecedor,Valor\nA,10\nB,-5\n'.encode()
    item=upload(client,'fornecedores.csv',original)
    assert item['sha256']==hashlib.sha256(original).hexdigest()
    assert client.get('/api/attachments/'+item['id']+'/content').content==original
    cid=client.post('/api/conversations',json={}).json()['id']
    response=client.post('/api/generate',json={'conversation':cid,'content':'Some os valores positivos','attachments':[item['id']]})
    assert response.status_code==200 and 'event: done' in response.text,response.text
    payload=fake_engine[1].payloads[-1][1]
    assert 'Fornecedor,Valor' in payload['messages'][-1]['content']
    messages=client.get('/api/conversations/'+cid).json()
    assert messages[0]['attachments'][0]['id']==item['id']
    assert 'fornecedores.csv' in client.get('/api/conversations/'+cid+'/export?format=md').text
    backup=client.post('/api/backup',json={}).json()['file']
    with sqlite3.connect(client.app.state.store.directory/backup) as db:
        assert db.execute('SELECT data FROM attachments').fetchone()[0]==original
    assert client.delete('/api/attachments/'+item['id']).status_code==400
    assert client.delete('/api/conversations/'+cid).status_code==200
    assert client.get('/api/attachments/'+item['id']+'/content').status_code==404


def test_images_keep_original_and_require_actual_vision(client):
    out=io.BytesIO();Image.new('RGB',(12,9),'red').save(out,format='PNG');raw=out.getvalue()
    item=upload(client,'foto.png',raw)
    assert item['kind']=='image' and item['mime']=='image/png'
    assert client.get('/api/attachments/'+item['id']+'/content').content==raw
    cid=client.post('/api/conversations',json={}).json()['id']
    result=client.post('/api/generate',json={'conversation':cid,'attachments':[item['id']]})
    assert result.status_code==400 and 'não aceita imagens' in result.text
    assert client.get('/api/conversations/'+cid).json()==[]
    assert client.post('/api/attachments?name=programa.exe',content=b'MZunsafe').status_code==400
    assert client.post('/api/attachments?name=image.png',content=b'not an image').status_code==400


def test_pdf_and_docx_are_extracted_without_executing_content(client):
    buffer=io.BytesIO();pdf=PdfWriter();pdf.add_blank_page(width=100,height=100);pdf.write(buffer)
    result=upload(client,'sem-texto.pdf',buffer.getvalue())
    assert 'OCR não está disponível' in result['warning']
    buffer=io.BytesIO()
    with ZipFile(buffer,'w') as z:
        z.writestr('word/document.xml','<w:document xmlns:w="urn:word"><w:body><w:p><w:r><w:t>Olá documento</w:t></w:r></w:p></w:body></w:document>')
    result=upload(client,'notas.docx',buffer.getvalue())
    with client.app.state.store.db() as db:
        assert 'Olá documento' in db.execute('SELECT text FROM attachments WHERE id=?',(result['id'],)).fetchone()[0]


def test_plan_and_access_policy_enforced_outside_model(tmp_path):
    project=tmp_path/'project';project.mkdir()
    (project/'readme.md').write_text('original')
    for name,args in [('write_file',{'path':'readme.md','content':'novo'}),('run_command',{'argv':['python','--version']})]:
        with pytest.raises(ValueError,match='Plan'):
            prepare_action(name,args,'agent','plan',str(project),True,'full')
    assert prepare_action('write_file',{'path':'readme.md','content':'novo'},'agent','build',str(project),True,'ask')['approval']
    assert not prepare_action('write_file',{'path':'readme.md','content':'novo'},'agent','build',str(project),True,'auto')['approval']
    assert prepare_action('read_file',{'path':'../outside.txt'},'agent','plan',str(project),False,'auto')['approval']
    assert prepare_action('read_file',{'path':'.env'},'agent','plan',str(project),False,'auto')['approval']
    assert not prepare_action('write_file',{'path':'../outside.txt','content':'novo'},'agent','build',str(project),False,'full')['approval']
    with pytest.raises(ValueError):prepare_action('web_fetch',{'url':'https://example.com'},'chat','build','',False,'full')


def test_writes_keep_revision_and_reject_stale_confirmation(tmp_path):
    project=tmp_path/'project';project.mkdir();target=project/'file.txt';target.write_text('antes')
    store=Store(tmp_path/'data');cid=store.conversation('Tarefa','agent');abort=asyncio.Event()
    action=prepare_action('write_file',{'path':'file.txt','content':'depois'},'agent','build',str(project),False,'ask')
    result=asyncio.run(execute_action(action,store,cid,abort))
    assert target.read_text()=='depois'
    with store.db() as db:
        assert db.execute('SELECT previous FROM agent_revisions WHERE id=?',(result['revision'],)).fetchone()[0]==b'antes'
    stale=prepare_action('write_file',{'path':'file.txt','content':'velho'},'agent','build',str(project),False,'ask')
    target.write_text('edicao do usuario')
    with pytest.raises(ValueError,match='mudou'):
        asyncio.run(execute_action(stale,store,cid,abort))
    assert target.read_text()=='edicao do usuario'


def test_commands_run_in_project_and_can_be_cancelled(tmp_path):
    async def check():
        event=asyncio.Event()
        result=await run_command([sys.executable,'-c','import os;print(os.getcwd())'],str(tmp_path),event)
        assert result['exit_code']==0 and str(tmp_path) in result['output']
        async def cancel():await asyncio.sleep(.2);event.set()
        task=asyncio.create_task(cancel())
        with pytest.raises(ValueError,match='interrompido'):
            await run_command([sys.executable,'-c','import time;time.sleep(20)'],str(tmp_path),event)
        await task
    asyncio.run(check())


def test_no_approval_or_abort_cannot_authorize_action():
    async def check():
        broker=ApprovalBroker();event=asyncio.Event();aid=broker.create({'name':'write_file'})
        event.set()
        assert await broker.wait(aid,event) is False
        assert not broker.pending
        with pytest.raises(ValueError):broker.decide(aid,True)
    asyncio.run(check())


def test_public_web_denies_loopback_private_and_mixed_dns(monkeypatch):
    async def check():
        loop=asyncio.get_running_loop()
        async def lookup(host,port,**kwargs):return [(2,1,6,'',('127.0.0.1',port))]
        monkeypatch.setattr(loop,'getaddrinfo',lookup)
        for value in ['http://localhost','https://example.com','http://169.254.169.254']:
            with pytest.raises(ValueError,match='locais'):await web.public_target(value)
        with pytest.raises(ValueError):await web.public_target('file:///etc/passwd')
        with pytest.raises(ValueError):await web.public_target('https://example.com:8765')
        async def public(host,port,**kwargs):return [(2,1,6,'',('1.1.1.1',port))]
        monkeypatch.setattr(loop,'getaddrinfo',public)
        url,sni,host=await web.public_target('https://example.com/path')
        assert url.host=='1.1.1.1' and sni=='example.com' and host=='example.com'
    asyncio.run(check())


@pytest.mark.parametrize('allow',[True,False])
def test_agent_loop_waits_for_consent_and_records_real_result(client,fake_engine,tmp_path,allow):
    handler=fake_engine[1];old_get=handler.do_GET;old_post=handler.do_POST
    def get(self):
        if self.path=='/api/extra/version':return self.send({'result':'CentralEngine','jinja':True})
        if self.path=='/props':return self.send({'modalities':{'vision':False},'chat_template_caps':{'supports_tools':True},'chat_template':'plain'})
        return old_get(self)
    def post(self):
        if self.path!='/v1/chat/completions':return old_post(self)
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        handler.payloads.append(('generate',data))
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        if data['messages'][-1]['role']=='tool':
            chunks=[{'choices':[{'delta':{'content':'Tarefa concluída.'},'finish_reason':'stop'}]}]
        else:
            chunks=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'call-write','type':'function','function':{'name':'write_file','arguments':json.dumps({'path':'novo.txt','content':'conteudo aprovado'})}}]},'finish_reason':'tool_calls'}]}]
        chunks.append({'choices':[],'usage':{'prompt_tokens':40,'completion_tokens':8}})
        for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n')
    handler.do_GET=get;handler.do_POST=post
    cid=client.post('/api/conversations',json={'kind':'agent','title':'Teste com ferramenta'}).json()['id']
    result={}
    thread=threading.Thread(target=lambda:result.update(response=client.post('/api/generate',json={'conversation':cid,'kind':'agent','content':'Crie novo.txt','workspace':str(tmp_path),'access':'ask'})))
    thread.start()
    try:
        for _ in range(1000):
            pending=dict(client.app.state.approvals.pending)
            if pending:break
            time.sleep(.01)
        else:raise AssertionError('Agente não solicitou aprovação')
        assert not (tmp_path/'novo.txt').exists()
        aid=next(iter(pending))
        assert client.post('/api/approvals/'+aid,json={'allow':allow}).status_code==200
        thread.join(timeout=10);assert not thread.is_alive()
        assert result['response'].status_code==200,result['response'].text
        assert (tmp_path/'novo.txt').exists() is allow
        if allow:assert (tmp_path/'novo.txt').read_text()=='conteudo aprovado'
        messages=client.get('/api/conversations/'+cid).json()
        assert messages[-1]['stats']['activities'][0]['status']==('done' if allow else 'denied')
        assert messages[-1]['stats']['generated_tokens']==16
        assert 'Tarefa concluída.' in messages[-1]['content']
        assert not client.get('/api/conversations').json()
        assert client.get('/api/conversations?kind=agent').json()[0]['id']==cid
    finally:
        client.post('/api/abort',json={})
        thread.join(timeout=10);handler.do_GET=old_get;handler.do_POST=old_post


def test_large_documents_can_be_consulted_without_inlining_everything(client):
    text='Introdução.\n'*500+'TOTAL ESPECIAL: 1523\n'+'Fim.\n'*500
    item=upload(client,'longo.txt',text.encode())
    cid=client.post('/api/conversations',json={}).json()['id']
    store=client.app.state.store;store.add_message(cid,'user','Analise',attachments=[item['id']])
    from backend.attachments import model_message
    message=model_message(store,store.messages(cid)[0])
    assert len(message['content'])<1600 and 'TOTAL ESPECIAL' not in message['content']
    action=prepare_action('search_attachment',{'id':item['id'],'query':'TOTAL ESPECIAL'},'chat','build','',False,'ask',[item['id']])
    assert not action['approval']
    result=asyncio.run(execute_action(action,store,cid,asyncio.Event()))
    assert '1523' in result['matches'][0]['text']
    other=store.conversation('Outra')
    with pytest.raises(ValueError,match='nesta conversa'):
        asyncio.run(execute_action(action,store,other,asyncio.Event()))


def test_web_redirects_revalidate_dns_and_private_targets(monkeypatch):
    import httpx
    real_client=httpx.AsyncClient
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):yield b'ok'
    def handler(request):
        return httpx.Response(302,headers={'Location':'http://127.0.0.1'},stream=Stream())
    def client_factory(**kwargs):
        kwargs['transport']=httpx.MockTransport(handler)
        return real_client(**kwargs)
    monkeypatch.setattr(web.httpx,'AsyncClient',client_factory)
    async def check():
        loop=asyncio.get_running_loop()
        async def lookup(host,port,**kwargs):return [(2,1,6,'',('127.0.0.1' if host=='127.0.0.1' else '1.1.1.1',port))]
        monkeypatch.setattr(loop,'getaddrinfo',lookup)
        with pytest.raises(ValueError,match='locais'):await web.read_public('https://example.com')
    asyncio.run(check())


def test_undo_restores_only_the_approved_revision(client,tmp_path):
    store=client.app.state.store;target=tmp_path/'undo.txt';target.write_text('original')
    cid=store.conversation('Undo','agent')
    action=prepare_action('write_file',{'path':'undo.txt','content':'alterado'},'agent','build',str(tmp_path),False,'ask')
    result=asyncio.run(execute_action(action,store,cid,asyncio.Event()))
    endpoint='/api/revisions/'+result['revision']+'/restore'
    assert client.post(endpoint,json={'confirmed':False}).status_code==422
    assert client.post(endpoint,json={'confirmed':True}).status_code==200
    assert target.read_text()=='original'
    assert client.post(endpoint,json={'confirmed':True}).status_code==400
    action=prepare_action('write_file',{'path':'undo.txt','content':'novo'},'agent','build',str(tmp_path),False,'ask')
    result=asyncio.run(execute_action(action,store,cid,asyncio.Event()))
    target.write_text('edicao posterior')
    assert client.post('/api/revisions/'+result['revision']+'/restore',json={'confirmed':True}).status_code==400
    assert target.read_text()=='edicao posterior'


def test_native_vision_payload_contract(client,fake_engine):
    handler=fake_engine[1];original=handler.do_GET
    def get(self):
        if self.path=='/api/extra/version':return self.send({'result':'CentralEngine','jinja':True})
        if self.path=='/props':return self.send({'modalities':{'vision':True},'chat_template_caps':{'supports_tools':False},'chat_template':'plain'})
        return original(self)
    handler.do_GET=get
    try:
        data=io.BytesIO();Image.new('RGB',(8,8),'blue').save(data,format='PNG')
        image=upload(client,'visao.png',data.getvalue())
        cid=client.post('/api/conversations',json={}).json()['id']
        response=client.post('/api/generate',json={'conversation':cid,'content':'Descreva a imagem','attachments':[image['id']]})
        assert response.status_code==200,response.text
        content=handler.payloads[-1][1]['messages'][-1]['content']
        assert content[0]['text']=='Descreva a imagem'
        assert content[1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    finally:handler.do_GET=original


def test_text_protocol_executes_only_valid_tool_json(client,fake_engine,tmp_path):
    handler=fake_engine[1];original=handler.do_POST
    def post(self):
        if self.path!='/v1/chat/completions':return original(self)
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        handler.payloads.append(('generate',data))
        last=data['messages'][-1]['content']
        reply='Leitura concluída.' if last.startswith('Resultado da ferramenta') else json.dumps({'tool':'list_files','arguments':{'path':'.'}})
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        chunks=[{'choices':[{'delta':{'content':reply},'finish_reason':'stop'}]}, {'choices':[],'usage':{'prompt_tokens':40,'completion_tokens':8}}]
        for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n')
    handler.do_POST=post
    try:
        (tmp_path/'marcador.txt').write_text('preservado')
        cid=client.post('/api/conversations',json={'kind':'agent'}).json()['id']
        response=client.post('/api/generate',json={'conversation':cid,'kind':'agent','agent_mode':'plan','content':'Liste arquivos','workspace':str(tmp_path)})
        assert response.status_code==200,response.text
        result=client.get('/api/conversations/'+cid).json()[-1]
        assert result['content']=='Leitura concluída.'
        assert result['stats']['activities'][0]['result']['entries']
        assert '"tool"' not in result['content']
    finally:handler.do_POST=original


def test_projectors_are_identified_and_cannot_start_as_text_models(client,tmp_path):
    import struct
    from test_central import gguf
    from backend.domain import Profile,build_command
    file=gguf(tmp_path/'mmproj.GGUF')
    file.write_bytes(file.read_bytes().replace(struct.pack('<Q',5)+b'qwen2',struct.pack('<Q',4)+b'clip'))
    settings=client.get('/api/bootstrap').json()['settings'];settings['folders']=[str(tmp_path)]
    assert client.put('/api/settings',json=settings).status_code==200
    model=client.get('/api/models').json()['models'][0]
    assert model['projector'] is True
    response=client.post('/api/engine/start',json={'path':str(file),'profile':Profile().model_dump()})
    assert response.status_code==400 and 'projetor' in response.text
    executable=tmp_path/'central-engine-nocuda';executable.write_bytes(b'fixture')
    command=build_command(executable,file,Profile(projector=str(file)),5001)
    assert command[command.index('--mmproj')+1]==str(file.resolve())
