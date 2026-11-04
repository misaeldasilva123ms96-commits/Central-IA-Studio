"""Real browser + Studio + explicit model HTTP fixture; real uploads/files/commands."""
import asyncio
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from PIL import Image
from playwright.async_api import async_playwright,expect

ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT);sys.path.insert(0,str(ROOT))
from backend.storage import Store
spec=importlib.util.spec_from_file_location('feature_fixtures',ROOT/'tests/test_central.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
fake=fixtures.fake_engine.__wrapped__();url,handler=next(fake)
old_get=handler.do_GET;old_post=handler.do_POST;handler.vision=False

def get(self):
    if self.path=='/api/extra/version':return self.send({'result':'CentralEngine','version':'fixture','jinja':True})
    if self.path=='/props':return self.send({'modalities':{'vision':handler.vision},'chat_template_caps':{'supports_tools':True},'chat_template':'plain'})
    if self.path=='/api/v1/model':return self.send({'result':'Central Engine · fixture de interface'})
    return old_get(self)

def post(self):
    if self.path!='/v1/chat/completions':return old_post(self)
    data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    handler.payloads.append(('generate',data))
    last=data['messages'][-1];content=last.get('content') or '';call=None
    if last['role']=='tool':
        result=json.loads(content)
        answer='A ação não foi executada: '+result['error'] if result.get('error') else 'A ferramenta concluiu a ação solicitada.'
    elif isinstance(content,list):answer='Imagem recebida pelo transporte de teste. Esta fixture não faz reconhecimento visual.'
    elif content.startswith('Liste'):
        call=('list_files',{'path':'.'});answer=''
    elif content.startswith('Crie'):
        target='automatico.txt' if 'automático' in content else 'novo.txt'
        call=('write_file',{'path':target,'content':'Conteúdo criado pelo teste de integração.\n'});answer=''
    elif content.startswith('Execute'):
        call=('run_command',{'argv':[sys.executable,'-c','from pathlib import Path;Path("comando.txt").write_text("COMMAND_OK");print("COMMAND_OK")']});answer=''
    elif content.startswith('Pesquise'):
        call=('web_search',{'query':'Python documentação oficial'});answer=''
    elif content.startswith('Como somar'):
        answer='Você pode filtrar os valores negativos antes de calcular a soma:\n\n```python\ndef total(valores):\n    return sum(valor for valor in valores if valor >= 0)\n```\n\nAssim, apenas valores maiores ou iguais a zero entram no cálculo.'
    else:answer='Documento recebido na fixture de interface.\n\n```python\nprint("arquivo recebido")\n```'
    chunks=[]
    if call:
        name,args=call
        chunks=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'call-fixture','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'finish_reason':'tool_calls'}]}]
    else:
        chunks=[{'choices':[{'delta':{'content':answer},'finish_reason':'stop'}]}]
    chunks.append({'choices':[],'usage':{'prompt_tokens':40,'completion_tokens':20}})
    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
    try:
        for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
    except (BrokenPipeError,ConnectionResetError):pass
handler.do_GET=get;handler.do_POST=post

async def check(port,project):
    out=ROOT/'work/qa/features04';out.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=None if os.environ.get('CENTRAL_USE_BUNDLED_BROWSER')=='1' else '/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1586,'height':992});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(f'http://127.0.0.1:{port}/')
        host=page.locator('.chat-host:not([hidden])')
        await expect(page.get_by_text('Conectado',exact=True)).to_be_visible()
        assert await page.locator('.brand>img').evaluate('(i)=>i.naturalWidth>0')
        await page.get_by_role('button',name='Adicionar arquivos e imagens').click()
        await expect(page.get_by_role('menuitem',name='Arquivos e documentos')).to_be_visible()
        await page.keyboard.press('Escape')
        await host.get_by_label('Selecionar arquivos',exact=True).set_input_files({'name':'fornecedores.csv','mimeType':'text/csv','buffer':b'Fornecedor,Valor\nA,10\nB,-5'})
        await expect(host.locator('.composer-area .attachment')).to_have_count(1)
        await expect(host.locator('.composer-area .spin')).to_have_count(0,timeout=30000)
        transfer=await page.evaluate_handle("""()=>{const d=new DataTransfer();d.items.add(new File(['Documento arrastado de teste'],'arrastado.txt',{type:'text/plain'}));return d;}""")
        await host.locator('.chat-module').dispatch_event('dragenter',{'dataTransfer':transfer})
        await expect(host.get_by_text('Solte arquivos ou imagens aqui')).to_be_visible()
        await host.locator('.chat-module').dispatch_event('drop',{'dataTransfer':transfer})
        await expect(host.locator('.composer-area .attachment')).to_have_count(2)
        await expect(host.locator('.composer-area .spin')).to_have_count(0,timeout=30000)
        await page.screenshot(path=str(out/'anexos-arrastar.png'))
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.locator('.message.assistant:not(.live)')).to_have_count(1)
        await expect(host.locator('.message.user .attachment')).to_have_count(2)
        sent=[v for kind,v in handler.payloads if kind=='generate'][-1]
        assert 'Fornecedor,Valor' in sent['messages'][-1]['content'] and 'Documento arrastado' in sent['messages'][-1]['content']
        await page.get_by_role('button',name='Nova conversa',exact=True).click()
        buffer=io.BytesIO();Image.new('RGB',(24,18),'#00a080').save(buffer,format='PNG');original=buffer.getvalue()
        upload_started=asyncio.Event();release_upload=asyncio.Event()
        async def hold_upload(route):
            upload_started.set();await release_upload.wait();await route.continue_()
        await page.route('**/api/attachments?*',hold_upload)
        await host.get_by_label('Selecionar imagens',exact=True).set_input_files({'name':'imagem.png','mimeType':'image/png','buffer':original})
        await upload_started.wait()
        await expect(page.get_by_role('button',name='Nova conversa',exact=True)).to_be_disabled()
        await expect(page.locator('.history-title').first).to_be_disabled()
        await page.keyboard.press('Control+Shift+O')
        await expect(host.locator('.composer-area .attachment')).to_have_count(1)
        release_upload.set()
        await expect(host.locator('.composer-area .spin')).to_have_count(0,timeout=30000)
        await expect(host.get_by_text('O modelo carregado não informou suporte a visão.',exact=False)).to_be_visible()
        await expect(host.get_by_role('button',name='Enviar',exact=True)).to_be_disabled()
        handler.vision=True
        await expect(host.locator('.attachment-warning')).to_have_count(0,timeout=12000)
        await expect(host.get_by_role('button',name='Enviar',exact=True)).to_be_enabled()
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.locator('.message.assistant:not(.live)')).to_have_count(1)
        sent=[v for kind,v in handler.payloads if kind=='generate'][-1]
        assert sent['messages'][-1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
        image_link=host.get_by_role('link',name='Baixar imagem.png')
        download=await page.request.get(f'http://127.0.0.1:{port}'+await image_link.get_attribute('href'))
        assert await download.body()==original
        await page.get_by_role('button',name='Agente',exact=True).click()
        nav=await page.locator('.sidebar nav button').all_text_contents()
        assert nav.index('Agente')==nav.index('Conversas')+1
        host=page.locator('.chat-host:not([hidden])')
        await expect(host.get_by_role('heading',name='O que vamos construir?')).to_be_visible()
        await host.get_by_role('button',name='Escolher projeto',exact=True).click()
        picker=page.get_by_role('dialog',name='Selecionar pasta do projeto')
        await picker.get_by_role('textbox',name='Caminho da pasta').fill(str(project))
        await picker.get_by_role('button',name='Abrir caminho').click()
        await expect(picker.get_by_role('button',name='readme.txt',exact=True)).to_have_count(0) # directories only
        await picker.get_by_role('button',name='Usar esta pasta',exact=True).click()
        await host.get_by_role('combobox',name='Modo do agente').select_option('plan')
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Liste os arquivos do projeto')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.locator('.tool-activity.done')).to_have_count(1)
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        sent=[v for kind,v in handler.payloads if kind=='generate'][-1]
        names=[x['function']['name'] for x in sent['tools']]
        assert 'write_file' not in names and 'run_command' not in names
        await page.get_by_role('button',name='Nova tarefa',exact=True).click()
        await host.get_by_role('combobox',name='Modo do agente').select_option('build')
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Crie um arquivo novo.txt')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        approval=host.get_by_role('region',name='Aprovação pendente')
        await expect(approval).to_be_visible()
        assert not (project/'novo.txt').exists()
        await expect(approval).to_contain_text('Conteúdo criado pelo teste')
        await page.screenshot(path=str(out/'agente-build-aprovacao.png'))
        await approval.get_by_role('button',name='Permitir uma vez',exact=True).click()
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        assert (project/'novo.txt').read_text()=='Conteúdo criado pelo teste de integração.\n'
        edited=host.locator('.tool-activity.done').filter(has_text='Editar arquivo').last
        await edited.locator('summary').click()
        await edited.get_by_role('button',name='Desfazer alteração',exact=True).click()
        undo=page.get_by_role('dialog',name='Desfazer alteração do agente')
        await undo.get_by_role('button',name='Confirmar restauração',exact=True).click()
        await expect(edited.get_by_text('Alteração desfeita.',exact=True)).to_be_visible()
        assert not (project/'novo.txt').exists()
        await edited.locator('summary').click()
        if await page.get_by_role('button',name='Fechar aviso').count():await page.get_by_role('button',name='Fechar aviso').click()
        await host.get_by_role('button',name='Permissões: Solicitar aprovação').click()
        await expect(page.get_by_role('menuitemradio',name='Acesso completo',exact=False)).to_be_visible()
        assert await page.locator('.access-menu').evaluate('''el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&el.contains(document.elementFromPoint(r.left+20,r.top+20));}''')
        await page.screenshot(path=str(out/'permissoes.png'))
        await page.get_by_role('menuitemradio',name='Aprovar por mim',exact=False).click()
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Crie arquivo automático')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        assert (project/'automatico.txt').exists()
        await expect(host.locator('.approval-card')).to_have_count(0)
        await host.get_by_role('button',name='Permissões: Aprovar por mim').click()
        await page.get_by_role('menuitemradio',name='Acesso completo',exact=False).click()
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Execute o comando de teste')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        assert (project/'comando.txt').read_text()=='COMMAND_OK'
        await host.get_by_role('button',name='Permissões: Acesso completo').click()
        await page.get_by_role('menuitemradio',name='Solicitar aprovação',exact=False).click()
        await host.get_by_role('button',name='Internet',exact=True).click()
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Pesquise a documentação de Python')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(approval).to_be_visible()
        await approval.get_by_role('button',name='Negar',exact=True).click()
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        await expect(host.locator('.tool-activity.denied')).to_have_count(1)
        for width,height in [(1586,992),(1366,768),(1024,600),(390,844),(390,500),(844,390)]:
            await page.set_viewport_size({'width':width,'height':height})
            bounds=await page.evaluate("""()=>{const c=document.querySelector('.chat-host:not([hidden]) .composer').getBoundingClientRect();return {w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight,bottom:c.bottom};}""")
            assert bounds['w']<=width and bounds['h']<=height+1 and bounds['bottom']<=height+1,bounds
            await page.screenshot(path=str(out/f'agente-{width}x{height}.png'))
        await page.set_viewport_size({'width':1586,'height':992})
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await page.get_by_role('button',name='Nova conversa',exact=True).click()
        host=page.locator('.chat-host:not([hidden])')
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Como somar os valores dos fornecedores sem considerar os negativos?')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.locator('.message.assistant:not(.live)')).to_have_count(1)
        await page.screenshot(path=str(out/'conversa-referencia.png'))
        assert not errors,errors
        await browser.close()
    print('v0.4 UI: anexos, drag/drop, imagem e capacidade, Plan, Build com aprovação, acesso automático/completo, comandos reais, internet negada, seis viewports: passaram.')

with tempfile.TemporaryDirectory() as directory:
    base=Path(directory);project=base/'projeto';project.mkdir();(project/'readme.txt').write_text('Projeto de teste')
    store=Store(base/'data');store.put('settings',{'engine_url':url,'executable':'','folders':[]})
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=(ROOT/'work/features04-server.log').open('w')
    process=subprocess.Popen([sys.executable,'run.py','--no-browser','--port',str(port),'--data-dir',str(base/'data')],stdout=log,stderr=log)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap',timeout=.3);break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Studio não iniciou')
        asyncio.run(check(port,project))
    finally:process.terminate();process.wait(timeout=10);log.close();fake.close()
