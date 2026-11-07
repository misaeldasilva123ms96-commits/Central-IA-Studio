"""Browser + actual backend; deterministic public GitHub transport fixture, no model."""
import asyncio
from datetime import datetime,timezone
import json
import os
from pathlib import Path
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
from backend.online_catalog import OnlineCatalog

SHA='a'*40
SKILL=b'---\nname: Catalog skill fixture\ndescription: Deterministic browser fixture with a reference file\n---\nRead references/guide.md when needed.'
original_fetch=OnlineCatalog.fetch
async def fetch(self,client,url,limit):
    if '/commits/' in url:return json.dumps({'sha':SHA,'commit':{'tree':{'sha':'b'*40}}}).encode()
    if '/git/trees/' in url:return json.dumps({'tree':[{'path':'skills/.curated/example/SKILL.md','type':'blob','mode':'100644','size':len(SKILL)},{'path':'skills/.curated/example/references/guide.md','type':'blob','mode':'100644','size':5}]}).encode()
    assert '/'+SHA+'/' in url
    return SKILL if url.endswith('/SKILL.md') else b'Guide'
OnlineCatalog.fetch=fetch
with tempfile.TemporaryDirectory() as directory:
    app=create_app(directory);store=app.state.store
    cid=store.conversation('Teste de horários')
    store.add_message(cid,'user','Pergunta com horário salvo',created=datetime(2026,11,7,19,38,tzinfo=timezone.utc).timestamp())
    store.add_message(cid,'assistant','Resposta com horário salvo',created=datetime(2026,11,7,19,39,tzinfo=timezone.utc).timestamp())
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap',timeout=.2);break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Backend não iniciou')
        out=ROOT/'work/qa/catalog05';out.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=None if os.environ.get('CENTRAL_USE_BUNDLED_BROWSER')=='1' else '/usr/bin/chromium',args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1366,'height':900},timezone_id='America/Sao_Paulo');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}')
            page.get_by_role('button',name='Plugins e Habilidades',exact=True).click()
            expect(page.locator('.extension-card')).to_have_count(8)
            assert page.locator('.extension-card').first.bounding_box()['height']<260
            page.get_by_role('button',name='Catálogos online',exact=True).click()
            page.get_by_role('button',name='Consultar fonte',exact=True).click()
            card=page.get_by_role('article',name='Catalog skill fixture',exact=True)
            expect(card).to_be_visible()
            card.get_by_role('button',name='Revisar e instalar',exact=True).click()
            dialog=page.get_by_role('dialog',name='Revisar pacote online',exact=True)
            expect(dialog).to_contain_text('2 arquivos')
            expect(dialog).to_contain_text('aaaaaaaa')
            dialog.get_by_role('button',name='Confirmar instalação',exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(card.locator('.extension-status')).to_have_text('Instalado')
            page.get_by_role('combobox',name='Filtrar catálogo online por instalação',exact=True).select_option('available')
            expect(page.locator('.extension-card')).to_have_count(0)
            page.get_by_role('combobox',name='Filtrar catálogo online por instalação',exact=True).select_option('installed')
            expect(card).to_be_visible()
            page.screenshot(path=str(out/'catalogo-online-fixture.png'))
            page.get_by_role('button',name='Conversas',exact=True).click()
            page.locator('.history-title').filter(has_text='Teste de horários').click()
            expect(page.locator('.message.user .message-time')).to_have_text('16:38')
            expect(page.locator('.message.assistant .message-time')).to_have_text('16:39')
            expect(page.locator('.message.user .message-time')).to_have_attribute('datetime','2026-11-07T19:38:00.000Z')
            page.reload()
            page.locator('.history-title').filter(has_text='Teste de horários').click()
            expect(page.locator('.message.user .message-time')).to_have_text('16:38')
            page.screenshot(path=str(out/'horarios-salvos.png'))
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=390')
            expect(page.locator('.message.assistant .message-time')).to_be_visible()
            page.screenshot(path=str(out/'horarios-mobile.png'))
            assert not errors,errors
            browser.close()
        print('Catálogo online: consulta, revisão, recursos, instalação e filtros; horários salvos no fuso do navegador, recarga e mobile: passaram.')
    finally:
        server.should_exit=True;thread.join(timeout=10);sock.close();OnlineCatalog.fetch=original_fetch
