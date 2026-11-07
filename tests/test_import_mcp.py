import asyncio
from contextlib import contextmanager
import io
import json
from pathlib import Path
import socket
import stat
import subprocess
import sys
import threading
import time
from zipfile import ZipFile,ZipInfo
import pytest
from test_central import client,fake_engine
from backend.extensions import catalog,apply_skills,change,resource_definition
from backend.import_packages import read_package,install_package,materialize,read_resource
from backend.mcp_bridge import MCPBridge,validate_config,tool_alias
from backend.storage import Store

FIXTURE=Path(__file__).parent/'fixtures/mcp_server.py'
SKILL=b'---\nname: external-review\ndescription: Review a project with supporting references.\n---\nRead references/checklist.md before reviewing. Never invent test execution.\n'


def package(legacy=False):
    out=io.BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('demo/.codex-plugin/plugin.json' if legacy else 'demo/plugin.json',json.dumps({'name':'demo-plugin','description':'Imported test package','version':'1.2.0','skills':'./skills/'}))
        z.writestr('demo/skills/review/SKILL.md',SKILL)
        z.writestr('demo/skills/review/references/checklist.md','Check inputs and errors.')
        z.writestr('demo/.mcp.json' if legacy else 'demo/mcp.json',json.dumps({'mcpServers':{'fixture':{'type':'stdio','command':sys.executable,'args':[str(FIXTURE)]}}}))
    return out.getvalue()


@pytest.mark.parametrize('legacy',[False,True])
def test_portable_and_codex_packages_preserve_skills_resources_and_servers(tmp_path,legacy):
    store=Store(tmp_path/'data');doc=read_package(package(legacy),'plugin.zip')
    key=install_package(store,doc)
    imported=[i for i in catalog(store) if not i['bundled']]
    assert len(imported)==2 and doc['servers'][0]['config']['transport']=='stdio'
    skill=next(i for i in imported if i['kind']=='skill')
    assert read_resource(store,skill['id'],'references/checklist.md',0)['text']=='Check inputs and errors.'
    messages=apply_skills(store,[{'role':'user','content':'Review'}],[skill['id']])
    assert 'Read references/checklist.md' in messages[0]['content']
    assert Path(materialize(store,key),'skills/review/SKILL.md').read_bytes()==SKILL
    with pytest.raises(ValueError):read_resource(store,skill['id'],'../SKILL.md',0)
    change(store,key,'disable')
    with pytest.raises(ValueError):apply_skills(store,[{'role':'user','content':'x'}],[skill['id']])
    assert not resource_definition(store,[skill['id']])
    assert not MCPBridge(store).servers()[0]['connected']


def test_import_requires_preview_digest_and_has_no_execution(client):
    data=package();preview=client.post('/api/extensions/import?name=plugin.zip',content=data).json()
    assert preview['name']=='demo-plugin' and len(preview['servers'])==1
    assert client.get('/api/mcp').json()['servers']==[]
    assert client.post('/api/extensions/import?name=plugin.zip&confirm=true',content=data).status_code==400
    result=client.post('/api/extensions/import?name=plugin.zip&confirm=true',content=data,headers={'X-Import-Digest':preview['digest']})
    assert result.status_code==200,result.text
    assert len(result.json()['servers'])==1 and not result.json()['servers'][0]['connected']


@pytest.mark.parametrize('path',['../escape','/absolute','C:/evil','folder\\evil','CON.txt','a/../b','foo.'])
def test_zip_rejects_unsafe_cross_platform_paths(path):
    out=io.BytesIO()
    with ZipFile(out,'w') as z:z.writestr(path,b'x')
    with pytest.raises(ValueError):read_package(out.getvalue(),'bad.zip')


def test_zip_rejects_symlinks_and_yaml_objects():
    out=io.BytesIO();entry=ZipInfo('link');entry.external_attr=(stat.S_IFLNK|0o777)<<16
    with ZipFile(out,'w') as z:z.writestr(entry,b'../elsewhere')
    with pytest.raises(ValueError):read_package(out.getvalue(),'bad.zip')
    for raw in [b'---\nname: &a test\ndescription: *a\n---\nbody',b'---\nname: !!python/object:os.system {}\ndescription: x\n---\nbody']:
        with pytest.raises(ValueError):read_package(raw,'SKILL.md')


def test_config_requires_references_and_safe_transport():
    assert validate_config({'type':'streamable-http','url':'https://example.com/mcp','headers':{'Authorization':'Bearer ${TOKEN}'}})['transport']=='http'
    with pytest.raises(ValueError):validate_config({'transport':'http','url':'http://example.com/mcp'})
    with pytest.raises(ValueError):validate_config({'command':'python','env':{'API_TOKEN':'literal-secret'}})


@contextmanager
def server_config(transport):
    if transport=='stdio':yield {'transport':'stdio','command':sys.executable,'args':[str(FIXTURE)]};return
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    process=subprocess.Popen([sys.executable,str(FIXTURE),'--http',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(200):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.05)
        else:raise AssertionError('MCP HTTP fixture did not start')
        yield {'transport':'http','url':f'http://127.0.0.1:{port}/mcp'}
    finally:process.terminate();process.wait(timeout=10)


@pytest.mark.parametrize('transport',['stdio','http'])
def test_real_mcp_discovery_selection_call_modes_and_cleanup(tmp_path,transport):
    async def check(config):
        bridge=MCPBridge(Store(tmp_path/'data'));key=bridge.save('Fixture',config)
        try:
            if transport=='http':
                with pytest.raises(ValueError):await bridge.connect(key)
            await bridge.connect(key,{'token':'test-session-only','env':{'PRIVATE_MCP_TOKEN':'another-session-only'},'headers':{}})
            assert bridge.servers()[0]['connected']
            assert not bridge.definitions('chat','build',True)
            bridge.select(key,['sum_values'])
            defs=bridge.definitions('chat','build',True);assert len(defs)==1
            assert not bridge.definitions('agent','plan',True)
            if transport=='http':assert not bridge.definitions('chat','build',False)
            options={'kind':'agent','agent_mode':'build','internet':True,'access':'ask'}
            action=bridge.prepare(defs[0]['function']['name'],{'x':19,'y':23},options)
            assert action['approval']
            result=await bridge.call(action,asyncio.Event())
            assert (result.get('structuredContent') or json.loads(result['content'][0]['text']))['total']==42
            if transport=='stdio':
                bridge.select(key,['credential_present'])
                credential=bridge.prepare(tool_alias(key,'credential_present'),{},options)
                present=await bridge.call(credential,asyncio.Event())
                assert json.loads(present['content'][0]['text'])['present']
            assert 'test-session-only' not in json.dumps(bridge.servers())
            assert 'another-session-only' not in bridge.store.path.read_bytes().decode(errors='ignore')
        finally:await bridge.close()
        assert not bridge.connections
    with server_config(transport) as config:asyncio.run(check(config))


def test_real_stdio_stop_cancels_session_and_process(tmp_path):
    async def check():
        bridge=MCPBridge(Store(tmp_path/'data'));key=bridge.save('Stop',{'command':sys.executable,'args':[str(FIXTURE)]})
        await bridge.connect(key);bridge.select(key,['wait_for_stop'])
        action=bridge.prepare(tool_alias(key,'wait_for_stop'),{}, {'kind':'agent','agent_mode':'build','internet':False,'access':'full'})
        abort=asyncio.Event();task=asyncio.create_task(bridge.call(action,abort));await asyncio.sleep(.15);abort.set()
        with pytest.raises(ValueError,match='interrompida'):await asyncio.wait_for(task,8)
        assert not bridge.connections
    asyncio.run(check())


def test_mcp_generation_waits_for_approval_and_keeps_timeline(client,fake_engine):
    added=client.post('/api/mcp',json={'name':'Fixture','config':{'command':sys.executable,'args':[str(FIXTURE)]}}).json();key=added['id']
    assert client.post('/api/mcp/'+key+'/connect',json={}).status_code==422
    connected=client.post('/api/mcp/'+key+'/connect',json={'confirmed':True});assert connected.status_code==200,connected.text
    assert client.put('/api/mcp/'+key+'/tools',json={'names':['sum_values']}).status_code==200
    handler=fake_engine[1];old_get=handler.do_GET;old_post=handler.do_POST
    def get(self):
        if self.path=='/api/extra/version':return self.send({'result':'CentralEngine','jinja':True})
        if self.path=='/props':return self.send({'modalities':{'vision':False},'chat_template_caps':{'supports_tools':True},'chat_template':'plain'})
        return old_get(self)
    def post(self):
        if self.path!='/v1/chat/completions':return old_post(self)
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        if data['messages'][-1]['role']=='tool':delta={'content':'Resultado consultado.'}
        else:delta={'content':'Vou consultar a ferramenta.','tool_calls':[{'index':0,'id':'mcp-call','function':{'name':tool_alias(key,'sum_values'),'arguments':'{"x":6,"y":7}'}}]}
        for chunk in [{'choices':[{'delta':delta,'finish_reason':'stop'}]},{'choices':[],'usage':{'completion_tokens':8}}]:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n')
    handler.do_GET=get;handler.do_POST=post
    cid=client.post('/api/conversations',json={}).json()['id'];result={}
    thread=threading.Thread(target=lambda:result.update(response=client.post('/api/generate',json={'conversation':cid,'content':'Some 6 e 7'})))
    thread.start()
    try:
        for _ in range(1000):
            pending=dict(client.app.state.approvals.pending)
            if pending:break
            time.sleep(.01)
        else:raise AssertionError('MCP did not request consent')
        assert thread.is_alive()
        assert client.post('/api/approvals/'+next(iter(pending)),json={'allow':True}).status_code==200
        thread.join(timeout=15);assert not thread.is_alive()
        assert 'event: done' in result['response'].text
        message=client.get('/api/conversations/'+cid).json()[-1]
        data=message['stats']['activities'][0]['result']
        assert (data.get('structuredContent') or json.loads(data['content'][0]['text']))['total']==13
        assert [b['type'] for b in message['stats']['timeline']]==['text','activity','text']
    finally:
        client.post('/api/abort',json={});thread.join(timeout=10)
        handler.do_GET=old_get;handler.do_POST=old_post


def test_implicit_policy_and_skill_dependencies_are_imported(tmp_path):
    out=io.BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('SKILL.md',SKILL)
        z.writestr('agents/openai.yaml','policy:\n  allow_implicit_invocation: false\ndependencies:\n  tools:\n    - type: mcp\n      value: docs\n      transport: streamable_http\n      url: https://example.com/mcp\n')
    store=Store(tmp_path/'data');doc=read_package(out.getvalue(),'skill.zip');key=install_package(store,doc)
    from backend.extensions import automatic_skills
    assert not next(i for i in catalog(store) if i['id']==key)['implicit']
    assert not automatic_skills(store,[],True)
    assert apply_skills(store,[{'role':'user','content':'x'}],[key])
    assert MCPBridge(store).servers()[0]['config']['url']=='https://example.com/mcp'


def test_imported_script_requires_build_and_approval_before_real_execution(tmp_path):
    from backend.import_packages import prepare_script
    from backend.agent_tools import run_command
    out=io.BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('SKILL.md',SKILL)
        z.writestr('scripts/run.py','from pathlib import Path\nimport os\nPath("skill-output.txt").write_text("SCRIPT_OK")\nprint(os.environ["SKILL_ROOT"])\n')
    store=Store(tmp_path/'data');key=install_package(store,read_package(out.getvalue(),'skill.zip'))
    project=tmp_path/'project';project.mkdir()
    options={'kind':'agent','agent_mode':'build','workspace':str(project),'internet':False,'access':'ask'}
    args={'id':key,'path':'scripts/run.py'}
    action=prepare_script(store,args,options)
    assert action['approval'] and not (project/'skill-output.txt').exists()
    assert json.loads(action['summary'].split(' · ',1)[1])==action['script_argv'] and 'run.py' in action['summary']
    assert not resource_definition(store,[key],'agent','plan',str(project))[0]['function']['name']=='run_skill_script'
    with pytest.raises(ValueError):prepare_script(store,args,options|{'agent_mode':'plan'})
    result=asyncio.run(run_command(action['script_argv'],action['cwd'],asyncio.Event(),action['script_env']))
    assert result['exit_code']==0 and (project/'skill-output.txt').read_text()=='SCRIPT_OK'


@pytest.mark.parametrize('native',[True,False])
def test_model_can_load_relevant_skill_then_read_its_reference(tmp_path,native):
    from backend.extensions import automatic_skills,activation_definition
    from backend.agent_tools import ApprovalBroker
    from backend.domain import Profile
    from backend.turns import run_turn
    store=Store(tmp_path/'data');install_package(store,read_package(package(),'plugin.zip'))
    key=next(i['id'] for i in catalog(store) if i['kind']=='skill' and not i['bundled'])
    eligible=automatic_skills(store,[],True)
    tools=activation_definition(eligible)+resource_definition(store,[key])
    messages=[{'role':'user','content':'Review'}]
    class Engine:
        def __init__(self):self.abort_event=asyncio.Event();self.step=0
        async def stream(self,payload):
            self.step+=1
            if self.step<=2:
                name='load_skill' if self.step==1 else 'read_skill_resource'
                arguments={'id':key} if self.step==1 else {'id':key,'path':'references/checklist.md'}
                delta={'tool_calls':[{'index':0,'id':str(self.step),'function':{'name':name,'arguments':json.dumps(arguments)}}]} if native else {'content':json.dumps({'tool':name,'arguments':arguments})}
            else:delta={'content':'Review based on the reference.'}
            yield {'choices':[{'delta':delta,'finish_reason':'stop'}],'usage':{'completion_tokens':8}}
        async def prepare(self,*args):return {'max_tokens':100},{}
    async def check():
        options={'kind':'chat','agent_mode':'build','workspace':'','internet':False,'access':'ask','skills':[],'eligible_skills':[key],'loaded_skills':[]}
        events=[event async for event in run_turn(Engine(),store,ApprovalBroker(),'unused',messages,Profile(),{'max_tokens':100},tools,native,options)]
        finished=[data for event,data in events if event=='activity' and data['status']=='done']
        assert len(finished)==2 and finished[1]['result']['text']=='Check inputs and errors.'
        assert options['loaded_skills']==[key]
    asyncio.run(check())


def test_shipped_example_import_and_real_mcp_call(tmp_path):
    example=Path(__file__).parents[1]/'frontend/public/central-demo-plugin.zip'
    store=Store(tmp_path/'data');key=install_package(store,read_package(example.read_bytes(),example.name))
    async def check():
        bridge=MCPBridge(store);server=bridge.servers()[0]
        # Use this test environment's Python, while the distributable example uses PATH.
        with store.db() as db:
            cfg=server['config']|{'command':sys.executable}
            db.execute('UPDATE mcp_servers SET config=? WHERE id=?',(json.dumps(cfg),server['id']))
        try:
            await bridge.connect(server['id']);bridge.select(server['id'],['demo_sum'])
            action=bridge.prepare(tool_alias(server['id'],'demo_sum'),{'a':12,'b':30},{'kind':'chat','agent_mode':'build','internet':False,'access':'full'})
            result=await bridge.call(action,asyncio.Event())
            assert json.loads(result['content'][0]['text'])['total']==42
        finally:await bridge.close()
    asyncio.run(check())
