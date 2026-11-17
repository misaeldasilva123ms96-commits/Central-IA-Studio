"""Create one immutable resource input for both PyInstaller distributions."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parent.parent


def prepare(root=ROOT):
    sys.path.insert(0,str(ROOT))
    from backend.runtime import DATA_SCHEMA
    root=Path(root);out=root/'work/freeze-resources'
    if out.exists():shutil.rmtree(out)
    common=out/'common';common.mkdir(parents=True)
    engine=root/'work/engine-package'
    required=['central-engine-nocuda.exe','LICENSE','NOTICE.md','third-party-licenses.zip']
    for name in required:
        if not (engine/name).is_file():raise ValueError('Motor aprovado incompleto: '+name)
    shutil.copytree(root/'frontend/dist',common/'frontend/dist')
    (common/'engine').mkdir()
    for path in engine.iterdir():
        if path.name in required or path.suffix.lower()=='.dll':shutil.copy2(path,common/'engine'/path.name)
    (common/'licencas').mkdir()
    for name in ['LICENSE','NOTICES.md','THIRD_PARTY_FRONTEND.txt','THIRD_PARTY_PYTHON.txt']:shutil.copy2(root/name,common/'licencas'/name)
    for name in ['LICENSE','NOTICES.md','central-ia-studio-source.zip']:shutil.copy2(root/name,common/name)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    version=json.loads((root/'frontend/package.json').read_text())['version']
    files={str(p.relative_to(common)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(common.rglob('*')) if p.is_file()}
    if any(name.lower().endswith('.gguf') for name in files):raise ValueError('Modelos GGUF não podem fazer parte do executável.')
    digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    base={'version':version,'commit':commit,'schema':DATA_SCHEMA,'payload_digest':digest,'engine_sha256':files['engine/central-engine-nocuda.exe'],'resources':files,'python':sys.version.split()[0]}
    number=tuple(int(v) for v in version.split('.'))+(0,)
    if len(number)!=4:raise ValueError('Versão precisa seguir major.minor.patch.')
    text="VSVersionInfo(ffi=FixedFileInfo(filevers="+repr(number)+",prodvers="+repr(number)+",mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('CompanyName','Central IA Studio'),StringStruct('FileDescription','Central IA Studio'),StringStruct('FileVersion',"+repr(version)+"),StringStruct('InternalName','CentralIAStudio'),StringStruct('OriginalFilename','CentralIAStudio.exe'),StringStruct('ProductName','Central IA Studio'),StringStruct('ProductVersion',"+repr(version)+"),StringStruct('Comments',"+repr('Commit '+commit)+")])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])"
    (out/'windows-version.txt').write_text(text,encoding='utf-8')
    for mode in ['onedir','onefile']:
        folder=out/mode;folder.mkdir()
        (folder/'build-info.json').write_text(json.dumps(base|{'distribution':mode},indent=2),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps(base,indent=2),encoding='utf-8')
    print(f'Recursos comuns: {version} {commit} {digest}')
    return base

if __name__=='__main__':prepare()
