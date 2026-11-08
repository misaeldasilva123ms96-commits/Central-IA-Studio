"""Real Studio UI/API with a gated HTTP model fixture: ordered work and final answer."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import uvicorn
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from backend.app import create_app
from backend.storage import Store
spec=importlib.util.spec_from_file_location('work_fixtures',ROOT/'tests/test_central.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
fake=fixtures.fake_engine.__wrapped__();url,handler=next(fake)
old_get,old_post=handler.do_GET,handler.do_POST
reasoning_gate=threading.Event();answer_gate=threading.Event();finish_gate=threading.Event()

def get(self):
    if self.path=='/api/extra/version':return self.send({'result':'CentralEngine','version':'work-fixture','jinja':True})
    if self.path=='/props':return self.send({'chat_template_caps':{'supports_tools':True},'chat_template':'plain'})
    return old_get(self)

def post(self):
    if self.path!='/v1/chat/completions':return old_post(self)
    data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));handler.payloads.append(('generate',data))
    last=data['messages'][-1]
    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
    def emit(delta,finish=None):
        chunk={'choices':[{'delta':delta,'finish_reason':finish}]}
        self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
    try:
        if last['role']=='tool':
            emit({'reasoning_content':'A ferramenta retornou 42. Vou preparar a resposta.'})
            if not answer_gate.wait(40):raise TimeoutError('Answer gate')
            emit({'content':'O resultado é 42.'})
            if not finish_gate.wait(40):raise TimeoutError('Finish gate')
            emit({},'stop')
        elif last.get('content')=='ola':emit({'content':'Olá! Como posso ajudar?'},'stop')
        else:
            emit({'reasoning_content':'Vou conferir o cálculo antes de responder.'})
            if not reasoning_gate.wait(40):raise TimeoutError('Reasoning gate')
            emit({'content':'Vou usar a calculadora.'})
            emit({'tool_calls':[{'index':0,'id':'work-calc','type':'function','function':{'name':'calculate','arguments':'{"expression":"20+22"}'}}]},'tool_calls')
        self.wfile.write(('data: '+json.dumps({'choices':[],'usage':{'prompt_tokens':40,'completion_tokens':20}})+'\n\n').encode());self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
    except (BrokenPipeError,ConnectionResetError):pass
handler.do_GET=get;handler.do_POST=post

with tempfile.TemporaryDirectory() as directory:
    store=Store(directory);store.put('settings',{'engine_url':url})
    app=create_app(directory);sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    out=Path(os.environ.get('CENTRAL_QA_DIR','/tmp/central-work-panel-qa'));out.mkdir(parents=True,exist_ok=True)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap',timeout=.2);break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Backend did not start')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=None if os.environ.get('CENTRAL_USE_BUNDLED_BROWSER')=='1' else '/usr/bin/chromium',args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1366,'height':900},timezone_id='America/Sao_Paulo');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}')
            assert page.title() and 'Central' in page.title();expect(page.get_by_text('Conectado',exact=True)).to_be_visible()
            page.get_by_role('button',name='Ajustes da sessão',exact=True).click()
            dialog=page.get_by_role('dialog',name='Ajustes da sessão',exact=True)
            dialog.get_by_text('Amostragem avançada',exact=True).click()
            dialog.get_by_label('Top-P',exact=True).fill('0.82')
            dialog.get_by_label('Temperatura',exact=True).fill('0.55')
            dialog.get_by_text('Contexto e desempenho',exact=True).click()
            expect(dialog.get_by_label('Threads CPU',exact=False)).to_be_visible()
            page.screenshot(path=str(out/'ajustes-avancados.png'))
            dialog.get_by_role('button',name='Salvar parâmetros',exact=True).click()
            expect(page.get_by_role('alert')).to_contain_text('Perfil salvo')
            model=page.request.get(f'http://127.0.0.1:{port}/api/engine').json()['model']
            from urllib.parse import quote
            saved=page.request.get(f'http://127.0.0.1:{port}/api/profiles?model='+quote(model,safe='')).json()
            assert saved['top_p']==.82 and saved['temperature']==.55
            page.get_by_role('button',name='Fechar Ajustes da sessão',exact=True).click()
            page.get_by_role('textbox',name='Mensagem',exact=True).fill('ola');page.get_by_role('button',name='Enviar',exact=True).click()
            expect(page.locator('.message.assistant:not(.live)')).to_have_count(1)
            for width in [1366,390,320]:
                page.set_viewport_size({'width':width,'height':844})
                bubble=page.locator('.message.user .user-bubble').bounding_box();stamp=page.locator('.message.user .message-time').bounding_box()
                assert stamp['y']>=bubble['y']+bubble['height'],(width,bubble,stamp)
                assert page.evaluate('document.documentElement.scrollWidth')<=width
                page.screenshot(path=str(out/f'ola-{width}.png'))
            page.set_viewport_size({'width':1366,'height':900})
            page.get_by_role('textbox',name='Mensagem',exact=True).fill('Calcule usando uma ferramenta')
            page.get_by_role('button',name='Enviar',exact=True).click()
            work=page.locator('.live .work-panel')
            expect(work).to_have_attribute('open','')
            expect(work.locator('.reasoning')).to_contain_text('Vou conferir')
            expect(work.locator('summary').first).to_contain_text(re.compile(r'Processando há [1-9]\d* s'))
            expect(page.locator('header').get_by_role('button',name=re.compile('Interromper'))).to_have_count(0)
            expect(page.get_by_role('button',name='Interromper',exact=True)).to_have_count(1)
            page.get_by_role('button',name='Ajustes da sessão',exact=True).click()
            expect(dialog.get_by_label('Temperatura',exact=True)).to_be_disabled()
            page.get_by_role('button',name='Fechar Ajustes da sessão',exact=True).click()
            reasoning_gate.set()
            expect(work.locator('.tool-activity.done')).to_have_count(1)
            expect(work.locator('.reasoning').last).to_contain_text('A ferramenta retornou 42')
            assert work.locator('[data-timeline-kind]').evaluate_all('els=>els.map(el=>el.dataset.timelineKind)')==['reasoning','text','activity','reasoning']
            page.screenshot(path=str(out/'trabalho-ferramenta-aberto.png'))
            answer_gate.set()
            expect(page.locator('.live .message-answer')).to_contain_text('O resultado é 42.')
            expect(work).not_to_have_attribute('open','')
            expect(page.get_by_role('button',name='Interromper',exact=True)).to_have_count(1)
            page.screenshot(path=str(out/'resposta-pensamento-recolhido.png'))
            finish_gate.set()
            expect(page.locator('.live')).to_have_count(0)
            historical=page.locator('.message.assistant').last
            expect(historical.locator('.work-panel')).not_to_have_attribute('open','')
            historical.locator('.work-panel>summary').click()
            assert historical.locator('[data-timeline-kind]').evaluate_all('els=>els.map(el=>el.dataset.timelineKind)')==['reasoning','text','activity','reasoning','text']
            data=page.request.get(f'http://127.0.0.1:{port}/api/conversations').json();cid=data[0]['id']
            stored=page.request.get(f'http://127.0.0.1:{port}/api/conversations/'+cid).json()[-1]
            assert [b['type'] for b in stored['stats']['timeline']]==['reasoning','text','activity','reasoning','text']
            page.reload();page.locator('.history-title').filter(has_text='ola').click()
            historical=page.locator('.message.assistant').last
            expect(historical.locator('.work-panel')).not_to_have_attribute('open','')
            historical.locator('.work-panel>summary').click()
            expect(historical.locator('.tool-activity')).to_have_count(1)
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name='Ajustes da sessão',exact=True).click()
            expect(dialog.get_by_role('heading',name='Ajustes da sessão',exact=True)).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth')<=390
            page.screenshot(path=str(out/'ajustes-mobile.png'))
            assert not errors,errors
            browser.close()
        print('Work panel QA passed: short-message timestamps at 1366/390/320, live timer, ordered reasoning/tools, collapse before finish, reload, session save/lock, one stop control; no console errors.')
    finally:
        reasoning_gate.set();answer_gate.set();finish_gate.set();server.should_exit=True;thread.join(timeout=10);sock.close();fake.close()
