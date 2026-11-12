"""Separate the portable runtime from complete development materials."""
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
APP_ZIP = 'Central-IA-Studio-Windows-x64.zip'
EXTRAS_ZIP = 'Central-IA-Studio-Fontes-e-Documentacao.zip'
RUNTIME_ENGINE = ('central-engine-nocuda.exe', 'LICENSE', 'NOTICE.md', 'third-party-licenses.zip')
NOTICES = ('LICENSE', 'NOTICES.md', 'THIRD_PARTY_FRONTEND.txt', 'THIRD_PARTY_PYTHON.txt')


def zip_tree(directory, destination):
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for file in sorted(directory.rglob('*')):
            if file.is_file():
                archive.write(file, file.relative_to(directory).as_posix(),
                              compress_type=ZIP_STORED if file.suffix.lower()=='.zip' else ZIP_DEFLATED)


def package(root=ROOT):
    root = Path(root)
    studio = root/'dist/CentralIAStudio'
    engine = root/'work/engine-package'
    # Fail before writing output if either distribution is incomplete.
    for file in [studio/'CentralIAStudio.exe', studio/'_internal/central-ia-studio-source.zip',
                 root/'dist/onefile/CentralIAStudio.exe',
                 studio/'_internal/build-info.json',root/'work/freeze-resources/onefile/build-info.json',
                 *(engine/name for name in RUNTIME_ENGINE),
                 engine/'llama-cpp-source.zip', engine/'central-engine-source.zip',
                 root/'central-ia-studio-source.zip', *(root/name for name in NOTICES)]:
        if not file.is_file():
            raise ValueError('Arquivo necessário ao pacote ausente: '+str(file))
    import json
    a=json.loads((studio/'_internal/build-info.json').read_text())
    b=json.loads((root/'work/freeze-resources/onefile/build-info.json').read_text())
    if a['distribution']!='onedir' or b['distribution']!='onefile' or {k:v for k,v in a.items() if k!='distribution'}!={k:v for k,v in b.items() if k!='distribution'}:
        raise ValueError('As distribuições não correspondem ao mesmo código/recursos.')
    (root/'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='release-',dir=root/'work') as temporary:
        stage = Path(temporary)
        runtime = stage/'app'
        shutil.copytree(studio, runtime/'CentralIAStudio')
        runtime_engine = runtime/'CentralIAStudio/engine'
        # This directory is assembled explicitly: engine sources live in the other ZIP.
        if runtime_engine.exists():
            shutil.rmtree(runtime_engine)
        runtime_engine.mkdir()
        for file in engine.iterdir():
            if file.name in RUNTIME_ENGINE or file.suffix.lower()=='.dll':shutil.copy2(file,runtime_engine/file.name)
        internal_engine=runtime/'CentralIAStudio/_internal/engine'
        if internal_engine.exists():shutil.rmtree(internal_engine)
        notices = runtime/'CentralIAStudio/licencas'
        notices.mkdir(exist_ok=True)
        for name in NOTICES:
            shutil.copy2(root/name, notices/name)
        shutil.copy2(root/'INICIAR_CENTRAL_IA_STUDIO.cmd', runtime/'ABRIR_CENTRAL_IA.cmd')
        (runtime/'LEIA-ME.txt').write_text(r'''CENTRAL IA STUDIO — APLICATIVO WINDOWS x64

1. Extraia TODO este ZIP. Os dados ficam no LocalAppData por padrão.
2. Abra ABRIR_CENTRAL_IA.cmd, ou CentralIAStudio\\CentralIAStudio.exe.
3. Em Modelos, selecione ou digite a pasta dos seus GGUF e inicie o modelo.

Não precisa instalar Python, Node.js ou KoboldCpp. O motor está incluído.
Não execute diretamente de dentro do ZIP. Não separe o EXE das pastas
_internal, engine e licencas. Para dados portáteis, inicie com --portable.

Os modelos GGUF não estão incluídos e permanecem nas suas pastas originais.
Requisitos: Windows x64 e CPU com AVX2/FMA/F16C/BMI2. Inferência por CPU.
A interface abre no navegador local: http://127.0.0.1:8765

Atualização: feche a versão anterior. ONEFILE e ONEDIR da mesma versão usam
%LOCALAPPDATA%\CentralIAStudio por padrão. GGUFs permanecem externos.
A base antiga data junto ao EXE é copiada com backup quando o destino está vazio.
Se ela estiver em outra instalação, use --migrate-from "C:\antiga\data".
A origem nunca é apagada e bases existentes não são mescladas/sobrescritas.
Use --portable para dados junto ao EXE, ou --data-dir para uma pasta escolhida.
Consulte Documentacao/docs/MIGRACAO_DE_DADOS.md no pacote de fontes.

Licenças: CentralIAStudio\\licencas e CentralIAStudio\\engine.
Código-fonte do Studio também disponível em Configurações na própria interface.
Fontes completas do Studio e do motor, guias e documentação estão no ZIP
Central-IA-Studio-Fontes-e-Documentacao.zip do mesmo lançamento.
Esse ZIP técnico é opcional para executar o aplicativo.
'''.replace(chr(92)*2,chr(92)),encoding='utf-8-sig')
        extras = stage/'extras'
        sources = extras/'Fontes'
        sources.mkdir(parents=True)
        shutil.copy2(root/'central-ia-studio-source.zip', sources/'central-ia-studio-source.zip')
        motor_sources = sources/'Motor'
        motor_sources.mkdir()
        for file in sorted(engine.iterdir()):
            if file.is_file() and file.suffix.lower()!='.exe' and file.name!='SHA256SUMS.txt':
                shutil.copy2(file, motor_sources/file.name)
        shutil.copytree(root/'docs', extras/'Documentacao/docs')
        shutil.copy2(root/'README.md', extras/'Documentacao/README.md')
        (extras/'Licencas').mkdir()
        for name in NOTICES:
            shutil.copy2(root/name, extras/'Licencas'/name)
        (extras/'LEIA-ME.txt').write_text(r'''CENTRAL IA STUDIO — FONTES E DOCUMENTAÇÃO

Este ZIP é opcional para usar o aplicativo Windows.

Fontes/central-ia-studio-source.zip: fontes do Studio, frontend compilado,
scripts de build, testes e documentação da versão correspondente.
Fontes/Motor/central-engine-source.zip: CLI, adaptações, testes e build do motor.
Fontes/Motor/llama-cpp-source.zip: fontes completas da revisão upstream usada.
Fontes/Motor/third-party-licenses.zip: avisos das dependências do motor.
Documentacao/: guias, referências, prévias e relatório das verificações.
Licencas/: licença do Studio e avisos de dependências do aplicativo.

As licenças do motor também acompanham Fontes/Motor.
Os hashes dos dois ZIPs de distribuição estão em SHA256SUMS.txt no lançamento.

Para executar, baixe Central-IA-Studio-Windows-x64.zip. Os arquivos deste
ZIP técnico não precisam ser copiados para a pasta do aplicativo.
Nenhum modelo GGUF ou dado pessoal está incluído.
'''.replace(chr(92)*2,chr(92)),encoding='utf-8-sig')
        zip_tree(runtime, root/APP_ZIP)
        zip_tree(extras, root/EXTRAS_ZIP)
    shutil.copy2(root/'dist/onefile/CentralIAStudio.exe',root/'CentralIAStudio.exe')
    return root/APP_ZIP, root/EXTRAS_ZIP


if __name__=='__main__':
    for output in package():
        print(f'{output.name}: {output.stat().st_size:,} bytes')
