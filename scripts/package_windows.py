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
                 *(engine/name for name in RUNTIME_ENGINE),
                 engine/'llama-cpp-source.zip', engine/'central-engine-source.zip',
                 root/'central-ia-studio-source.zip', *(root/name for name in NOTICES)]:
        if not file.is_file():
            raise ValueError('Arquivo necessário ao pacote ausente: '+str(file))
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
        for name in RUNTIME_ENGINE:
            shutil.copy2(engine/name, runtime_engine/name)
        notices = runtime/'CentralIAStudio/licencas'
        notices.mkdir(exist_ok=True)
        for name in NOTICES:
            shutil.copy2(root/name, notices/name)
        shutil.copy2(root/'INICIAR_CENTRAL_IA_STUDIO.cmd', runtime/'ABRIR_CENTRAL_IA.cmd')
        (runtime/'LEIA-ME.txt').write_text('''CENTRAL IA STUDIO — APLICATIVO WINDOWS x64

1. Extraia TODO este ZIP em uma pasta gravável.
2. Abra ABRIR_CENTRAL_IA.cmd, ou CentralIAStudio\\CentralIAStudio.exe.
3. Em Modelos, selecione ou digite a pasta dos seus GGUF e inicie o modelo.

Não precisa instalar Python, Node.js ou KoboldCpp. O motor está incluído.
Não execute diretamente de dentro do ZIP. Não separe o EXE das pastas
_internal, engine e licencas. Elas fazem parte da instalação portátil.

Os modelos GGUF não estão incluídos e permanecem nas suas pastas originais.
Requisitos: Windows x64 e CPU com AVX2/FMA/F16C/BMI2. Inferência por CPU.
A interface abre no navegador local: http://127.0.0.1:8765

Atualização: feche a versão anterior, faça backup da pasta data e extraia
esta versão em uma pasta nova. Para levar histórico e configurações, copie
a pasta data anterior para junto do novo CentralIAStudio.exe, com o app fechado.

Licenças: CentralIAStudio\\licencas e CentralIAStudio\\engine.
Código-fonte do Studio também disponível em Configurações na própria interface.
Fontes completas do Studio e do motor, guias e documentação estão no ZIP
Central-IA-Studio-Fontes-e-Documentacao.zip do mesmo lançamento.
Esse ZIP técnico é opcional para executar o aplicativo.
''',encoding='utf-8-sig')
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
        (extras/'LEIA-ME.txt').write_text('''CENTRAL IA STUDIO — FONTES E DOCUMENTAÇÃO

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
''',encoding='utf-8-sig')
        zip_tree(runtime, root/APP_ZIP)
        zip_tree(extras, root/EXTRAS_ZIP)
    return root/APP_ZIP, root/EXTRAS_ZIP


if __name__=='__main__':
    for output in package():
        print(f'{output.name}: {output.stat().st_size:,} bytes')
