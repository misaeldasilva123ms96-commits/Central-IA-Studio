"""Preset controls + real Studio requests and local compaction with a deterministic model fixture."""
import importlib.util
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
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from backend.app import create_app
from backend.storage import Store
from backend.domain import Profile
from test_context_memory import install_memory_handler,seed_memory_case,SUMMARY
import test_central as fixtures
fake=fixtures.fake_engine.__wrapped__();url,handler=next(fake);install_memory_handler(handler)
with tempfile.TemporaryDirectory() as directory:
    store=Store(directory);store.put('settings',{'engine_url':url});store.save_profile('default',Profile(context=2048,max_output=768).model_dump());cid=seed_memory_case(store)
    app=create_app(directory);sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    out=Path(os.environ.get('CENTRAL_QA_DIR','/tmp/central-presets-context-qa'));out.mkdir(parents=True,exist_ok=True)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap',timeout=.2);break
            except Exception:time.sleep(.1)
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=None if os.environ.get('CENTRAL_USE_BUNDLED_BROWSER')=='1' else '/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1366,'height':900},timezone_id='America/Sao_Paulo');errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type in ('error','warning') else None)
            page.goto(f'http://127.0.0.1:{port}');expect(page.get_by_text('Conectado',exact=True)).to_be_visible()
            page.get_by_role('button',name='Ajustes da sessão',exact=True).click()
            dialog=page.get_by_role('dialog',name='Ajustes da sessão',exact=True);mode=dialog.get_by_role('combobox',name='Modo',exact=True)
            expect(mode.locator('option')).to_have_count(7)
            mode.select_option('rapido');expect(dialog.get_by_label('Saída máxima (tokens)',exact=True)).to_have_value('512');expect(dialog.get_by_label('Temperatura',exact=True)).to_have_value('0.4')
            mode.select_option('criativo');expect(dialog.get_by_label('Temperatura',exact=True)).to_have_value('0.95')
            dialog.get_by_label('Temperatura',exact=True).fill('0.66');expect(mode).to_have_value('personalizado')
            mode.select_option('equilibrado');expect(dialog.get_by_label('Saída máxima (tokens)',exact=True)).to_have_value('1536')
            dialog.get_by_text('Memória da conversa',exact=True).click();expect(dialog.get_by_role('checkbox',name='Compactação automática do histórico',exact=True)).to_be_checked()
            page.screenshot(path=str(out/'modos-e-memoria.png'))
            dialog.get_by_role('button',name='Salvar parâmetros',exact=True).click();expect(page.get_by_role('alert')).to_contain_text('Perfil salvo')
            page.get_by_role('button',name='Fechar Ajustes da sessão',exact=True).click()
            page.get_by_role('button',name='Abrir ajustes do Central IA',exact=True).click();page.get_by_role('menuitem',name='Parâmetros',exact=True).click()
            expect(page.get_by_role('combobox',name='Modo',exact=True)).to_have_value('equilibrado')
            page.get_by_role('combobox',name='Modo',exact=True).select_option('codigo');expect(page.get_by_label('Temperatura',exact=True)).to_have_value('0.25')
            page.get_by_role('combobox',name='Modo',exact=True).select_option('equilibrado')
            page.get_by_role('button',name='Conversas',exact=True).click();page.locator('.history-title').filter(has_text='Conversa com histórico').click()
            page.get_by_role('textbox',name='Mensagem',exact=True).fill('Continue o projeto');page.get_by_role('button',name='Enviar',exact=True).click()
            expect(page.locator('.message.assistant:not(.live)').last).to_contain_text('Resposta final com memória.',timeout=30000)
            expect(page.locator('.limits>summary')).to_contain_text('Histórico compactado')
            page.locator('.limits>summary').click();expect(page.locator('.limits')).to_contain_text('Compactadas 6 mensagens')
            page.get_by_text('Ver memória compactada (6 mensagens)',exact=True).click();expect(page.locator('.context-memory pre')).to_have_text(SUMMARY);expect(page.locator('.context-memory pre')).to_be_visible()
            original=page.request.get(f'http://127.0.0.1:{port}/api/conversations/'+cid).json();assert len(original)==10 and 'pergunta 0' in original[0]['content']
            page.screenshot(path=str(out/'historico-compactado.png'))
            page.reload();page.locator('.history-title').filter(has_text='Conversa com histórico').click()
            page.locator('.limits>summary').click();page.get_by_text('Ver memória compactada (6 mensagens)',exact=True).click();expect(page.locator('.context-memory pre')).to_have_text(SUMMARY);expect(page.locator('.context-memory pre')).to_be_visible()
            page.get_by_role('button',name='Descartar memória compactada',exact=True).click();expect(page.locator('.context-memory')).to_have_count(0)
            assert len(page.request.get(f'http://127.0.0.1:{port}/api/conversations/'+cid).json())==10
            page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='Ajustes da sessão',exact=True).click()
            expect(dialog.get_by_role('combobox',name='Modo',exact=True)).to_have_value('equilibrado')
            dialog.get_by_text('Memória da conversa',exact=True).click();dialog.get_by_role('checkbox',name='Compactação automática do histórico',exact=True).uncheck()
            page.screenshot(path=str(out/'memoria-mobile.png'));assert page.evaluate('document.documentElement.scrollWidth')<=390
            assert not errors,errors;browser.close()
        print('Presets/context QA passed: seven modes, visible parameter changes, manual override, session/full parameters, local checkpoint, history preserved, reload, reset and mobile; clean console.')
    finally:
        server.should_exit=True;thread.join(timeout=10);sock.close();fake.close()
