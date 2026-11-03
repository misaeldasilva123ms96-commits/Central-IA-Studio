"""E2E com fixture explícita: não mede inferência real. Requer playwright + Chromium."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('central_fixtures',ROOT/'tests/test_central.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
fake=fixtures.fake_engine.__wrapped__();url,handler=next(fake)
errors=[]
with tempfile.TemporaryDirectory() as directory:
    proc=subprocess.Popen([sys.executable,'run.py','--no-browser','--port','8767','--data-dir',directory],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap',timeout=.2);break
            except Exception: time.sleep(.1)
        else: raise RuntimeError('Gerenciador não iniciou')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':900})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8767/')
            page.get_by_role('button',name='Configurar conexão',exact=True).click()
            page.get_by_text('Endereço do KoboldCpp',exact=True).locator('..').locator('input').fill(url)
            page.get_by_role('button',name='Salvar conexão',exact=True).click()
            page.get_by_role('alert').filter(has_text='Configuração salva').wait_for()
            page.get_by_role('button',name='Parâmetros',exact=True).click()
            page.get_by_role('spinbutton').nth(0).fill('8192')
            page.get_by_text('Saída máxima (tokens)',exact=True).locator('..').locator('input').fill('5000')
            page.get_by_role('button',name='Conversas',exact=True).click()
            page.get_by_text('Conectado',exact=True).wait_for(timeout=10000)
            page.get_by_text('Registrar benchmark',exact=True).click()
            page.get_by_role('textbox',name='Mensagem',exact=True).fill('Teste de integração no navegador')
            page.get_by_role('button',name='Enviar',exact=True).click()
            page.get_by_text('Olá, mundo!',exact=True).wait_for(timeout=10000)
            page.get_by_text('Solicitado: 5000',exact=False).wait_for()
            page.get_by_text('Pensamento retornado pelo motor',exact=True).click()
            page.get_by_text('Teste separado.',exact=False).wait_for()
            assert handler.payloads[-1][1]['max_tokens']==5000
            page.screenshot(path='work/qa/chat-fixture.png',full_page=True)
            page.get_by_role('button',name='Benchmarks',exact=True).click()
            page.get_by_role('cell',name='modelo-fixture',exact=True).wait_for()
            page.get_by_role('button',name='Conversas',exact=True).click()
            page.get_by_role('combobox',name='Conversa',exact=True).select_option(index=1)
            page.get_by_text('Olá, mundo!',exact=True).wait_for()
            page.get_by_role('button',name='Regenerar',exact=True).click()
            page.get_by_text('Olá, mundo!',exact=True).wait_for()
            page.get_by_role('button',name='Continuar',exact=True).wait_for()
            browser.close()
    finally:
        proc.terminate();proc.wait(timeout=10)
        fake.close()
assert not errors,errors
print('Chat E2E com fixture HTTP: passou; max_tokens=5000; histórico, reasoning, benchmark e regeneração verificados.')
