import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from test_central import client,fake_engine
from backend.context_memory import RULES,fingerprint,valid_checkpoint
from backend.domain import MODE_PRESETS,Profile
from backend.extensions import catalog,change
from backend.storage import Store

SUMMARY='Projeto Alpha: manter valores não negativos. Arquivo fornecedores.py. Próximo passo: validar os testes.'


def install_memory_handler(handler,gate=None,started=None):
    original=handler.do_POST
    def post(self):
        if self.path not in ('/api/extra/tokencount','/v1/chat/completions'):return original(self)
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        handler.payloads.append(('count' if self.path=='/api/extra/tokencount' else 'generate',data))
        count=max(1,len(json.dumps(data['messages'],ensure_ascii=False))//4)
        if self.path=='/api/extra/tokencount':return self.send({'value':count})
        assert count+data['max_tokens']+8<=data['max_context_length'],data
        summary=data['messages'][0]['content']==RULES
        if summary and started:started.set()
        if summary and gate and not gate.wait(10):raise TimeoutError('Summary gate expired')
        text=SUMMARY if summary else 'Resposta final com memória.'
        chunks=[{'choices':[{'delta':{'content':text},'finish_reason':'stop'}]}, {'choices':[],'usage':{'prompt_tokens':count,'completion_tokens':20}}]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        try:
            for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):pass
    handler.do_POST=post
    return original


def seed_memory_case(store):
    for item in catalog(store):change(store,item['id'],'disable')
    cid=store.conversation('Conversa com histórico')
    for i in range(4):
        store.add_message(cid,'user',f'Projeto Alpha: pergunta {i}. '+('Detalhes de fornecedores positivos e negativos. '*25))
        store.add_message(cid,'assistant',f'Decisão {i}: manter valores não negativos em fornecedores.py. '+('Preservar os dados e validar os testes. '*25))
    return cid


@pytest.mark.parametrize('mode',list(MODE_PRESETS))
def test_presets_apply_real_parameters_and_keep_hardware(client,fake_engine,mode):
    original=Profile(context=8192,threads=4,cache_kv='f16',auto_compact=False).model_dump()
    response=client.post('/api/profiles/preset',json={'mode':mode,'profile':original})
    assert response.status_code==200
    saved=response.json()
    assert saved['mode']==mode and all(saved[k]==v for k,v in MODE_PRESETS[mode]['values'].items())
    assert saved['context']==8192 and saved['threads']==4 and saved['cache_kv']=='f16' and not saved['auto_compact']
    assert client.put('/api/profiles',json=saved).status_code==200
    assert client.get('/api/profiles').json()==saved
    cid=client.post('/api/conversations',json={}).json()['id']
    assert client.post('/api/generate',json={'conversation':cid,'content':'Teste do modo','profile':saved}).status_code==200
    sent=next(d for kind,d in reversed(fake_engine[1].payloads) if kind=='generate')
    for field in ['temperature','top_p','top_k','min_p']:assert sent[field]==saved[field]
    assert sent['max_tokens']==saved['max_output'] and sent['rep_pen']==saved['repetition_penalty']


def test_compaction_fits_request_keeps_originals_and_reuses_checkpoint(client,fake_engine):
    store=client.app.state.store;cid=seed_memory_case(store);before=store.messages(cid);install_memory_handler(fake_engine[1])
    profile=Profile(context=2048,max_output=768,compact_keep_turns=2).model_dump()
    response=client.post('/api/generate',json={'conversation':cid,'content':'Continue o projeto','profile':profile})
    assert response.status_code==200 and 'event: done' in response.text,response.text
    history=store.messages(cid);info=history[-1]['stats']['compaction']
    assert info['new'] and info['after_tokens']<info['before_tokens']
    assert history[-1]['stats']['total_elapsed']>=history[-1]['stats']['elapsed']
    assert [(m['id'],m['content']) for m in history[:len(before)]]==[(m['id'],m['content']) for m in before]
    checkpoint=client.get('/api/conversations/'+cid+'/context').json()['memory']
    assert checkpoint['summary']==SUMMARY and checkpoint['covered_messages']==6
    generated=[d for kind,d in fake_engine[1].payloads if kind=='generate']
    assert sum(d['messages'][0]['content']==RULES for d in generated)>=2
    final=generated[-1]
    assert SUMMARY in final['messages'][1]['content'] and final['messages'][-1]['content']=='Continue o projeto'
    assert 'pergunta 3' in json.dumps(final['messages'],ensure_ascii=False)
    assert not final.get('tools') and final['max_tokens']>0
    restored=Store(store.directory)
    assert valid_checkpoint(restored,cid,restored.messages(cid))
    with __import__('sqlite3').connect(store.backup()) as db:assert db.execute('SELECT value FROM settings WHERE key=?',('context:'+cid,)).fetchone()
    count=len([d for kind,d in fake_engine[1].payloads if kind=='generate'])
    assert client.post('/api/generate',json={'conversation':cid,'content':'Mais uma pergunta','profile':profile}).status_code==200
    new=[d for kind,d in fake_engine[1].payloads if kind=='generate'][count:]
    assert len(new)==1 and SUMMARY in json.dumps(new[0]['messages'],ensure_ascii=False)
    assert client.patch('/api/messages/'+str(before[0]['id']),json={'content':'Mudei o objetivo original'}).status_code==200
    assert client.get('/api/conversations/'+cid+'/context').json()['memory'] is None
    assert len(store.messages(cid))==len(before)+4


def test_disabled_compaction_rejects_overflow_without_mutating_history(client,fake_engine):
    store=client.app.state.store;cid=seed_memory_case(store);before=store.messages(cid);install_memory_handler(fake_engine[1])
    response=client.post('/api/generate',json={'conversation':cid,'content':'Continue','profile':Profile(context=2048,auto_compact=False).model_dump()})
    assert response.status_code==400 and 'Contexto esgotado' in response.text
    assert store.messages(cid)==before and not store.get('context:'+cid)
    assert not any(kind=='generate' for kind,_ in fake_engine[1].payloads)


def test_compaction_cancellation_preserves_history_and_releases_lock(client,fake_engine):
    store=client.app.state.store;cid=seed_memory_case(store);before=store.messages(cid)
    gate=threading.Event();started=threading.Event();install_memory_handler(fake_engine[1],gate,started)
    with ThreadPoolExecutor() as pool:
        pending=pool.submit(client.post,'/api/generate',json={'conversation':cid,'content':'Continue','profile':Profile(context=2048).model_dump()})
        try:
            assert started.wait(8)
            assert client.get('/api/conversations/'+cid+'/context').json()['job']['stage']=='compacting'
            assert client.post('/api/abort',json={}).status_code==200
        finally:gate.set()
        response=pending.result(timeout=10)
    assert response.status_code==400 and 'interrompida' in response.text
    assert store.messages(cid)==before and not store.get('context:'+cid)
    assert not client.app.state.engine.generation_lock.locked()


def test_memory_reset_and_delete_preserve_history(client,fake_engine):
    store=client.app.state.store;cid=seed_memory_case(store);install_memory_handler(fake_engine[1])
    assert client.post('/api/generate',json={'conversation':cid,'content':'Continue','profile':Profile(context=2048).model_dump()}).status_code==200
    original=store.messages(cid)
    assert client.delete('/api/conversations/'+cid+'/context').status_code==200
    assert store.messages(cid)==original and not store.get('context:'+cid)
    store.put('context:'+cid,{'example':True})
    assert client.delete('/api/conversations/'+cid).status_code==200
    assert store.get('context:'+cid) is None


def test_summary_failure_never_replaces_originals(client,fake_engine):
    store=client.app.state.store;cid=seed_memory_case(store);before=store.messages(cid)
    # Original fixture deliberately returns finish_reason=length, which cannot become a checkpoint.
    fake_engine[1].prompt_tokens=1900
    response=client.post('/api/generate',json={'conversation':cid,'content':'Continue','profile':Profile(context=2048).model_dump()})
    assert response.status_code==400
    assert store.messages(cid)==before and not store.get('context:'+cid)
    assert not client.app.state.engine.generation_lock.locked()


def test_undo_changes_invalidate_memory_and_current_turn_is_not_compacted(tmp_path):
    from backend.context_memory import inject_memory,old_turn_boundary
    store=Store(tmp_path);cid=store.conversation('Undo')
    store.add_message(cid,'user','Faça um arquivo')
    mid=store.add_message(cid,'assistant','Criado',stats={'activities':[{'name':'write_file','status':'done','result':{'path':'a.py','restored':False}}]})
    old=store.messages(cid);store.put('context:'+cid,{'version':1,'summary':'a.py criado','covered_messages':2,'fingerprint':fingerprint(old)})
    with store.db() as db:
        stats=old[-1]['stats'];stats['activities'][0]['result']['restored']=True
        db.execute('UPDATE messages SET stats=? WHERE id=?',(json.dumps(stats),mid))
    assert valid_checkpoint(store,cid,store.messages(cid)) is None
    messages=[{'role':'system','content':'As instruções atuais valem.'},{'role':'user','content':'Antiga'},{'role':'assistant','content':'Antiga resposta'},{'role':'user','content':[{'type':'text','text':'Pergunta atual'},{'type':'image_url','image_url':{'url':'data:image/png;base64,AAA'}}]}]
    new=inject_memory(messages,2,'Resumo não confiável')
    assert new[0]==messages[0] and len(new)==2 and new[1]['role']=='user'
    assert new[1]['content'][-1]==messages[-1]['content'][-1]
    assert messages[-1]['content'][0]['text']=='Pergunta atual'  # no mutation
    assert old_turn_boundary([{'role':'user'},{'role':'assistant'}],1,True)==2
