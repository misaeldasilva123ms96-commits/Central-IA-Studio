import asyncio
import json
import sqlite3
import time
from pathlib import Path
import pytest
from test_central import client,fake_engine
from backend.storage import Store
from backend.extensions import catalog,change
from backend.online_catalog import OnlineCatalog,source_parts
from backend.turns import run_turn
from backend.agent_tools import ApprovalBroker
from backend.domain import Profile


def test_message_time_migrates_without_fabricating_history(tmp_path):
    db=sqlite3.connect(tmp_path/'central.sqlite3')
    db.executescript("CREATE TABLE conversations(id TEXT PRIMARY KEY,title TEXT,created REAL); INSERT INTO conversations VALUES ('old','Old',100); CREATE TABLE messages(id INTEGER PRIMARY KEY,conversation TEXT,role TEXT,content TEXT,reasoning TEXT DEFAULT '',stats TEXT DEFAULT '{}'); INSERT INTO messages(conversation,role,content) VALUES ('old','user','Old question');")
    db.close()
    store=Store(tmp_path)
    assert store.messages('old')[0]['created'] is None
    before=time.time();store.add_message('old','assistant','New answer');after=time.time()
    assert before<=Store(tmp_path).messages('old')[1]['created']<=after
    with sqlite3.connect(store.backup()) as backup:assert backup.execute('SELECT created FROM messages WHERE id=2').fetchone()[0]>=before


def test_api_times_survive_edit_and_reload(client):
    cid=client.post('/api/conversations',json={}).json()['id'];before=time.time()
    client.post('/api/generate',json={'conversation':cid,'content':'Horário'})
    messages=client.get('/api/conversations/'+cid).json()
    assert len(messages)==2 and before<=messages[0]['created']<=messages[1]['created']<=time.time()
    mid=messages[0]['id'];created=messages[0]['created']
    assert client.patch('/api/messages/'+str(mid),json={'content':'Editada'}).status_code==200
    assert Store(client.app.state.store.directory).messages(cid)[0]['created']==created


def test_preinstalled_basics_preserve_user_removals(tmp_path):
    store=Store(tmp_path)
    assert all(i['installed'] and i['enabled'] for i in catalog(store))
    change(store,'writing','remove');change(store,'clock','disable')
    restored={i['id']:i for i in catalog(Store(tmp_path))}
    assert not restored['writing']['installed'] and not restored['clock']['enabled']


def test_plain_fallback_streams_before_engine_finishes(tmp_path):
    class Engine:
        abort_event=asyncio.Event()
        finished=False
        async def stream(self,payload):
            yield {'choices':[{'delta':{'content':'Olá'}}]}
            self.finished=True
            yield {'choices':[{'delta':{'content':' mundo'},'finish_reason':'stop'}],'usage':{'completion_tokens':2},'timings':{'predicted_per_second':3.5}}
    async def check():
        engine=Engine();store=Store(tmp_path)
        events=run_turn(engine,store,ApprovalBroker(),'test',[],Profile(),{'max_tokens':50},[{'function':{'name':'calculate'}}],False,{})
        event=await anext(events)
        assert not engine.finished and event[1]['choices'][0]['delta']['content']=='Olá'
        rest=[e async for e in events]
        assert rest[-1][1]['timings']['predicted_per_second']==3.5
        assert ''.join(c.get('delta',{}).get('content','') for _,chunk in [event]+rest for c in chunk.get('choices',[]))=='Olá mundo'
    asyncio.run(check())


@pytest.mark.parametrize('url',['http://github.com/a/b','https://github.com.evil/a/b','https://u:p@github.com/a/b','https://github.com/a/b/tree/main/../x','https://localhost/a/b','https://github.com/a/b?token=secret'])
def test_online_sources_reject_nonpublic_locations(url):
    with pytest.raises(ValueError):source_parts(url)


def fake_github(monkeypatch):
    sha='a'*40;tree='b'*40
    skill=b'---\nname: Example skill\ndescription: A real package fixture\n---\nRead references/guide.md when needed.'
    async def fetch(self,client,url,limit):
        if '/commits/' in url:return json.dumps({'sha':sha,'commit':{'tree':{'sha':tree}}}).encode()
        if '/git/trees/' in url:return json.dumps({'tree':[{'path':'skills/example/SKILL.md','mode':'100644','type':'blob','size':len(skill)},{'path':'skills/example/references/guide.md','mode':'100755','type':'blob','size':5}]}).encode()
        assert '/'+sha+'/' in url
        if url.endswith('/SKILL.md'):return skill
        if url.endswith('/guide.md'):return b'Guide'
        raise AssertionError(url)
    monkeypatch.setattr(OnlineCatalog,'fetch',fetch)


def test_online_preview_installs_reviewed_pinned_resources(client,monkeypatch):
    fake_github(monkeypatch);url='https://github.com/example/skills/tree/main/skills'
    response=client.post('/api/extensions/online/browse',json={'url':url})
    assert response.status_code==200
    row=response.json()['items'][0]
    preview=client.post('/api/extensions/online/preview',json={'url':url,'key':row['id']}).json()
    assert preview['file_count']==2 and preview['entry']['commit']=='a'*40
    assert client.post('/api/extensions/online/install',json={'ticket':preview['ticket'],'digest':'wrong'}).status_code==400
    install=client.post('/api/extensions/online/install',json={'ticket':preview['ticket'],'digest':preview['digest']})
    assert install.status_code==200
    item=next(i for i in install.json()['items'] if i['id']==install.json()['id'])
    assert item['source']==row['url'] and item['installed']
    with client.app.state.store.db() as db:
        assert db.execute('SELECT mode FROM extension_files WHERE package=? AND path=?',(item['id'],'references/guide.md')).fetchone()[0]==0o700
    # Reusing the reviewed package reactivates the existing installation, without duplicates.
    again=client.post('/api/extensions/online/install',json={'ticket':preview['ticket'],'digest':preview['digest']}).json()
    assert again['id']==item['id']
    assert url in client.get('/api/extensions/sources').json()['custom']
