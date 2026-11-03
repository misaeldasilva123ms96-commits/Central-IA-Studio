import os
import asyncio
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from .domain import build_command, thinking_value

class Engine:
    def __init__(self, store):
        self.store = store
        self.process = None
        self.active_path = None
        self.launch_profile = None
        self.started = None
        self.log_handle = None
        self.request_key = None
        self.cancelled = False
        self.generation_lock = asyncio.Lock()
        self.lifecycle_lock = asyncio.Lock()

    @property
    def url(self):
        return self.store.get('settings',{}).get('engine_url','http://127.0.0.1:5001')

    def client(self):
        return httpx.AsyncClient(base_url=self.url, timeout=httpx.Timeout(15,read=180), trust_env=False, follow_redirects=False)

    async def json(self, path, payload=None):
        async with self.client() as client:
            r = await (client.get(path) if payload is None else client.post(path,json=payload))
            r.raise_for_status()
            return r.json()

    async def status(self):
        owned = self.process is not None and self.process.poll() is None
        result = {'connected':False,'owned':owned,'pid':self.process.pid if owned else None,
                  'active_path':self.active_path if owned else None,'launch_profile':self.launch_profile if owned else None}
        try:
            async with self.client() as client:
                paths = ['/api/extra/version','/api/v1/model','/api/extra/true_max_context_length']
                responses = await asyncio.gather(*(client.get(p,timeout=2) for p in paths))
                for r in responses:
                    r.raise_for_status()
                caps, model, ctx = [r.json() for r in responses]
            result.update(connected=True,capabilities=caps,model=model.get('result'),context=ctx.get('value'))
        except (httpx.HTTPError,ValueError,KeyError) as e:
            result['error'] = 'Motor indisponível: '+str(e)
        return result

    def start(self, model, profile):
        if self.process and self.process.poll() is None:
            raise ValueError('Pare o motor atual antes de trocar de modelo')
        settings = self.store.get('settings',{})
        if urlsplit(self.url).hostname == '::1':
            raise ValueError('Para iniciar o motor gerenciado, use 127.0.0.1 na conexão')
        port = urlsplit(self.url).port
        cmd = build_command(settings.get('executable',''), model, profile, port)
        with socket.socket() as probe:
            if os.name == 'nt':
                probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            else:
                probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:
                probe.bind(('127.0.0.1',port))
            except OSError:
                raise ValueError('Porta ocupada. Conecte ao motor existente ou configure outra porta.')
        self.log_handle = open(self.store.directory/'engine.log','ab',buffering=0)
        try:
            self.process = subprocess.Popen(cmd,stdout=self.log_handle,stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL,shell=False,cwd=str(Path(cmd[0]).parent))
        except Exception:
            self.log_handle.close()
            self.log_handle = None
            raise
        self.active_path = str(Path(model).resolve())
        self.launch_profile = profile.model_dump()
        self.started = time.monotonic()
        return {'pid':self.process.pid,'state':'iniciando','command':cmd}

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None
        self.active_path = None
        self.launch_profile = None

    async def abort(self):
        if not self.request_key:
            return {'interrupted':False}
        self.cancelled = True
        return await self.json('/api/extra/abort',{'genkey':self.request_key})

    async def prepare(self, messages, profile):
        status = await self.status()
        if not status['connected'] or not status.get('context'):
            raise ValueError('Conecte um KoboldCpp com modelo carregado antes de gerar')
        payload = {'messages':messages,'temperature':profile.temperature,'top_p':profile.top_p,
                   'top_k':profile.top_k,'min_p':profile.min_p,'rep_pen':profile.repetition_penalty,
                   'stream':True,'stream_options':{'include_usage':True}}
        thinking = thinking_value(profile)
        if thinking != 'default':
            if not status.get('capabilities',{}).get('jinja'):
                raise ValueError('Thinking explícito exige KoboldCpp iniciado com Jinja. O template também precisa aceitar enable_thinking.')
            payload['chat_template_kwargs'] = {'enable_thinking':thinking == 'on'}
            payload['reasoning_effort'] = 'none' if thinking == 'off' else 'high'
        tokens = await self.json('/api/extra/tokencount',payload)
        occupied = tokens.get('value',-1)
        if not isinstance(occupied,int) or occupied < 0:
            raise ValueError('Motor não forneceu contagem válida; geração não iniciada')
        context = min(int(status['context']),profile.context)
        # KoboldCpp reserva 20%/35% da janela para entrada (generate / calculate_min_remain_hardlimit).
        reserve = max(min(context-4,16),int(context*(.2 if occupied < context*.25 else .35)))
        effective = min(profile.max_output,context-occupied-8,context-reserve)
        if effective < 1:
            raise ValueError('Contexto esgotado. Reduza o histórico ou reinicie com contexto maior.')
        payload.update(max_tokens=effective,max_context_length=context)
        return payload, {'requested_output':profile.max_output,'effective_output':effective,
                         'allocated_context':status['context'],'request_context':context,'occupied_context':occupied,
                         'thinking_requested':thinking,'thinking_confirmed':False,
                         'warning':'Template deve aceitar enable_thinking; efeito requer validação real.' if thinking != 'default' else None,
                         'model':status.get('model')}

    async def stream(self, payload):
        async with self.client() as client:
            async with client.stream('POST','/v1/chat/completions',json=payload) as response:
                response.raise_for_status()
                data = []
                async for line in response.aiter_lines():
                    if line.startswith('data:'):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        raw = '\n'.join(data)
                        data = []
                        if raw == '[DONE]':
                            return
                        yield json.loads(raw)
                if data and '\n'.join(data) != '[DONE]':
                    yield json.loads('\n'.join(data))
