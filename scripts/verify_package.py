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
    import json,shutil
    hashes={name:verify(ROOT/name,required) for name,required in packages}
    exe=ROOT/'CentralIAStudio.exe'
    if not exe.is_file() or exe.read_bytes()[:2]!=b'MZ':raise ValueError('ONEFILE Windows ausente ou inválido.')
    from PyInstaller.archive.readers import CArchiveReader
    reader=CArchiveReader(str(exe))
    if any(name.lower().endswith('.gguf') for name in reader.toc):raise ValueError('GGUF indevido no ONEFILE.')
    embedded=json.loads(reader.extract('build-info.json'))
    expected=json.loads((ROOT/'work/freeze-resources/onefile/build-info.json').read_text())
    if embedded!=expected:raise ValueError('A identificação embutida do ONEFILE diverge dos recursos atuais.')
    hashes[exe.name]=hashlib.sha256(exe.read_bytes()).hexdigest()
    manifest=json.loads((ROOT/'work/freeze-resources/manifest.json').read_text())
    (ROOT/'DISTRIBUTIONS.json').write_text(json.dumps({k:v for k,v in manifest.items() if k!='resources'}|{'artifacts':hashes},indent=2),encoding='utf-8')
    hashes['DISTRIBUTIONS.json']=hashlib.sha256((ROOT/'DISTRIBUTIONS.json').read_bytes()).hexdigest()
    for name in ['BUILD_REPORT.json','TEST_RESULTS.json']:
        if (ROOT/name).is_file():hashes[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    lines=[digest+'  '+name for name,digest in hashes.items()]
    (ROOT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
    for mode,primary in [('onedir','Central-IA-Studio-Windows-x64.zip'),('onefile','CentralIAStudio.exe'),('sources','Central-IA-Studio-Fontes-e-Documentacao.zip')]:
        stage=ROOT/'work/artifacts'/mode
        if stage.exists():shutil.rmtree(stage)
        stage.mkdir(parents=True)
        names=[primary,'DISTRIBUTIONS.json',*[n for n in ['BUILD_REPORT.json','TEST_RESULTS.json'] if n in hashes]]
        for name in names:shutil.copy2(ROOT/name,stage/name)
        (stage/'SHA256SUMS.txt').write_text('\n'.join(hashes[name]+'  '+name for name in names)+'\n')
        if mode=='sources':shutil.copy2(ROOT/'SHA256SUMS.txt',stage/'SHA256SUMS_ALL.txt')
    print('Pacotes íntegros; hashes gravados em SHA256SUMS.txt')
