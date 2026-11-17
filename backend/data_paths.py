"""Shared writable data, explicit portable mode and non-destructive legacy migration."""
from contextlib import closing,nullcontext
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
from urllib.parse import quote
import uuid
from .runtime import SOURCE_ROOT,executable_directory,resource_root

class DataLock:
    def __init__(self,path,filename='.central.lock'):
        self.path=Path(path)/filename;self.file=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.is_symlink():raise ValueError('Arquivo de bloqueio não pode ser um link.')
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        self.file=os.fdopen(fd,'r+b')
        self.file.seek(0,2)
        if self.file.tell()==0:self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            self.file.close();self.file=None
            raise ValueError('Esta pasta de dados já está em uso por outra instância. Feche-a antes de continuar.') from error
        return self
    def __exit__(self,*args):
        if self.file:
            if os.name=='nt':
                import msvcrt
                self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_UN)
            self.file.close();self.file=None


def reject_resource_data(path):
    if getattr(sys,'frozen',False) and path.is_relative_to(resource_root()):
        raise ValueError('Dados persistentes não podem ficar na pasta temporária/interna do PyInstaller. Use --data-dir em uma pasta gravável.')


def migrate(source,target):
    source=Path(source).resolve();target=Path(target).resolve()
    if source==target:return {'status':'same','source':str(source)}
    if source.is_relative_to(target) or target.is_relative_to(source):raise ValueError('Origem e destino da migração não podem conter um ao outro.')
    if target.exists() and any(target.iterdir()):raise ValueError('O destino já contém dados. A migração não sobrescreve nem mescla bases; use outra pasta vazia.')
    database=source/'central.sqlite3'
    if not database.is_file() or database.is_symlink():raise ValueError('A origem não contém um SQLite regular do Central IA Studio.')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=target.parent/('.central-migrating-'+uuid.uuid4().hex);stage.mkdir()
    try:
        with closing(sqlite3.connect('file:'+quote(str(database).replace('\\','/'),safe='/:')+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(stage/'central.sqlite3')) as new:
            if old.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('A base antiga está inconsistente. Origem preservada; restaure um backup antes de migrar.')
            old.backup(new)
            if new.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Falha ao verificar a cópia migrada.')
        (stage/'backups').mkdir()
        backup='antes-da-migracao-'+uuid.uuid4().hex+'.sqlite3'
        shutil.copy2(stage/'central.sqlite3',stage/'backups'/backup)
        skipped=[]
        for item in source.rglob('*'):
            rel=item.relative_to(source)
            if item.is_symlink() or getattr(item,'is_junction',lambda:False)():raise ValueError('A origem contém links. Selecione uma pasta regular ou use --data-dir sem copiar os dados.')
            if item.is_dir():continue
            if rel.parts[0] in ('central.sqlite3','central.sqlite3-wal','central.sqlite3-shm','.central.lock'):continue
            if item.suffix.lower()=='.gguf':skipped.append(str(rel));continue
            if str(rel)=='migration.json':rel=Path('backups')/('migration-source-'+uuid.uuid4().hex+'.json')
            dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():raise ValueError('Conflito com arquivo de backup na origem. Use uma pasta de destino diferente e revise os dados.')
            shutil.copy2(item,dest)
        # Only the known old bundled engine is normalized; external programs and GGUF paths stay untouched.
        with closing(sqlite3.connect(stage/'central.sqlite3')) as db:
            row=db.execute("SELECT value FROM settings WHERE key='settings'").fetchone()
            if row:
                settings=json.loads(row[0]);exe=settings.get('executable','')
                expected=source.parent/'engine'/'central-engine-nocuda.exe'
                if exe and Path(exe).resolve()==expected.resolve():
                    settings['executable']='';db.execute("UPDATE settings SET value=? WHERE key='settings'",(json.dumps(settings),))
            db.commit()
        report={'status':'migrated','source':str(source),'destination':str(target),'created':time.time(),'gguf_not_copied':skipped,'source_preserved':True,'backup':'backups/'+backup}
        (stage/'migration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if target.exists():target.rmdir()  # only an empty destination, never user files
        stage.rename(target)
        return report
    finally:
        if stage.exists():shutil.rmtree(stage)


def resolve_data(override=None,portable=False,migrate_from=None):
    explicit=override or os.environ.get('CENTRAL_DATA_DIR')
    if portable and explicit:raise ValueError('Escolha --portable ou --data-dir/CENTRAL_DATA_DIR, sem combinar os modos.')
    if explicit:target=Path(explicit).expanduser().resolve()
    elif portable:target=(executable_directory()/'data').resolve()
    elif getattr(sys,'frozen',False) or os.name=='nt':
        target=(Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'CentralIAStudio').resolve()
    else:target=(SOURCE_ROOT/'data').resolve()
    reject_resource_data(target)
    legacy=Path(migrate_from).expanduser().resolve() if migrate_from else executable_directory()/'data'
    report={'status':'existing' if (target/'central.sqlite3').is_file() else 'new','destination':str(target),'portable':portable}
    target.parent.mkdir(parents=True,exist_ok=True)
    # Serialize the initial copy before the regular per-database lock can exist.
    lock=DataLock(target.parent,filename='.'+target.name+'-migration.lock') if migrate_from or (not explicit and not portable) else nullcontext()
    with lock:
        if migrate_from:
            report=migrate(legacy,target)|{'portable':portable}
        elif not explicit and not portable and legacy.resolve()!=target and (legacy/'central.sqlite3').is_file():
            if not target.exists() or not any(target.iterdir()):report=migrate(legacy,target)|{'portable':False}
            else:report['notice']='Há uma base antiga em '+str(legacy)+'. Ela foi preservada e não foi mesclada com a base compartilhada.'
        target.mkdir(parents=True,exist_ok=True)
        probe=target/('.write-test-'+uuid.uuid4().hex)
        try:
            with probe.open('xb'):pass
            probe.unlink()
        except OSError as error:raise ValueError('A pasta de dados não permite escrita. Use --data-dir em uma pasta gravável.') from error
    return target,report
