"""Packaging paths. User data never belongs to the PyInstaller resource directory."""
import json
import os
from pathlib import Path
import subprocess
import sys

SOURCE_ROOT=Path(__file__).resolve().parent.parent
DATA_SCHEMA=1


def resource_root():
    return Path(getattr(sys,'_MEIPASS',SOURCE_ROOT)).resolve()


def executable_directory():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else SOURCE_ROOT


def bundled_engine():
    name='central-engine-nocuda.exe' if os.name=='nt' else 'central-engine-nocuda'
    for path in [resource_root()/'engine'/name,executable_directory()/'engine'/name]:
        if path.is_file():return str(path)
    return ''


def canonical_executable(value):
    if not value:return ''
    current=bundled_engine()
    if current and Path(value).resolve()==Path(current).resolve():return ''
    # A previous onefile temp directory must never remain a persisted engine path.
    if Path(value).name.lower()=='central-engine-nocuda.exe' and any(p.startswith('_MEI') for p in Path(value).parts):return ''
    return value


def build_info():
    path=resource_root()/'build-info.json'
    if path.is_file():
        result=json.loads(path.read_text(encoding='utf-8'))
        if result.get('distribution') not in ('onefile','onedir') or len(result.get('commit',''))!=40:
            raise ValueError('Identificação do pacote inválida. Baixe novamente o pacote completo.')
        return result
    if getattr(sys,'frozen',False):raise ValueError('Identificação do pacote ausente. Baixe novamente o pacote completo.')
    version=json.loads((SOURCE_ROOT/'frontend/package.json').read_text())['version']
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE_ROOT,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit='desenvolvimento'
    return {'version':version,'commit':commit,'distribution':'source','schema':DATA_SCHEMA,'payload_digest':None}
