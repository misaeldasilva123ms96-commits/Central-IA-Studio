"""Run the actual frozen Windows application. Test tools are not runtime dependencies."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from zipfile import ZipFile
import httpx
import psutil

ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from backend.domain import Profile,build_command
from backend.storage import Store


def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

def memory(pid):
    try:
        p=psutil.Process(pid);info=p.memory_full_info()
        return {'rss':info.rss,'uss':getattr(info,'uss',None)}
    except psutil.Error:return {'rss':0,'uss':None}

def size(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())

def wait_dead(pid,timeout=12):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if not psutil.pid_exists(pid):return True
        time.sleep(.1)
    return False

def shell(script):
    result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return result.stdout.strip()

def deny_write(path,deny=True):
    # Deny specific writes, not generic W: generic write also includes
    # SYNCHRONIZE/READ_CONTROL required by CreateProcess on an executable.
    # A directory read-only attribute alone does not enforce this test.
    escaped=str(path).replace("'","''")
    if deny:shell(f"$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; & icacls '{escaped}' /deny \"*$($sid):(OI)(CI)(WD,AD,WEA,WA,D,DC)\" /T /C | Out-Null; if ($LASTEXITCODE) {{ exit 1 }}")
    else:shell(f"$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; & icacls '{escaped}' /remove:d \"*$sid\" /T /C | Out-Null")
    if deny:
        try:(Path(path)/'must-not-write').write_text('x')
        except PermissionError:return
        raise AssertionError('Read-only test precondition failed: ACL still permits writes')

def firewall(exe,name,enable=True):
    if enable:
        shell("if (@(Get-NetFirewallProfile | Where-Object { [string]$_.Enabled -ne 'True' }).Count) { throw 'Firewall profile disabled' }")
        program=str(exe).replace("'","''")
        shell(f"New-NetFirewallRule -DisplayName '{name}' -Direction Outbound -Action Block -Program '{program}' -RemoteAddress Internet -ErrorAction Stop | Out-Null")
    else:shell(f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue | Remove-NetFirewallRule")

class App:
    def __init__(self,exe,env,directory,extra=()):
        self.port=free_port();self.directory=directory;directory.mkdir(parents=True,exist_ok=True)
        self.output=open(directory/'app.log','ab');self.started=time.perf_counter()
        self.process=subprocess.Popen([str(exe),'--no-browser','--port',str(self.port),*extra],env=env,cwd=directory,stdout=self.output,stderr=subprocess.STDOUT)
        self.http=httpx.Client(base_url=f'http://127.0.0.1:{self.port}',timeout=30,trust_env=False)
        self.bootstrap=None
        for _ in range(900):
            if self.process.poll() is not None:break
            try:
                res=self.http.get('/api/bootstrap')
                if res.status_code==200:self.bootstrap=res.json();break
            except httpx.HTTPError:pass
            time.sleep(.1)
        if self.bootstrap is None:
            self.kill();raise RuntimeError('Frozen app failed to start: '+(directory/'app.log').read_text(errors='replace')[-6000:])
        self.startup=time.perf_counter()-self.started
        self.http.headers['X-Central-Token']=self.bootstrap['token']
        self.pid=self.bootstrap['runtime']['pid'];self.resources=Path(self.bootstrap['build'].get('resources_directory') or self.bootstrap['runtime']['resources_directory'])
    def api(self,path,data=None,method='POST'):
        res=self.http.get(path) if data is None else self.http.request(method,path,json=data)
        assert res.is_success,(path,res.status_code,res.text[:2000])
        return res.json()
    def close(self):
        started=time.perf_counter();self.api('/api/shutdown',{})
        self.process.wait(timeout=30);elapsed=time.perf_counter()-started
        self.http.close();self.output.close()
        assert self.process.returncode==0,('shutdown return code',self.process.returncode)
        assert wait_dead(self.pid)
        return elapsed
    def kill(self):
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=15);self.http.close();self.output.close()


def frontend(app,out):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--disable-background-networking','--no-first-run'])
        page=browser.new_page(viewport={'width':1366,'height':900});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{app.port}/');page.get_by_role('button',name='Conversas',exact=True).wait_for()
        page.get_by_role('button',name='Abrir ajustes do Central IA',exact=True).click()
        text=page.get_by_role('menu',name='Ajustes do Central IA').inner_text()
        assert app.bootstrap['version'] in text and app.bootstrap['commit'][:8] in text
        session=page.context.new_cdp_session(page);session.send('Performance.enable')
        metrics={m['name']:m['value'] for m in session.send('Performance.getMetrics')['metrics']}
        page.screenshot(path=str(out));assert not errors,errors
        version=browser.version;browser.close()
    return {'js_heap_used':metrics.get('JSHeapUsedSize'),'js_heap_total':metrics.get('JSHeapTotalSize'),'browser':version}


def start_engine(app,model):
    settings={'engine_url':'http://127.0.0.1:'+str(free_port()),'executable':app.bootstrap['settings']['executable'],'folders':[str(model.parent)]}
    app.api('/api/settings',settings,'PUT')
    for extension in app.api('/api/extensions')['items']:
        if extension['enabled']:app.api('/api/extensions/'+extension['id'],{'action':'disable'},'PATCH')
    profile=Profile(cache_kv='f16',flash_attention=False,max_output=8,auto_compact=False).model_dump()
    start=time.perf_counter();result=app.api('/api/engine/start',{'path':str(model),'profile':profile})
    for _ in range(600):
        if app.api('/api/engine')['connected']:break
        time.sleep(.1)
    else:raise AssertionError('Native engine did not load tiny fixture')
    return result['pid'],profile,time.perf_counter()-start


def seed_legacy(path):
    store=Store(path)
    cid=store.conversation('Histórico anterior à atualização')
    store.add_message(cid,'user','Pergunta persistida antes da migração')
    store.add_message(cid,'assistant','Resposta preservada')
    store.save_profile('default',Profile(temperature=.42).model_dump())
    store.put('skill_automation',{'enabled':False})
    with store.db() as db:db.execute('PRAGMA user_version=0')
    return cid


def expect_failure(exe,env,out,extra,pattern,port=None):
    started=time.monotonic()
    result=subprocess.run([str(exe),'--no-browser','--port',str(port or free_port()),*extra],env=env,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=40)
    text=result.stdout.decode(errors='replace')
    assert result.returncode!=0 and any(p.lower() in text.lower() for p in pattern),(result.returncode,text)
    return {'exit_code':result.returncode,'seconds':time.monotonic()-started,'message':text[-1200:]}


def run(mode,model,fixture_mcp):
    root=ROOT/'work'/('smoke '+mode);root.mkdir(parents=True,exist_ok=True)
    install=root/'application with spaces';install.mkdir(exist_ok=True)
    if mode=='onedir':
        with ZipFile(ROOT/'Central-IA-Studio-Windows-x64.zip') as archive:archive.extractall(install)
        exe=install/'CentralIAStudio/CentralIAStudio.exe'
    else:
        exe=install/'CentralIAStudio.exe';shutil.copy2(ROOT/'CentralIAStudio.exe',exe)
        assert [p.name for p in install.iterdir()]==['CentralIAStudio.exe']
    properties=json.loads(shell("(Get-Item '"+str(exe).replace("'","''")+"').VersionInfo | Select-Object FileVersion,ProductVersion,Comments | ConvertTo-Json"))
    expected_build=json.loads((ROOT/'work/freeze-resources/manifest.json').read_text())
    assert properties['FileVersion']==expected_build['version'] and expected_build['commit'] in properties['Comments']
    install_bytes=size(install)
    legacy=exe.parent/'data';legacy_cid=seed_legacy(legacy)
    env=os.environ.copy()
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','CENTRAL_DATA_DIR'):env.pop(key,None)
    env['PATH']=os.path.join(os.environ['SYSTEMROOT'],'System32')
    env['LOCALAPPDATA']=str(root/'user profile')
    temp=root/'temporary with spaces';temp.mkdir(exist_ok=True);env['TEMP']=env['TMP']=str(temp)
    rule='Central-IA-CI-'+mode;firewall(exe,rule)
    app=None;locked=False;checks=[];samples=[]
    report={'format':mode,'platform':sys.platform,'distributed_bytes':(ROOT/('CentralIAStudio.exe' if mode=='onefile' else 'Central-IA-Studio-Windows-x64.zip')).stat().st_size,'installed_bytes':install_bytes,'samples':samples,'checks':checks,'model':'tiny random untrained fixture; GGUF remains external','network_isolation':'Windows Firewall outbound Internet block; loopback allowed','runtime_path':env['PATH'],'model_path':str(model),'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest()}
    try:
        app=App(exe,env,root/'migration launch')
        build=app.bootstrap['build'];report['build']=build
        expected=json.loads((ROOT/'work/freeze-resources/manifest.json').read_text())
        for key in ('version','commit','schema','payload_digest','engine_sha256'):assert build[key]==expected[key]
        assert build['distribution']==mode and app.bootstrap['runtime']['process_guard']['enabled']
        data=Path(app.bootstrap['runtime']['data_directory'])
        assert data==Path(env['LOCALAPPDATA'])/'CentralIAStudio' and not data.is_relative_to(app.resources)
        assert app.bootstrap['runtime']['migration']['status']=='migrated'
        assert app.api('/api/conversations/'+legacy_cid)[0]['content']=='Pergunta persistida antes da migração'
        assert app.api('/api/profiles')['temperature']==.42 and app.api('/api/extensions/automation')['enabled'] is False
        assert (legacy/'central.sqlite3').is_file() and list((data/'backups').glob('*.sqlite3'))
        app.close();app=None;checks+=['migration_snapshot_source_preserved','shared_schema_version_commit','persistent_outside_resources']
        deny_write(install);locked=True
        for index in range(2):
            app=App(exe,env,root/('performance '+str(index)))
            assert len(app.api('/api/conversations/'+legacy_cid))==2
            record={'launch':index+1,'startup_seconds':app.startup,'manager_idle':memory(app.pid),'launcher_idle':memory(app.process.pid),'frontend':frontend(app,root/f'frontend-{index}.png')}
            engine_path=Path(app.bootstrap['settings']['executable'])
            assert engine_path.is_file() and hashlib.sha256(engine_path.read_bytes()).hexdigest()==build['engine_sha256']
            assert not list(install.rglob('*.gguf'))
            pid,profile,load=start_engine(app,model)
            record['profile']=profile
            record.update(engine_load_seconds=load,manager_with_engine=memory(app.pid),engine=memory(pid))
            record['temporary_extraction_bytes']=size(app.resources) if mode=='onefile' else 0
            conversation=app.api('/api/conversations',{'title':f'Chat real {mode} {index}'})['id']
            text=app.http.post('/api/generate',json={'conversation':conversation,'content':'Teste real do motor integrado','profile':profile},timeout=60).text
            assert 'event: done' in text and 'event: error' not in text,text
            assert app.api('/api/conversations/'+conversation)[-1]['stats']['generated_tokens'] is not None
            app.api('/api/engine/stop',{});assert wait_dead(pid)
            record['manager_after_stop']=memory(app.pid)
            resources=app.resources;record['shutdown_seconds']=app.close();app=None
            record['temporary_cleaned']=not resources.exists() if mode=='onefile' else None
            if mode=='onefile':assert record['temporary_cleaned']
            samples.append(record)
        checks+=['readonly_install_actual_acl','no_python_node_path','frontend_render_version_commit','builtin_engine_sha','real_engine_sse_sqlite','restart_persistence','normal_shutdown_no_orphans','normal_temp_cleanup','external_gguf_single_location']
        app=App(exe,env,root/'functional checks')
        from PIL import Image
        from pypdf import PdfWriter
        png=io.BytesIO();Image.new('RGB',(16,16),'red').save(png,format='PNG')
        pdf=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(pdf)
        for name,data_bytes,kind in [('note.txt',b'Attachment offline test','document'),('image.png',png.getvalue(),'image'),('file.pdf',pdf.getvalue(),'document')]:
            res=app.http.post('/api/attachments',params={'name':name},content=data_bytes,headers={'Content-Type':'application/octet-stream'},timeout=40)
            assert res.status_code==200 and res.json()['kind']==kind,res.text
        source=app.http.get('/api/source').content
        assert hashlib.sha256(source).hexdigest()==build['resources']['central-ia-studio-source.zip']
        license_items=app.api('/api/licenses')['licenses'];assert len(license_items)>=6
        example=app.http.get('/central-demo-plugin.zip').content
        preview=app.http.post('/api/extensions/import',params={'name':'demo.zip'},content=example).json()
        installed=app.http.post('/api/extensions/import',params={'name':'demo.zip','confirm':'true'},content=example,headers={'X-Import-Digest':preview['digest']})
        assert installed.status_code==200 and not installed.json()['servers'][0]['connected']
        server=app.api('/api/mcp',{'name':'MCP standalone CI','config':{'transport':'stdio','command':str(fixture_mcp),'args':[]}})['id']
        connected=app.api('/api/mcp/'+server+'/connect',{'confirmed':True})
        selected=next(s for s in connected['servers'] if s['id']==server)
        assert selected['connected'] and any(t['name']=='demo_sum' for t in selected['tools'])
        app.api('/api/mcp/'+server+'/disconnect',{})
        checks+=['offline_text_png_pdf_workers','sources_licenses_offline','plugins_skills_preserved','mcp_sdk_stdio_standalone_server']
        report['occupied_port_failure']=expect_failure(exe,env,root,[],['Porta','ocupada'],port=app.port)
        report['duplicate_data_failure']=expect_failure(exe,env,root,[],['dados já','dados j','uso por outra'])
        report['portable_readonly_failure']=expect_failure(exe,env,root,['--portable'],['pasta','escrita','Permission','permiss'])
        if mode=='onefile':
            bad=root/'extraction denied';bad.mkdir(exist_ok=True);deny_write(bad)
            try:
                blocked=dict(env,TEMP=str(bad),TMP=str(bad),TMPDIR=str(bad))
                report['extraction_failure']=expect_failure(exe,blocked,root,[],['temporary','temp','_MEI'])
            finally:deny_write(bad,False)
        pid,profile,_=start_engine(app,model)
        cid=app.api('/api/conversations',{'title':'Interromper geração real'})['id'];started=threading.Event();streamed=[]
        def stream():
            with app.http.stream('POST','/api/generate',json={'conversation':cid,'content':'Continue gerando','profile':profile|{'max_output':3000}},timeout=60) as response:
                for line in response.iter_lines():
                    streamed.append(line)
                    if line=='event: delta':started.set()
        worker=threading.Thread(target=stream);worker.start();assert started.wait(20)
        assert app.api('/api/abort',{})['interrupted'];worker.join(timeout=30);assert not worker.is_alive()
        assert 'event: done' in streamed
        app.api('/api/engine/stop',{});assert wait_dead(pid)
        checks.append('real_stream_abort_recover')
        # A server created by this test, not by the app, must survive app shutdown.
        port=free_port();external=subprocess.Popen(build_command(str(ROOT/'work/engine-package/central-engine-nocuda.exe'),str(model),Profile(cache_kv='f16',flash_attention=False),port),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            app.api('/api/settings',{'engine_url':f'http://127.0.0.1:{port}','executable':'','folders':[str(model.parent)]},'PUT')
            for _ in range(200):
                if app.api('/api/engine')['connected']:break
                time.sleep(.1)
            assert not app.api('/api/engine')['owned']
            collision=app.http.post('/api/engine/start',json={'path':str(model),'profile':profile})
            assert collision.status_code==400 and external.poll() is None
            app.api('/api/engine/stop',{});assert external.poll() is None
            app.close();app=None;assert external.poll() is None
        finally:external.terminate();external.wait(timeout=15)
        checks.append('external_engine_never_killed')
        app=App(exe,env,root/'forced termination');pid,_,_=start_engine(app,model);manager=app.pid;resources=app.resources
        app.kill();app=None;assert wait_dead(manager) and wait_dead(pid)
        report['forced_exit_temp_remains']=resources.exists() if mode=='onefile' else None
        checks.append('forced_launcher_exit_no_manager_engine_orphans')
        app=App(exe,env,root/'recovery after crash')
        assert app.api('/api/conversations/'+legacy_cid)[0]['content']=='Pergunta persistida antes da migração'
        app.close();app=None;checks.append('sqlite_recovery_after_forced_exit')
        # Common default LocalAppData, no GGUF/config copying between formats.
        cross=dict(env,LOCALAPPDATA=str(ROOT/'work/cross-distribution-profile'))
        app=App(exe,cross,root/'format interchange')
        titles=[c['title'] for c in app.api('/api/conversations')]
        if mode=='onefile':assert 'Intercâmbio onedir' in titles
        app.api('/api/conversations',{'title':'Intercâmbio '+mode})
        app.api('/api/profiles',Profile(temperature=.33).model_dump(),'PUT')
        report['cross_data_directory']=app.bootstrap['runtime']['data_directory']
        report['cross_title']='Intercâmbio '+mode
        report['features']={'extensions':sorted((i['id'],i['kind']) for i in app.api('/api/extensions')['items'] if i['bundled']),'mode_presets':app.bootstrap['mode_presets'],'schema':app.bootstrap['runtime']['schema'],'licenses_digest':hashlib.sha256(json.dumps(license_items,sort_keys=True).encode()).hexdigest()}
        app.close();app=None
        checks.append('shared_default_data_interchange')
        report['passed']=True
    except Exception as error:
        report['passed']=False;report['error']=repr(error)
        raise
    finally:
        if app:app.kill()
        if locked:deny_write(install,False)
        firewall(exe,rule,False)
        (ROOT/f'work/test-{mode}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('DISTRIBUTION_TEST_REPORT '+json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--format',required=True,choices=['onedir','onefile']);parser.add_argument('--model',required=True);parser.add_argument('--mcp-fixture',required=True)
    args=parser.parse_args();run(args.format,Path(args.model).resolve(),Path(args.mcp_fixture).resolve())
