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
    elif content.startswith('Consulte MCP'):
        call=(handler.mcp_alias,{'x':20,'y':22});answer=''
    elif content.startswith('Use automaticamente'):
        call=('load_skill',{'id':handler.skill_id});answer=''
    elif content.startswith('Calcule'):
        call=('calculate',{'expression':'(10 + 5) * 2'});answer=''
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
        chunks=[{'choices':[{'delta':{'content':'Vou executar esta etapa.\n\n','tool_calls':[{'index':0,'id':'call-fixture','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'finish_reason':'tool_calls'}]}]
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
        await page.get_by_role('button',name='Abrir ajustes do Central IA',exact=True).click()
        await expect(page.get_by_role('menuitem',name='Configurações',exact=True)).to_be_visible()
        await page.keyboard.press('Escape')
        await expect(page.get_by_role('menu',name='Ajustes do Central IA')).to_have_count(0)
        await page.get_by_role('button',name='Abrir ajustes do Central IA',exact=True).click()
        await page.get_by_role('menuitem',name='Configurações',exact=True).click()
        await expect(page.get_by_role('heading',name='Configurações',exact=True)).to_be_visible()
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await expect(page.locator('.sidebar .history-title')).to_have_count(35)
        sidebar=page.locator('.sidebar-scroll')
        assert await sidebar.evaluate("el=>{const nav=el.querySelector('nav').getBoundingClientRect();const history=el.querySelector('.sidebar-history').getBoundingClientRect();return nav.bottom<=history.top&&getComputedStyle(el.querySelector('.history-list')).overflowY==='visible'&&el.scrollHeight>el.clientHeight;}")
        assert await page.locator('.sidebar nav button').first.evaluate("el=>el.getBoundingClientRect().height<=38")
        await sidebar.evaluate('el=>el.scrollTop=el.scrollHeight')
        await expect(page.get_by_role('button',name='Histórico de teste 00',exact=True)).to_be_in_viewport()
        assert await page.locator('.sidebar nav').evaluate('el=>el.getBoundingClientRect().bottom<el.parentElement.getBoundingClientRect().top')
        await sidebar.evaluate('el=>el.scrollTop=0')
        assert await page.locator('.sidebar nav button').all_text_contents()==['Conversas','Agente','Plugins e Habilidades']
        assert await page.locator('.header-actions button[title*=tema]').count()==0
        await page.get_by_role('button',name='Abrir ajustes do Central IA',exact=True).click()
        for name in ['Modelos','Parâmetros','Benchmarks','Monitoramento']:
            await expect(page.get_by_role('menuitem',name=name,exact=True)).to_be_visible()
        await page.screenshot(path=str(out/'rodape-expansivo.png'))
        await page.keyboard.press('Escape')
        await page.get_by_role('button',name='Plugins e Habilidades',exact=True).click()
        await expect(page.locator('.extension-card')).to_have_count(8)
        example=await page.request.get(f'http://127.0.0.1:{port}/central-demo-plugin.zip')
        assert example.status==200
        from zipfile import ZipFile
        with ZipFile(io.BytesIO(await example.body())) as archive:assert 'plugin.json' in archive.namelist()
        await page.screenshot(path=str(out/'marketplace-plugins.png'))
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=390')
        await page.screenshot(path=str(out/'marketplace-tela-menor.png'))
        await page.set_viewport_size({'width':1586,'height':992})
        await page.get_by_role('textbox',name='Pesquisar extensões',exact=True).fill('JSON')
        await expect(page.locator('.extension-card')).to_have_count(1)
        await page.get_by_role('textbox',name='Pesquisar extensões',exact=True).fill('')
        await page.get_by_role('button',name='Catálogos online',exact=True).click()
        await expect(page.get_by_role('combobox',name='Fonte do catálogo',exact=True)).to_be_visible()
        await page.get_by_role('textbox',name='Repositório GitHub personalizado',exact=True).fill('https://localhost/private')
        await page.get_by_role('button',name='Adicionar fonte',exact=True).click()
        await expect(page.get_by_role('alert')).to_contain_text('URL pública')
        await page.get_by_role('button',name='Plugins',exact=True).click()
        calculator=page.get_by_role('article',name='Calculadora',exact=True)
        await page.get_by_role('combobox',name='Filtrar por instalação',exact=True).select_option('installed')
        await expect(page.locator('.extension-card')).to_have_count(8)
        await page.get_by_role('combobox',name='Filtrar por instalação',exact=True).select_option('available')
        await expect(page.locator('.extension-card')).to_have_count(0)
        await page.get_by_role('combobox',name='Filtrar por instalação',exact=True).select_option('all')
        await expect(calculator.locator('.extension-status')).to_have_text('Ativo')
        await calculator.get_by_role('button',name='Desativar Calculadora',exact=True).click()
        await expect(calculator.locator('.extension-status')).to_have_text('Desativado')
        await calculator.get_by_role('button',name='Ativar Calculadora',exact=True).click()
        await expect(calculator.locator('.extension-status')).to_have_text('Ativo')
        await page.get_by_role('button',name='Habilidades',exact=True).click()
        await expect(page.locator('.extension-card')).to_have_count(8)
        writing=page.get_by_role('article',name='Redação e revisão',exact=True)
        await expect(writing.locator('.extension-status')).to_have_text('Ativo')
        await expect(writing.locator('.extension-status')).to_have_text('Ativo')
        await writing.get_by_role('checkbox',name='Uso automático de Redação e revisão',exact=True).uncheck()
        await expect(writing.get_by_role('checkbox',name='Uso automático de Redação e revisão',exact=True)).to_be_enabled()
        general=page.get_by_role('checkbox',name='Ativar seleção automática geral',exact=True)
        await general.uncheck();await expect(general).to_be_enabled()
        await page.reload()
        await page.get_by_role('button',name='Plugins e Habilidades',exact=True).click()
        await expect(page.get_by_role('checkbox',name='Ativar seleção automática geral',exact=True)).not_to_be_checked()
        await page.get_by_role('checkbox',name='Ativar seleção automática geral',exact=True).check()
        await expect(page.get_by_role('checkbox',name='Ativar seleção automática geral',exact=True)).to_be_enabled()
        await page.get_by_role('button',name='Habilidades',exact=True).click()
        await expect(writing.get_by_role('checkbox',name='Uso automático de Redação e revisão',exact=True)).not_to_be_checked()
        await page.screenshot(path=str(out/'marketplace-habilidades.png'))
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await host.get_by_role('button',name='Selecionar habilidades',exact=True).click()
        skills=page.get_by_role('dialog',name='Habilidades desta conversa',exact=True)
        await skills.get_by_role('checkbox',name='Redação e revisão',exact=False).check()
        await page.screenshot(path=str(out/'habilidade-na-conversa.png'))
        await skills.get_by_role('button',name='Explorar habilidades',exact=True).click()
        await expect(page.get_by_role('button',name='Habilidades',exact=True)).to_have_attribute('aria-pressed','true')
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Calcule o resultado da expressão')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.locator('.tool-activity.done')).to_have_count(1)
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        generated=[v for key,v in handler.payloads if key=='generate']
        assert 'Revise e redija em português brasileiro' in generated[-1]['messages'][0]['content']
        assert json.loads(generated[-1]['messages'][-1]['content'])['result']==30
        await page.reload()
        await page.get_by_role('button',name='Calcule o resultado da expressão',exact=True).click()
        await expect(host.locator('.skills-trigger')).to_contain_text('1')
        await page.get_by_role('button',name='Plugins e Habilidades',exact=True).click()
        await page.get_by_role('button',name='Conexões MCP',exact=True).click()
        await page.get_by_role('button',name='Adicionar servidor',exact=True).click()
        dialog=page.get_by_role('dialog',name='Adicionar servidor MCP',exact=True)
        await dialog.get_by_label('Nome',exact=True).fill('MCP de teste')
        await dialog.get_by_role('button',name='Salvar servidor',exact=True).click()
        await expect(dialog.get_by_role('alert')).to_be_visible()
        await dialog.get_by_label('Programa',exact=True).fill(sys.executable)
        await dialog.get_by_label('Argumentos MCP',exact=True).fill(json.dumps([str(ROOT/'tests/fixtures/mcp_server.py')]))
        await dialog.get_by_role('button',name='Salvar servidor',exact=True).click()
        server=page.get_by_role('article',name='MCP de teste',exact=True)
        await expect(server).to_be_visible()
        await server.get_by_role('button',name='Conectar',exact=True).click()
        consent=page.get_by_role('dialog',name='Autorizar conexão MCP',exact=True)
        await consent.get_by_role('button',name='Cancelar',exact=True).click()
        await expect(server.get_by_role('button',name='Conectar',exact=True)).to_be_visible()
        await server.get_by_role('button',name='Conectar',exact=True).click()
        await consent.get_by_role('button',name='Autorizar e conectar',exact=True).click()
        await expect(server.get_by_role('button',name='Desconectar',exact=True)).to_be_visible(timeout=30000)
        await server.get_by_role('checkbox',name='sum_values',exact=True).check()
        await expect(server.get_by_role('checkbox',name='sum_values',exact=True)).to_be_enabled()
        response=await page.request.get(f'http://127.0.0.1:{port}/api/mcp')
        from backend.mcp_bridge import tool_alias
        handler.mcp_alias=tool_alias((await response.json())['servers'][0]['id'],'sum_values')
        await page.screenshot(path=str(out/'mcp-conectado.png'))
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await page.get_by_role('button',name='Nova conversa',exact=True).click()
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Consulte MCP para somar 20 e 22')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        mcp_approval=host.get_by_role('region',name='Aprovação pendente')
        await expect(mcp_approval).to_contain_text('MCP de teste')
        await mcp_approval.get_by_role('button',name='Permitir uma vez',exact=True).click()
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        await expect(host.locator('.tool-activity.done')).to_have_count(1)
        generated=[v for key,v in handler.payloads if key=='generate']
        mcp_result=json.loads(generated[-1]['messages'][-1]['content'])
        assert (mcp_result.get('structuredContent') or json.loads(mcp_result['content'][0]['text']))['total']==42
        await page.screenshot(path=str(out/'mcp-na-conversa.png'))
        await page.get_by_role('button',name='Plugins e Habilidades',exact=True).click()
        await page.get_by_role('button',name='Conexões MCP',exact=True).click()
        await server.get_by_role('button',name='Desconectar',exact=True).click()
        await page.get_by_role('button',name='Habilidades',exact=True).click()
        imported=b'---\nname: imported-checklist\ndescription: Imported checklist for targeted review.\n---\nUse CHECKLIST_IMPORTADO before answering. Preserve the user intent.\n'
        upload=io.BytesIO()
        with ZipFile(upload,'w') as archive:
            archive.writestr('SKILL.md',imported)
            archive.writestr('agents/openai.yaml','policy:\n  allow_implicit_invocation: false\n')
        await page.get_by_label('Importar pacote de extensão',exact=True).set_input_files({'name':'skill.zip','mimeType':'application/zip','buffer':upload.getvalue()})
        preview=page.get_by_role('dialog',name='Revisar importação',exact=True)
        await expect(preview).to_contain_text('imported-checklist')
        await preview.get_by_role('button',name='Confirmar instalação',exact=True).click()
        await expect(page.get_by_role('article',name='imported-checklist',exact=True)).to_be_visible()
        response=await page.request.get(f'http://127.0.0.1:{port}/api/extensions')
        imported_item=next(i for i in (await response.json())['items'] if i['name']=='imported-checklist')
        assert imported_item['implicit'] is False and imported_item['automatic'] is True
        handler.skill_id=imported_item['id']
        await page.screenshot(path=str(out/'habilidade-importada.png'))
        await page.get_by_role('button',name='Conversas',exact=True).click()
        await page.get_by_role('button',name='Nova conversa',exact=True).click()
        await host.get_by_role('textbox',name='Mensagem',exact=True).fill('Use automaticamente a habilidade de checklist')
        await host.get_by_role('button',name='Enviar',exact=True).click()
        await expect(host.locator('.tool-activity.done')).to_have_count(1)
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        generated=[v for key,v in handler.payloads if key=='generate']
        assert 'CHECKLIST_IMPORTADO' in generated[-1]['messages'][-1]['content']
        await page.screenshot(path=str(out/'habilidade-automatica.png'))
        await page.get_by_role('button',name='Nova conversa',exact=True).click()
        if await page.get_by_role('button',name='Fechar aviso').count():await page.get_by_role('button',name='Fechar aviso').click()

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
        await expect(host.locator('.message.user .message-time').last).to_have_text(__import__('re').compile(r'^\d{2}:\d{2}$'))
        await expect(host.locator('.message.assistant:not(.live) .message-time').last).to_have_attribute('datetime',__import__('re').compile(r'^\d{4}-.*Z$'))
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
        await expect(host.locator('.attachment-warning')).to_have_count(0,timeout=30000) # asynchronous metrics polling
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
        await expect(picker.locator('.directory-list')).to_have_attribute('aria-label','Pastas em '+str(project))
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
        assert await host.locator('.live [data-timeline-kind]').evaluate_all("els=>els.map(el=>el.dataset.timelineKind)")==['text','activity']
        assert not (project/'novo.txt').exists()
        await expect(approval).to_contain_text('Conteúdo criado pelo teste')
        await page.screenshot(path=str(out/'agente-build-aprovacao.png'))
        await approval.get_by_role('button',name='Permitir uma vez',exact=True).click()
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0)
        assert (project/'novo.txt').read_text()=='Conteúdo criado pelo teste de integração.\n'
        sequence=host.locator('.message.assistant:not(.live)').last.locator('[data-timeline-kind]')
        assert await sequence.evaluate_all("els=>els.map(el=>el.dataset.timelineKind)")==['text','activity','text']
        await page.reload()
        host=page.locator('.chat-host:not([hidden])')
        await page.get_by_role('button',name='Agente',exact=True).click()
        await page.get_by_role('button',name='Crie um arquivo novo.txt',exact=True).click()
        sequence=host.locator('.message.assistant:not(.live)').last.locator('[data-timeline-kind]')
        await expect(sequence).to_have_count(3)
        assert await sequence.evaluate_all("els=>els.map(el=>el.dataset.timelineKind)")==['text','activity','text']

        await page.screenshot(path=str(out/'agente-sequencia.png'))
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
        await expect(host.get_by_role('button',name='Interromper',exact=True)).to_have_count(0,timeout=20000)
        await expect(approval).to_have_count(0)
        await expect(host.locator('.tool-activity.done').filter(has_text='Buscar na internet')).to_have_count(1)
        for width,height in [(1586,992),(1366,768),(1024,600),(390,844),(390,500),(844,390)]:
            await page.set_viewport_size({'width':width,'height':height})
            bounds=await page.evaluate("""()=>{const c=document.querySelector('.chat-host:not([hidden]) .composer').getBoundingClientRect();return {w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight,bottom:c.bottom};}""")
            assert bounds['w']<=width and bounds['h']<=height+1 and bounds['bottom']<=height+1,bounds
            await page.screenshot(path=str(out/f'agente-{width}x{height}.png'))
            if (width,height)==(390,500):
                await page.get_by_role('button',name='Abrir menu',exact=True).click()
                await sidebar.evaluate('el=>el.scrollTop=0')
                assert await sidebar.evaluate("el=>el.scrollHeight>=el.clientHeight&&getComputedStyle(el.querySelector('nav')).overflowY==='visible'&&getComputedStyle(el.querySelector('.history-list')).overflowY==='visible'")
                await page.screenshot(path=str(out/'lateral-compacta-tela-menor.png'))
                await page.keyboard.press('Escape')
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
    print('v0.5 UI: marketplace, instalação/ativação, habilidades no pedido real, anexos, drag/drop, imagem e capacidade, Plan, Build com aprovação, acesso automático/completo, comandos reais, internet habilitada sem aprovação extra, rolagem lateral única, seis viewports: passaram.')

with tempfile.TemporaryDirectory() as directory:
    base=Path(directory);project=base/'projeto';project.mkdir();(project/'readme.txt').write_text('Projeto de teste')
    store=Store(base/'data');store.put('settings',{'engine_url':url,'executable':'','folders':[]})
    for index in range(35):store.conversation(f'Histórico de teste {index:02d}','chat')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=(ROOT/'work/features04-server.log').open('w')
    fixture_bootstrap="import runpy;import backend.agent_tools as t\nasync def search(query):return {'provider':'fixture de busca','results':[{'title':'Python fixture','url':'https://www.python.org/'}]}\nt.search_web=search\nrunpy.run_path('run.py',run_name='__main__')"
    process=subprocess.Popen([sys.executable,'-c',fixture_bootstrap,'--no-browser','--port',str(port),'--data-dir',str(base/'data')],stdout=log,stderr=log)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap',timeout=.3);break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Studio não iniciou')
        asyncio.run(check(port,project))
    finally:process.terminate();process.wait(timeout=10);log.close();fake.close()
