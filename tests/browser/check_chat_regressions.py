"""UI regression tests with an explicit HTTP fixture, not a trained model."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from playwright.async_api import async_playwright,expect

ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT);sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('central_fixtures',ROOT/'tests/test_central.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
fake=fixtures.fake_engine.__wrapped__();url,handler=next(fake)
finished=threading.Event();original_post=handler.do_POST
code='def total(valores):\n    return sum(v for v in valores if v >= 0)\n'
unlabelled='linha 1\n\n\n    linha 4\n'
answer='Exemplo do teste de interface:\n\n```python\n'+code+'```\n\nSem linguagem:\n\n```\n'+unlabelled+'```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n'
def do_post(self):
    if self.path!='/v1/chat/completions':return original_post(self)
    data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    handler.payloads.append(('generate',data))
    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
    content='Você pode filtrar os valores negativos antes de calcular a soma:\n\n```python\n'+code+'```\n\nAssim, apenas valores maiores ou iguais a zero entram no cálculo.' if data['messages'][-1]['content'].startswith('Como somar') else answer
    first={'choices':[{'delta':{'content':content},'finish_reason':None}]}
    self.wfile.write(('data: '+json.dumps(first)+'\n\n').encode());self.wfile.flush()
    finished.wait(20)
    chunks=[{'choices':[{'delta':{'content':'\nFim do exemplo.'},'finish_reason':None}]},{'choices':[{'delta':{},'finish_reason':'stop'}]},
            {'choices':[],'usage':{'prompt_tokens':40,'completion_tokens':20},'timings':{'predicted_per_second':3.5}}]
    for c in chunks:self.wfile.write(('data: '+json.dumps(c)+'\n\n').encode())
    self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
handler.do_POST=do_post

async def check(port,directory):
    out=ROOT/'work/qa/chat-regressions';out.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=None if os.environ.get('CENTRAL_USE_BUNDLED_BROWSER')=='1' else '/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':1440,'height':900},permissions=['clipboard-read','clipboard-write'])
        page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(f'http://127.0.0.1:{port}/')
        await page.get_by_role('button',name='Configurar conexão',exact=True).click()
        await page.get_by_text('Endereço do motor',exact=True).locator('..').locator('input').fill(url)
        await page.get_by_role('button',name='Salvar conexão',exact=True).click()
        await expect(page.get_by_role('alert')).to_contain_text('Configuração salva')
        await page.get_by_role('button',name='Conversas',exact=True).click()
        try:await page.get_by_text('Conectado',exact=True).wait_for(timeout=12000)
        except Exception:
            await page.screenshot(path=str(out/'failure-connect.png'))
            print(await page.locator('body').inner_text(),errors)
            raise
        await page.get_by_role('button',name='Fechar aviso').click()
        await page.get_by_text('Mensagem de sistema',exact=True).click()
        system_box=page.get_by_role('textbox',name='Mensagem de sistema',exact=True)
        original=await system_box.input_value();assert 'português brasileiro' in original
        custom=original+' MARCADOR-PERSONALIZADO'
        await system_box.fill(custom)
        await page.get_by_text('Mensagem de sistema',exact=True).click()
        gate=asyncio.Event()
        async def hold(route):
            if route.request.method=='POST':await gate.wait()
            await route.continue_()
        await page.route('**/api/conversations',hold)
        text='Mensagem imediata com a palavra svg'
        await page.get_by_role('textbox',name='Mensagem',exact=True).fill(text)
        await page.get_by_role('button',name='Enviar',exact=True).click()
        await expect(page.locator('.message.user')).to_contain_text(text)
        assert not gate.is_set() and not any(k=='generate' for k,_ in handler.payloads)
        await expect(page.get_by_role('textbox',name='Mensagem',exact=True)).to_have_value('')
        await page.screenshot(path=str(out/'01-envio-imediato.png'))
        gate.set()
        await expect(page.locator('.messages pre > code.language-python')).to_have_count(1)
        # Same Markdown (GFM tables) during streaming and after persistence.
        await expect(page.locator('.messages table')).to_have_count(1)
        assert handler.payloads[-1][1]['messages'][0]['content']==custom
        await page.get_by_role('button',name='Parâmetros',exact=True).click()
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await expect(page.get_by_role('button',name='Interromper',exact=True)).to_be_visible()
        await expect(page.locator('.message.user')).to_contain_text(text)
        await page.set_viewport_size({'width':1024,'height':600})
        await page.locator('.messages').evaluate('(el)=>{el.scrollTop=0;}')
        await page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        assert await page.locator('.messages').evaluate('(el)=>el.scrollHeight-el.clientHeight>70')
        finished.set()
        await expect(page.locator('.message.assistant')).to_have_count(1)
        await expect(page.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        await expect(page.locator('.message.user')).to_have_count(1)
        assert await page.locator('.messages').evaluate('(el)=>el.scrollTop')<2
        await page.get_by_text('Mensagem de sistema',exact=True).click()
        assert await system_box.input_value()==custom
        await page.get_by_text('Mensagem de sistema',exact=True).click()
        assert await page.locator('.message.assistant pre').first.evaluate('(p)=>Array.from(p.children).map(c=>c.tagName)')==['CODE']
        await expect(page.locator('.message.assistant footer')).to_contain_text('primeiro trecho')
        await expect(page.locator('.message.assistant footer')).to_contain_text('decodificação: 3.50')
        assert await page.locator('.message.assistant pre > code.language-python').text_content()==code
        await expect(page.locator('.message.assistant .code-toolbar button')).to_have_count(2)
        stable_code=await page.locator('.message.assistant pre code').first.element_handle()
        async with page.expect_response('**/api/metrics') as poll:
            pass
        await (await poll.value).body()
        await page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        assert await stable_code.evaluate('(node)=>node.isConnected')
        await expect(page.locator('.message.assistant .hljs-keyword').first).to_be_visible()

        await page.locator('.message.assistant .code-toolbar button').first.click()
        assert await page.evaluate('navigator.clipboard.readText()')==code
        # Selection copy preserves code fences/indentation and excludes SVG/actions.
        await page.evaluate('''()=>{const r=document.createRange();r.selectNodeContents(document.querySelector('.messages'));const s=getSelection();s.removeAllRanges();s.addRange(r);}''')
        await page.keyboard.press('Control+c')
        copied=await page.evaluate('''async()=>{const items=await navigator.clipboard.read();const out={};for(const item of items)for(const type of item.types)out[type]=await(await item.getType(type)).text();return out;}''')
        assert '<svg' not in copied['text/html'] and '<button' not in copied['text/html']
        assert '```python\n'+code.rstrip() in copied['text/plain']
        assert unlabelled.rstrip() in copied['text/plain']
        assert 'A\tB\n1\t2\n' in copied['text/plain']
        assert 'palavra svg' in copied['text/plain']  # do not strip legitimate text
        await page.evaluate("""()=>{const code=document.querySelector('.message.assistant pre code');const all=code.textContent;const start=all.indexOf('    return');const end=all.indexOf('\\n',start);const walker=document.createTreeWalker(code,NodeFilter.SHOW_TEXT);let pos=0,node,r=document.createRange();while(node=walker.nextNode()){const next=pos+node.textContent.length;if(start>=pos&&start<next)r.setStart(node,start-pos);if(end>pos&&end<=next){r.setEnd(node,end-pos);break;}pos=next;}const s=getSelection();s.removeAllRanges();s.addRange(r);}""")
        await page.keyboard.press('Control+c')
        assert await page.evaluate('navigator.clipboard.readText()')==code.splitlines()[1]
        await page.evaluate('getSelection().removeAllRanges()')
        for width,height in [(1586,992),(1440,900),(1366,768),(1024,600),(390,844),(390,500),(844,390)]:
            await page.set_viewport_size({'width':width,'height':height})
            await page.wait_for_function('''()=>{const c=document.querySelector('.composer').getBoundingClientRect();return c.bottom<=innerHeight+1;}''')
            bounds=await page.evaluate('''()=>({w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight,header:document.querySelector('header').getBoundingClientRect().height})''')
            assert bounds['w']<=width and bounds['h']<=height+1,bounds
            assert bounds['header']<=56,bounds
            await page.screenshot(path=str(out/f'viewport-{width}x{height}.png'))
        # A rejected request restores the draft and does not duplicate stored users.
        async def reject(route):
            await route.fulfill(status=400,content_type='application/json',body=json.dumps({'detail':'Contexto de teste esgotado'}))
        await page.route('**/api/generate',reject)
        await page.get_by_role('textbox',name='Mensagem',exact=True).fill('mensagem recuperavel')
        await page.get_by_role('button',name='Enviar',exact=True).click()
        await expect(page.get_by_role('textbox',name='Mensagem',exact=True)).to_have_value('mensagem recuperavel')
        await expect(page.get_by_role('textbox',name='Mensagem',exact=True)).to_be_enabled()
        await expect(page.locator('.message.user')).to_have_count(1)
        await expect(page.get_by_role('alert')).to_contain_text('Contexto de teste esgotado')
        # New history management and local directory chooser exercise real API.
        await page.set_viewport_size({'width':1440,'height':900})
        await page.get_by_role('button',name='Fechar aviso').click()
        await page.get_by_role('button',name='Modelos',exact=True).click()
        await page.get_by_role('textbox',name='Pasta com modelos (GGUF)',exact=True).fill(directory)
        await page.get_by_role('button',name='Selecionar pasta',exact=True).click()
        picker=page.get_by_role('dialog',name='Selecionar pasta de modelos')
        await picker.get_by_role('button',name='biblioteca ç',exact=True).click()
        await page.screenshot(path=str(out/'folder-picker.png'))
        await picker.get_by_role('button',name='Usar esta pasta',exact=True).click()
        await expect(page.get_by_role('textbox',name='Pasta com modelos (GGUF)',exact=True)).to_have_value(str(Path(directory)/'biblioteca ç'))
        await page.get_by_role('button',name='Adicionar pasta',exact=True).click()
        await expect(page.get_by_role('button',name='teste.gguf',exact=True)).to_be_visible()
        await page.get_by_role('button',name='Selecionar pasta',exact=True).click()
        await picker.get_by_role('button',name='Pasta acima',exact=True).click()
        await expect(picker.get_by_role('textbox',name='Caminho da pasta')).to_have_value(directory)
        await page.keyboard.press('Escape')
        await expect(picker).to_have_count(0)
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await page.get_by_role('button',name='Ajustes da sessão',exact=True).click()
        await expect(page.get_by_role('dialog',name='Ajustes da sessão')).to_be_visible()
        await page.keyboard.press('Escape')
        await page.locator('.history-title').first.hover()
        await page.get_by_role('button',name='Renomear '+text).click()
        await page.get_by_role('dialog').get_by_role('textbox').fill('Conversa renomeada')
        await page.get_by_role('button',name='Salvar',exact=True).click()
        await expect(page.locator('.history-title').filter(has_text='Conversa renomeada')).to_have_count(1)
        await page.get_by_role('textbox',name='Pesquisar histórico').fill('inexistente')
        await expect(page.get_by_text('Nenhuma conversa encontrada.')).to_be_visible()
        await page.get_by_role('textbox',name='Pesquisar histórico').fill('')
        await page.get_by_role('button',name='Nova conversa',exact=True).click()
        await expect(page.get_by_role('heading',name='Como posso ajudar?')).to_be_visible()
        await page.get_by_role('button',name='Revise meu código',exact=True).click()
        await expect(page.get_by_role('textbox',name='Mensagem',exact=True)).to_have_value('Revise este código e sugira melhorias:\n\n')
        history_gate=asyncio.Event()
        async def hold_history(route):
            await history_gate.wait();await route.continue_()
        await page.route('**/api/system-prompt/*',hold_history)
        await page.locator('.history-title').filter(has_text='Conversa renomeada').click()
        await expect(page.get_by_role('textbox',name='Mensagem',exact=True)).to_be_disabled()
        history_gate.set()
        await expect(page.locator('.message.assistant')).to_have_count(1)
        await expect(page.get_by_role('textbox',name='Mensagem',exact=True)).to_be_enabled()
        await page.unroute('**/api/system-prompt/*',hold_history)
        await page.locator('.history-title').first.hover()
        await page.get_by_role('button',name='Excluir Conversa renomeada').click()
        await page.get_by_role('button',name='Cancelar',exact=True).click()
        await expect(page.locator('.history-title').filter(has_text='Conversa renomeada')).to_have_count(1)
        await page.locator('.history-title').first.hover()
        await page.get_by_role('button',name='Excluir Conversa renomeada').click()
        await page.get_by_role('dialog').get_by_role('button',name='Excluir conversa',exact=True).click()
        await expect(page.locator('.history-row')).to_have_count(0)
        await page.get_by_role('button',name='Ativar tema claro').click()
        await page.screenshot(path=str(out/'empty-light.png'))
        await page.get_by_role('button',name='Ativar tema escuro').click()
        # Keep a readable preview of the real interface with explicitly synthetic content.
        await page.unroute('**/api/generate',reject)
        await page.get_by_role('textbox',name='Mensagem',exact=True).fill('Como somar os valores dos fornecedores sem considerar os negativos?')
        await page.get_by_role('button',name='Enviar',exact=True).click()
        await expect(page.locator('.message.assistant')).to_have_count(1)
        await expect(page.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        bootstrap=(await (await context.request.get(f'http://127.0.0.1:{port}/api/bootstrap')).json())
        headers={'X-Central-Token':bootstrap['token']}
        rows=await (await context.request.get(f'http://127.0.0.1:{port}/api/conversations')).json()
        await context.request.patch(f'http://127.0.0.1:{port}/api/conversations/'+rows[0]['id'],headers=headers,data={'title':'Revisão de código Python'})
        for title in ['Planejamento da semana','Ideias para um projeto']:
            await context.request.post(f'http://127.0.0.1:{port}/api/conversations',headers=headers,data={'title':title})
        await page.reload()
        await page.locator('.history-title').filter(has_text='Revisão de código Python').click()
        await expect(page.locator('.message.assistant')).to_have_count(1)
        await page.set_viewport_size({'width':1586,'height':992})
        await page.screenshot(path=str(out/'preview-desktop.png'))
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(out/'preview-mobile.png'))
        assert not errors,errors
        await browser.close()
    print('UI: envio antes da resposta, sistema preservado, abas durante geração, Markdown, cópia sem SVG seleção de pastas, gestão de histórico e sete viewports: passaram.')

with tempfile.TemporaryDirectory() as directory:
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,'run.py','--no-browser','--port',str(port),'--data-dir',directory],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap',timeout=.2);break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Gerenciador não iniciou')
        fixtures.gguf(Path(directory)/'biblioteca ç'/'teste.gguf')
        asyncio.run(check(port,directory))
    finally:
        finished.set();proc.terminate();proc.wait(timeout=10);fake.close()
