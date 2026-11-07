import asyncio
import json
import pytest
import sqlite3
from test_central import client,fake_engine
from backend.extensions import catalog,change,tools_for,apply_skills
from backend.agent_tools import definitions,ApprovalBroker
from backend.domain import Profile
from backend.storage import Store
from backend.turns import run_turn
from backend.utility_tools import execute


def test_catalog_install_toggle_remove_persist_and_backup(client):
    items=client.get('/api/extensions').json()['items']
    assert len(items)==16 and sum(i['kind']=='plugin' for i in items)==8
    assert sum(i['installed'] for i in items)==4
    for action,installed,enabled in [('install',True,True),('disable',True,False),('enable',True,True),('remove',False,False)]:
        response=client.patch('/api/extensions/calculator',json={'action':action})
        assert response.status_code==200
        item=next(i for i in response.json()['items'] if i['id']=='calculator')
        assert (item['installed'],item['enabled'])==(installed,enabled)
        restored=Store(client.app.state.store.directory)
        assert next(i for i in catalog(restored) if i['id']=='calculator')['enabled']==enabled
    backup=client.post('/api/backup',json={}).json()['file']
    with sqlite3.connect(client.app.state.store.directory/backup) as db:
        assert json.loads(db.execute("SELECT value FROM settings WHERE key='extensions'").fetchone()[0])['calculator']=={'installed':False,'enabled':False}
    assert client.patch('/api/extensions/calculator',json={'action':'enable'}).status_code==400
    assert client.patch('/api/extensions/missing',json={'action':'install'}).status_code==400
    assert client.patch('/api/extensions/calculator',json={'action':'execute'}).status_code==422
    client.portal.call(client.app.state.engine.generation_lock.acquire)
    try:assert client.patch('/api/extensions/calculator',json={'action':'install'}).status_code==409
    finally:client.app.state.engine.generation_lock.release()


def test_plugin_gates_preserve_modes_and_internet(tmp_path):
    store=Store(tmp_path/'data')
    def names(mode='plan',internet=False):return {t['function']['name'] for t in tools_for(store,definitions('agent',mode,str(tmp_path),internet,True))}
    assert 'calculate' not in names() and 'web_search' not in names()
    change(store,'calculator','install');assert 'calculate' in names()
    change(store,'web','disable');assert 'web_search' not in names(internet=True)
    change(store,'web','enable');assert 'web_search' in names(internet=True)
    assert 'run_command' not in names() and 'write_file' not in names()
    assert 'run_command' in names('build')
    change(store,'terminal','remove');assert 'run_command' not in names('build')


def test_skills_enter_real_request_and_session(client,fake_engine):
    client.patch('/api/extensions/writing',json={'action':'install'})
    cid=client.post('/api/conversations',json={}).json()['id']
    response=client.post('/api/generate',json={'conversation':cid,'content':'Revise este texto','skills':['writing']})
    assert response.status_code==200 and 'event: done' in response.text
    payload=fake_engine[1].payloads[-1][1]
    assert 'Revise e redija em português brasileiro' in payload['messages'][0]['content']
    assert client.get('/api/system-prompt/'+cid).json()['options']['skills']==['writing']
    client.patch('/api/extensions/writing',json={'action':'disable'})
    response=client.post('/api/generate',json={'conversation':cid,'content':'Novo texto','skills':['writing']})
    assert response.status_code==400 and 'desativada' in response.text
    assert client.post('/api/generate',json={'conversation':cid,'content':'x','skills':['a','b','c','d']}).status_code==422


@pytest.mark.parametrize('installed',[False,True])
def test_tool_loop_cannot_execute_uninstalled_plugin(tmp_path,installed):
    store=Store(tmp_path/'data');cid=store.conversation('Cálculo')
    if installed:change(store,'calculator','install')
    tools=tools_for(store,definitions('chat','build','',True))
    class Engine:
        def __init__(self):self.abort_event=asyncio.Event();self.count=0
        async def stream(self,payload):
            self.count+=1
            if self.count==1:delta={'tool_calls':[{'index':0,'id':'calc','function':{'name':'calculate','arguments':'{"expression":"3 * 4"}'}}]}
            else:delta={'content':'Concluído'}
            yield {'choices':[{'delta':delta,'finish_reason':'stop'}],'usage':{'completion_tokens':8}}
        async def prepare(self,*args):return {'max_tokens':100},{}
    async def check():
        events=[event async for event in run_turn(Engine(),store,ApprovalBroker(),cid,[{'role':'user','content':'3*4'}],Profile(),{'max_tokens':100},tools,True,{'kind':'chat','agent_mode':'build','workspace':'','internet':True,'access':'ask'})]
        activity=[data for name,data in events if name=='activity'][-1]
        assert activity['status']==('done' if installed else 'error')
        if installed:assert activity['result']['result']==12
        else:assert 'não instalada' in activity['result']['error']
    asyncio.run(check())


@pytest.mark.parametrize('expression',['__import__("os").system("echo bad")','2 ** 999999','True','1/0','[1]*999999','1e309'])
def test_calculator_rejects_code_and_unbounded_numbers(expression):
    with pytest.raises(ValueError):execute('calculate',{'expression':expression})


def test_local_tools_produce_real_results():
    assert execute('calculate',{'expression':'(10 + 5) * 2 - 3'})['result']==27
    assert json.loads(execute('format_json',{'text':'{"a":[1,2]}'})['formatted'])=={'a':[1,2]}
    with pytest.raises(ValueError):execute('format_json',{'text':'{"a": NaN}'})
    result=execute('summarize_csv',{'text':'Fornecedor;Valor\nA;10,50\nB;-5\nC;2,50\nD;erro','column':'Valor','delimiter':';','decimal':',','exclude_negative':True})
    assert result['sum']=='13.00' and result['negative_excluded']==1 and result['invalid']==1 and result['used']==2
    assert execute('current_datetime',{})['utc'].endswith('+00:00')


def test_csv_decimal_precision_and_limits():
    args={'text':'Valor\n123456789012345678901234567890.12345678901234567890\n0.00000000000000000001','column':'Valor','delimiter':';','decimal':'.'}
    assert execute('summarize_csv',args)['sum']=='123456789012345678901234567890.12345678901234567891'
    args['text']='Valor\n1e-1000000\n2'
    result=execute('summarize_csv',args)
    assert result['invalid']==1 and result['sum']=='2'


def test_concurrent_changes_keep_both_updates(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    store=Store(tmp_path/'data');change(store,'calculator','install')
    original=store.get;barrier=threading.Barrier(2)
    def synchronized_read(key,default=None):
        value=original(key,default)
        if key=='extensions':barrier.wait(timeout=5)
        return value
    monkeypatch.setattr(store,'get',synchronized_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        disabled=pool.submit(change,store,'calculator','disable')
        installed=pool.submit(change,store,'clock','install')
        disabled.result(timeout=10);installed.result(timeout=10)
    monkeypatch.setattr(store,'get',original)
    state={item['id']:item for item in catalog(store)}
    assert state['calculator']['installed'] and not state['calculator']['enabled']
    assert state['clock']['installed'] and state['clock']['enabled']



def test_global_and_per_skill_automatic_settings_persist(client):
    from backend.extensions import automatic_skills
    client.patch('/api/extensions/writing',json={'action':'install'})
    assert client.get('/api/extensions/automation').json()['enabled']
    assert client.put('/api/extensions/automation',json={'enabled':False}).status_code==200
    assert not automatic_skills(client.app.state.store,[],True)
    client.put('/api/extensions/automation',json={'enabled':True})
    assert [i['id'] for i in automatic_skills(client.app.state.store,[],True)]==['writing']
    assert client.patch('/api/extensions/writing',json={'action':'auto_disable'}).status_code==200
    assert not automatic_skills(client.app.state.store,[],True)
    items=client.get('/api/extensions').json()['items']
    item=next(i for i in items if i['id']=='writing')
    assert item['installed'] and item['enabled'] and not item['automatic']
    assert apply_skills(client.app.state.store,[{'role':'user','content':'x'}],['writing'])
    client.patch('/api/extensions/writing',json={'action':'disable'})
    client.patch('/api/extensions/writing',json={'action':'enable'})
    assert not automatic_skills(client.app.state.store,[],True)
    client.patch('/api/extensions/writing',json={'action':'auto_enable'})
    assert automatic_skills(client.app.state.store,[],True)
