"""Valida os ZIPs distribuíveis e gera seus hashes SHA-256."""
import hashlib
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent

def verify(path, required):
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP corrompido: '+str(path))
        names = {n.replace('\\', '/') for n in archive.namelist()}
        if not required <= names:
            raise ValueError('Arquivos ausentes: '+str(required-names))
        for name in names:
            if name.startswith('/') or '..' in name.split('/') or name.lower().endswith('.gguf'):
                raise ValueError('Entrada indevida: '+name)
    return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__ == '__main__':
    packages = [
        ('Central-IA-Studio-Windows-x64.zip', {'CentralIAStudio/CentralIAStudio.exe', 'CentralIAStudio/engine/central-engine-nocuda.exe', 'CentralIAStudio/engine/llama-cpp-source.zip', 'CentralIAStudio/engine/central-engine-source.zip', 'CentralIAStudio/engine/third-party-licenses.zip', 'INICIAR_CENTRAL_IA_STUDIO.cmd', 'central-ia-studio-source.zip', 'LICENSE', 'NOTICES.md', 'THIRD_PARTY_FRONTEND.txt', 'THIRD_PARTY_PYTHON.txt'}),
        ('central-ia-studio-source.zip', {'backend/app.py', 'frontend/dist/index.html', 'README.md', 'LICENSE'}),
    ]
    lines = [verify(ROOT/name, required)+'  '+name for name, required in packages]
    (ROOT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
    print('Pacotes íntegros; hashes gravados em SHA256SUMS.txt')
