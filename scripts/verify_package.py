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
        ('Central-IA-Studio-Windows-x64.zip', {
            'ABRIR_CENTRAL_IA.cmd', 'LEIA-ME.txt',
            'CentralIAStudio/CentralIAStudio.exe',
            'CentralIAStudio/_internal/central-ia-studio-source.zip',
            'CentralIAStudio/engine/central-engine-nocuda.exe',
            'CentralIAStudio/engine/LICENSE', 'CentralIAStudio/engine/NOTICE.md',
            'CentralIAStudio/engine/third-party-licenses.zip',
            'CentralIAStudio/licencas/LICENSE', 'CentralIAStudio/licencas/NOTICES.md',
            'CentralIAStudio/licencas/THIRD_PARTY_FRONTEND.txt',
            'CentralIAStudio/licencas/THIRD_PARTY_PYTHON.txt'}),
        ('Central-IA-Studio-Fontes-e-Documentacao.zip', {
            'LEIA-ME.txt', 'Fontes/central-ia-studio-source.zip',
            'Fontes/Motor/llama-cpp-source.zip', 'Fontes/Motor/central-engine-source.zip',
            'Fontes/Motor/third-party-licenses.zip', 'Fontes/Motor/LICENSE',
            'Documentacao/README.md', 'Documentacao/docs/ATUALIZACAO_0_3_0.md',
            'Licencas/LICENSE', 'Licencas/THIRD_PARTY_FRONTEND.txt', 'Licencas/THIRD_PARTY_PYTHON.txt'}),
    ]
    lines = [verify(ROOT/name, required)+'  '+name for name, required in packages]
    (ROOT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
    print('Pacotes íntegros; hashes gravados em SHA256SUMS.txt')
