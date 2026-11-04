"""Smoke/integracao sobre um binario REAL e GGUF aleatorio, sem modelo baixado.
Uso: python engine/tests/test_engine_http.py BINARIO FIXTURE.gguf
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import httpx
from backend.domain import Profile, build_command
from backend.engine import Engine
from backend.storage import Store

binary=Path(sys.argv[1]).resolve();model=Path(sys.argv[2]).resolve()
assert 'CentralEngine' in subprocess.check_output([binary,'--version'],text=True)
assert '--mmproj' in subprocess.check_output([binary,'--help'],text=True)
assert subprocess.run([binary,'--model',str(model),'--mmproj',str(model.parent/'missing-projector.gguf')],capture_output=True).returncode==2
for args in [['--host','0.0.0.0'],['--hf-repo','unwanted/repo'],['--tools','all'],['--gpulayers','1'],['--prompt-cache-mib','-1'],['--prompt-cache-mib','8193']]:
    assert subprocess.run([binary,*args],capture_output=True).returncode == 2
with tempfile.TemporaryDirectory() as directory:
    local_model=Path(directory)/'modelo de teste ç.GGUF'
    shutil.copyfile(model,local_model)
    store=Store(Path(directory)/'data')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    store.put('settings',{'engine_url':f'http://127.0.0.1:{port}','executable':str(binary),'folders':[str(model.parent)]})
    engine=Engine(store)
    profile=Profile(context=4096,max_output=2050,cache_kv='f16',flash_attention=False)
    # Malicious implicit upstream defaults must have no effect.
    old=os.environ.get('LLAMA_ARG_HOST');os.environ['LLAMA_ARG_HOST']='invalid-host-for-test'
    try: engine.start(str(local_model),profile)
    finally:
        if old is None: os.environ.pop('LLAMA_ARG_HOST',None)
        else: os.environ['LLAMA_ARG_HOST']=old
    try:
        async def check():
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                if engine.process.poll() is not None:
                    raise RuntimeError((store.directory/'engine.log').read_text(errors='replace'))
                status=await engine.status()
                if status['connected']:break
                await asyncio.sleep(.2)
            else: raise TimeoutError('Motor nao carregou')
            assert status['kind']=='central'
            assert status['vision'] is False
            assert status['capabilities']['version']=='0.3.0'
            assert status['context']==4096,status
            assert status['capabilities']['cpu_only'] is True
            diagnostic=await engine.json('/central/v1/status')
            assert diagnostic['engine']=='CentralEngine' and diagnostic['context']==4096
            _,on_limits=await engine.prepare([{'role':'user','content':'Teste'}],profile.model_copy(update={'thinking':'on'}))
            _,off_limits=await engine.prepare([{'role':'user','content':'Teste'}],profile.model_copy(update={'thinking':'off'}))
            assert on_limits['occupied_context'] > off_limits['occupied_context']
            # Repeated prompts must reuse real KV tokens; disabling bypasses reuse.
            cache_payload,_=await engine.prepare([{'role':'user','content':'cache de contexto '*30}],profile)
            cache_payload.update(max_tokens=3,temperature=0,logit_bias={'101':100,'2':-100,'0':-100})
            assert cache_payload['cache_prompt'] is True
            for _ in range(2):
                cached_chunks=[c async for c in engine.stream(cache_payload)]
            cached_usage=next(c['usage'] for c in cached_chunks if c.get('usage'))
            assert cached_usage['prompt_tokens_details']['cached_tokens']>0,cached_usage
            cache_payload['cache_prompt']=False
            uncached=[c async for c in engine.stream(cache_payload)]
            uncached_usage=next(c['usage'] for c in uncached if c.get('usage'))
            assert uncached_usage['prompt_tokens_details']['cached_tokens']==0,uncached_usage
            async with engine.client() as native_client:
                overflow=await native_client.post('/v1/chat/completions',json={'messages':[{'role':'user','content':'Teste '*5000}],'max_tokens':1,'stream':False})
                assert overflow.status_code==400,overflow.text
            print(json.dumps({'prompt_cache_reused_tokens':cached_usage['prompt_tokens_details']['cached_tokens'],'cache_disabled_tokens':0,'context_overflow_rejected':True}))
            payload,limits=await engine.prepare([{'role':'user','content':'Teste'}],profile)
            assert payload['repeat_penalty']==profile.repetition_penalty
            assert 'rep_pen' not in payload
            assert 0 < limits['occupied_context'] < 4096
            # Bias to an ASCII token to make random model output valid/observable.
            payload.update(temperature=0,logit_bias={'101':100,'2':-100,'0':-100})
            chunks=[c async for c in engine.stream(payload)]
            usage=next(c['usage'] for c in chunks if c.get('usage'))
            assert usage['completion_tokens']==2050,usage
            assert any(c.get('choices',[{}])[0].get('delta',{}).get('content') for c in chunks if c.get('choices'))
            assert any(c.get('choices',[{}])[0].get('finish_reason')=='length' for c in chunks if c.get('choices'))
            # Start a long request and cancel on the first delta. Closing HTTP must
            # cancel inference; a subsequent short request must complete.
            engine.request_key='our-generation';engine.cancelled=False;engine.abort_event.clear()
            payload['max_tokens']=3500
            got=False
            async for chunk in engine.stream(payload):
                if chunk.get('choices') and chunk['choices'][0].get('delta',{}).get('content'):
                    got=True
                    result=await engine.abort()
                    assert result['method']=='disconnect'
            assert got and engine.cancelled
            engine.request_key=None;engine.abort_event.clear();engine.cancelled=False
            payload['max_tokens']=3
            again=[c async for c in engine.stream(payload)]
            assert next(c['usage'] for c in again if c.get('usage'))['completion_tokens']==3
            print(json.dumps({'real_binary':True,'model':'random weights, not trained','loaded_context':status['context'],
                'generated_tokens':usage['completion_tokens'],'sse':True,'cancel_and_recover':True,'upstream_env_ignored':True}))
        asyncio.run(check())
    finally:
        engine.stop()
    assert engine.process.poll() is not None

    # Full Studio API -> owned native process -> SSE -> SQLite, not a mock engine.
    from fastapi.testclient import TestClient
    from backend.app import create_app
    with TestClient(create_app(Path(directory)/'studio')) as client:
        client.headers['X-Central-Token']=client.get('/api/bootstrap').json()['token']
        settings={'engine_url':f'http://127.0.0.1:{port}','executable':str(binary),'folders':[directory]}
        assert client.put('/api/settings',json=settings).status_code==200
        short_profile=profile.model_copy(update={'max_output':8}).model_dump()
        started=client.post('/api/engine/start',json={'path':str(local_model),'profile':short_profile})
        assert started.status_code==200,started.text
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            connected=client.get('/api/engine').json()
            if connected['connected']:break
            time.sleep(.2)
        else: raise TimeoutError('Studio nao conectou ao proprio motor')
        cid=client.post('/api/conversations',json={}).json()['id']
        reply=client.post('/api/generate',json={'conversation':cid,'content':'Teste real','profile':short_profile})
        assert reply.status_code==200 and 'event: done' in reply.text,reply.text
        messages=client.get('/api/conversations/'+cid).json()
        assert messages[-1]['role']=='assistant'
        assert messages[-1]['stats']['finish_reason'] in ['stop','length']
        assert messages[-1]['stats']['generated_tokens'] is not None
        assert client.post('/api/engine/stop',json={}).status_code==200
        print('Studio API -> processo Central Engine real -> SSE -> SQLite: passou.')
