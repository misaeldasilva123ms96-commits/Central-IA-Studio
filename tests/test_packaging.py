"""The portable package must retain runtime resources and offline source access."""
import io
from pathlib import Path
from zipfile import ZipFile
import pytest
from scripts.package_windows import package
from scripts.verify_package import verify


def zip_bytes(name, content):
    buffer=io.BytesIO()
    with ZipFile(buffer,'w') as archive:
        archive.writestr(name,content)
    return buffer.getvalue()


def test_separate_runtime_and_complete_sources(tmp_path):
    def put(name,content):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    source=zip_bytes('backend/app.py',b'# corresponding Studio source')
    put('dist/CentralIAStudio/CentralIAStudio.exe',b'test-only frozen executable')
    put('dist/CentralIAStudio/_internal/runtime.dll',b'unchanged runtime resource')
    put('dist/CentralIAStudio/_internal/frontend/dist/index.html',b'interface')
    put('dist/CentralIAStudio/_internal/central-ia-studio-source.zip',source)
    put('central-ia-studio-source.zip',source)
    put('work/engine-package/central-engine-nocuda.exe',b'test-only native executable')
    for name in ['llama-cpp-source.zip','central-engine-source.zip','third-party-licenses.zip']:
        put('work/engine-package/'+name,zip_bytes('content.txt',name.encode()))
    for name in ['LICENSE','NOTICE.md','README.md','SHA256SUMS.txt']:
        put('work/engine-package/'+name,name.encode())
    for name in ['LICENSE','NOTICES.md','THIRD_PARTY_FRONTEND.txt','THIRD_PARTY_PYTHON.txt','README.md']:
        put(name,name.encode())
    put('INICIAR_CENTRAL_IA_STUDIO.cmd',b'@echo off\r\nCentralIAStudio\\CentralIAStudio.exe')
    put('docs/guia.md','Guia completo ç'.encode())
    app,extras=package(tmp_path)
    verify(app,{'ABRIR_CENTRAL_IA.cmd','CentralIAStudio/CentralIAStudio.exe'})
    verify(extras,{'Fontes/Motor/llama-cpp-source.zip','Documentacao/docs/guia.md'})
    with ZipFile(app) as archive:
        names=set(archive.namelist())
        assert {name.split('/')[0] for name in names}=={'ABRIR_CENTRAL_IA.cmd','LEIA-ME.txt','CentralIAStudio'}
        assert archive.read('CentralIAStudio/_internal/runtime.dll')==b'unchanged runtime resource'
        assert archive.read('CentralIAStudio/engine/central-engine-nocuda.exe')==b'test-only native executable'
        assert archive.read('CentralIAStudio/_internal/central-ia-studio-source.zip')==source
        assert archive.read('CentralIAStudio/licencas/THIRD_PARTY_PYTHON.txt')==b'THIRD_PARTY_PYTHON.txt'
        assert not any('llama-cpp-source.zip' in name or name.startswith('docs/') for name in names)
        with ZipFile(io.BytesIO(archive.read('CentralIAStudio/_internal/central-ia-studio-source.zip'))) as embedded:
            assert embedded.read('backend/app.py')==b'# corresponding Studio source'
    with ZipFile(extras) as archive:
        assert archive.read('Fontes/central-ia-studio-source.zip')==source
        assert archive.read('Fontes/Motor/llama-cpp-source.zip')==(tmp_path/'work/engine-package/llama-cpp-source.zip').read_bytes()
        assert archive.read('Documentacao/docs/guia.md').decode()=='Guia completo ç'
        assert not any(name.endswith(('.exe','.gguf')) for name in archive.namelist())
    # An incomplete runtime must never produce a plausible replacement ZIP.
    (tmp_path/'dist/CentralIAStudio/_internal/central-ia-studio-source.zip').unlink()
    before=app.read_bytes()
    with pytest.raises(ValueError,match='ausente'):
        package(tmp_path)
    assert app.read_bytes()==before
