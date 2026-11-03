import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path('work/qa');out.mkdir(parents=True,exist_ok=True);errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765/')
    page.get_by_role('heading',name='Sua IA, no seu computador.').wait_for()
    page.screenshot(path=str(out/'desktop.png'),full_page=True)
    assert page.get_by_role('button',name='Enviar',exact=True).is_disabled()
    page.get_by_role('button',name='Configurar conexão',exact=True).click()
    page.get_by_role('button',name='Salvar conexão',exact=True).click()
    page.get_by_role('alert').filter(has_text='Configuração salva').wait_for()
    page.get_by_role('button',name='Parâmetros',exact=True).click()
    output=page.get_by_text('Saída máxima (tokens)',exact=True).locator('..').locator('input')
    output.fill('10000')
    page.get_by_role('button',name='Salvar parâmetros',exact=True).click()
    page.get_by_role('alert').filter(has_text='Parâmetros salvos').wait_for()
    page.reload()
    page.get_by_role('button',name='Parâmetros',exact=True).click()
    assert page.get_by_text('Saída máxima (tokens)',exact=True).locator('..').locator('input').input_value()=='10000'
    page.get_by_role('button',name='Modelos',exact=True).click()
    page.get_by_role('heading',name='Nenhum GGUF encontrado.').wait_for()
    page.wait_for_function('scrollY === 0')
    assert page.locator('header').bounding_box()['y']==0
    page.screenshot(path=str(out/'models.png'),full_page=False)
    page.get_by_role('button',name='Monitoramento',exact=True).click()
    page.get_by_role('heading',name='Monitoramento local').wait_for()
    assert page.get_by_text('RAM do sistema',exact=True).count()==1
    page.get_by_role('button',name='Benchmarks',exact=True).click()
    page.get_by_text('Nenhuma avaliação registrada.',exact=True).wait_for()
    page.get_by_role('button',name='Conversas',exact=True).click()
    page.get_by_role('button',name='Ativar tema claro').click()
    assert page.locator('html').get_attribute('data-theme')=='light'
    page.get_by_role('button',name='Ativar tema escuro').click()
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='Abrir menu').click()
    page.get_by_role('button',name='Modelos',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(out/'mobile-models.png'),full_page=True)
    page.get_by_role('button',name='Abrir menu').click()
    page.get_by_role('button',name='Conversas',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    browser.close()
assert not errors,errors
(out/'browser-results.json').write_text(json.dumps({'passed':True,'viewport_desktop':[1440,900],'viewport_mobile':[390,844],'page_errors':errors,'checks':['disconnected send disabled','settings persisted','numeric max output 10000 persisted across reload','empty model library','monitoring','benchmark empty state','light and dark themes','mobile navigation','no horizontal overflow']},indent=2))
print('Browser checks passed; no page errors')
