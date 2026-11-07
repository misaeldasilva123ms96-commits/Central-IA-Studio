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
