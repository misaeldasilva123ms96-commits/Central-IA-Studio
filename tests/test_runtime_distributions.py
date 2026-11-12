import asyncio
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from test_central import client,fake_engine,gguf
from backend.storage import Store
from backend.data_paths import DataLock,migrate,resolve_data
from backend import runtime


def test_migration_keeps_sqlite_blobs_profiles_backups_and_originals(tmp_path):
    legacy=tmp_path/'old application/data';store=Store(legacy);cid=store.conversation('Histórico')
    store.add_message(cid,'user','pergunta');store.put('context:'+cid,{'summary':'memória'});store.save_profile('default',{'temperature':.42})
    store.put('settings',{'folders':['D:/GGUF externo'],'executable':str(legacy.parent/'engine/central-engine-nocuda.exe')})
    (legacy/'extensions/a').mkdir(parents=True);(legacy/'extensions/a/ref.md').write_text('referência')
    (legacy/'model.gguf').write_bytes(b'not copied')
    before=(legacy/'central.sqlite3').read_bytes();target=tmp_path/'profile/CentralIAStudio'
    report=migrate(legacy,target);new=Store(target)
    assert (legacy/'central.sqlite3').read_bytes()==before
    assert new.messages(cid)[0]['content']=='pergunta' and new.get('context:'+cid)['summary']=='memória'
    assert new.profile('default')['temperature']==.42
    assert new.get('settings')=={'folders':['D:/GGUF externo'],'executable':''}
    assert not (target/'model.gguf').exists() and (legacy/'model.gguf').exists()
    assert (target/'extensions/a/ref.md').read_text()=='referência' and (target/report['backup']).is_file()
    assert report['source_preserved'] and report['gguf_not_copied']==['model.gguf']
    with pytest.raises(ValueError,match='não sobrescreve'):migrate(legacy,target)
    assert new.messages(cid)[0]['content']=='pergunta'


def test_migration_refuses_corrupt_source_and_links(tmp_path):
    source=tmp_path/'source';source.mkdir();(source/'central.sqlite3').write_bytes(b'corrupt')
    with pytest.raises((ValueError,sqlite3.DatabaseError)):migrate(source,tmp_path/'target')
    assert not (tmp_path/'target').exists() and (source/'central.sqlite3').read_bytes()==b'corrupt'
    (source/'central.sqlite3').unlink();Store(source)
    if os.name!='nt':
        (source/'link').symlink_to(tmp_path)
        with pytest.raises(ValueError,match='links'):migrate(source,tmp_path/'target')
    with pytest.raises(ValueError,match='conter'):migrate(source,source/'child')


def test_data_lock_is_exclusive_and_released(tmp_path):
    with DataLock(tmp_path):
        with pytest.raises(ValueError,match='instância'):
            with DataLock(tmp_path):pass
    with DataLock(tmp_path):pass


def test_defaults_shared_portable_explicit_and_not_resource_root(tmp_path,monkeypatch):
    from backend import data_paths
    resources=tmp_path/'_MEI-test';resources.mkdir();application=tmp_path/'application';application.mkdir()
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'_MEIPASS',str(resources),raising=False)
    monkeypatch.setattr(data_paths,'executable_directory',lambda:application)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'profile'));monkeypatch.delenv('CENTRAL_DATA_DIR',raising=False)
    path,_=resolve_data();assert path==tmp_path/'profile/CentralIAStudio'
    portable,_=resolve_data(portable=True);assert portable==application/'data'
    explicit,_=resolve_data(tmp_path/'custom');assert explicit==tmp_path/'custom'
    with pytest.raises(ValueError,match='PyInstaller'):resolve_data(resources/'data')
    monkeypatch.setenv('CENTRAL_DATA_DIR',str(tmp_path/'environment'))
    assert resolve_data()[0]==tmp_path/'environment'
    with pytest.raises(ValueError,match='sem combinar'):resolve_data(portable=True)


def test_automatic_copy_once_never_merges_second_source(tmp_path,monkeypatch):
    from backend import data_paths
    app=tmp_path/'install';cid=Store(app/'data').conversation('first')
    monkeypatch.setattr(data_paths,'executable_directory',lambda:app)
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path/'resources'),raising=False)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'profile'));monkeypatch.delenv('CENTRAL_DATA_DIR',raising=False)
    target,report=resolve_data();assert report['status']=='migrated'
    Store(app/'data').conversation('later source entry')
    _,again=resolve_data();assert again['status']=='existing' and 'notice' in again
    with Store(target).db() as db:assert db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]==1


def test_bundled_engine_from_resources_or_sidecar(tmp_path,monkeypatch):
    resources=tmp_path/'_MEI-test';side=tmp_path/'application';name='central-engine-nocuda.exe' if os.name=='nt' else 'central-engine-nocuda'
    (resources/'engine').mkdir(parents=True);(side/'engine').mkdir(parents=True)
    (resources/'engine'/name).write_bytes(b'engine');(side/'engine'/name).write_bytes(b'engine')
    monkeypatch.setattr(runtime,'resource_root',lambda:resources);monkeypatch.setattr(runtime,'executable_directory',lambda:side)
    assert runtime.bundled_engine()==str(resources/'engine'/name)
    assert runtime.canonical_executable(runtime.bundled_engine())==''
    (resources/'engine'/name).unlink();assert runtime.bundled_engine()==str(side/'engine'/name)
    assert runtime.canonical_executable('custom external program')=='custom external program'


def test_newer_schema_is_refused_without_dropping_data(tmp_path):
    store=Store(tmp_path);store.put('keep','value')
    with store.db() as db:db.execute('PRAGMA user_version=999')
    with pytest.raises(ValueError,match='versão mais nova'):Store(tmp_path)
    with sqlite3.connect(store.path) as db:assert db.execute("SELECT value FROM settings WHERE key='keep'").fetchone()[0]=='"value"'


def test_shared_http_pool_is_bounded_and_closed(client,fake_engine):
    engine=client.app.state.engine
    async def check():
        for _ in range(4):assert (await engine.status())['connected']
        assert len(engine._http_clients)==1
        original=list(engine._http_clients.values());await engine.close_http_pool()
        assert all(c.is_closed for c in original)
    client.portal.call(check)


def test_cached_metadata_tracks_replacements(tmp_path):
    from backend.gguf import metadata,_cached_metadata
    path=gguf(tmp_path/'model.gguf');_cached_metadata.cache_clear()
    first=metadata(path);first['quantization']='modified return value'
    assert metadata(path)['quantization']=='Q4_K_M' and _cached_metadata.cache_info().hits>=1
    path.write_bytes(b'BAD!'+path.read_bytes()[4:])
    with pytest.raises(ValueError,match='Assinatura'):metadata(path)


def test_heavy_parsers_are_lazy_in_clean_process():
    text=subprocess.check_output([sys.executable,'-c',"import backend.attachments,sys; print('pypdf' in sys.modules, 'PIL.Image' in sys.modules)"],text=True)
    assert text.strip()=='False False'


def test_source_packager_does_not_include_untracked_private_files(tmp_path,monkeypatch):
    from scripts import package_source
    subprocess.run(['git','init',str(tmp_path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (tmp_path/'app.py').write_text('safe source');(tmp_path/'private.py').write_text('do not ship');(tmp_path/'.env').write_text('TOKEN=secret')
    subprocess.run(['git','-C',str(tmp_path),'add','app.py','.env'],check=True)
    monkeypatch.setattr(package_source,'ROOT',tmp_path)
    assert [str(rel) for _,rel in package_source.source_files()]==['app.py']


def test_launcher_cannot_be_started_as_inference_engine(tmp_path):
    from backend.domain import build_command,Profile
    launcher=tmp_path/'CentralIAStudio.exe';launcher.write_bytes(b'MZtest')
    model=gguf(tmp_path/'model.gguf')
    with pytest.raises(ValueError,match='aplicativo, não o motor'):build_command(str(launcher),str(model),Profile(),5001)
