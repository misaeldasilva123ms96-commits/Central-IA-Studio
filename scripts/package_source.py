"""Pacote de fontes sem modelos, motores, dados do usuário ou arquivos de trabalho."""
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT=Path(__file__).resolve().parent.parent
EXCLUDED={'.git','work','node_modules','__pycache__','.pytest_cache','.venv','data','build'}

def source_files():
    paths=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if p.name == 'SHA256SUMS.txt' or not p.is_file() or set(rel.parts)&EXCLUDED or rel.parts[0]=='dist' or p.suffix.lower() in ['.exe','.gguf','.zip','.pyc','.spec']:
            continue
        paths.append((p,rel))
    return paths

def package(destination):
    paths=source_files()
    with ZipFile(destination,'w',ZIP_DEFLATED) as z:
        for p,rel in paths:
            z.write(p,str(rel))
    with ZipFile(destination) as z:
        assert z.testzip() is None
        assert 'frontend/dist/index.html' in z.namelist()
        assert 'backend/app.py' in z.namelist()
        assert not any(n.endswith(('.gguf','.exe')) for n in z.namelist())
    digest=hashlib.sha256(Path(destination).read_bytes()).hexdigest()
    ROOT.joinpath('SHA256SUMS.txt').write_text(digest+'  '+Path(destination).name+'\n')
    print(f'{destination}: {len(paths)} arquivos; SHA256 {digest}')
    return digest

if __name__=='__main__':
    package(ROOT/'central-ia-studio-source.zip')
