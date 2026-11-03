"""Pacote CPU sem CUDA, com avisos e fontes reprodutíveis correspondentes."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
binary,upstream,out=map(lambda p:Path(p).resolve(),sys.argv[1:4])
out.mkdir(parents=True,exist_ok=True)
shutil.copy2(binary,out/binary.name)
shutil.copy2(ROOT/'engine/LICENSE',out/'LICENSE')
shutil.copy2(ROOT/'engine/NOTICE.md',out/'NOTICE.md')
shutil.copy2(ROOT/'engine/README.md',out/'README.md')
# Original upstream sources + our exact patches and CLI sources.
subprocess.run(['git','-C',str(upstream),'archive','--format=zip','--output',str(out/'llama-cpp-source.zip'),'HEAD'],check=True)
with ZipFile(out/'central-engine-source.zip','w',ZIP_DEFLATED) as z:
    for p in sorted((ROOT/'engine').rglob('*')):
        if p.is_file() and p.suffix not in ['.pyc','.exe'] and '__pycache__' not in p.parts:
            z.write(p,str(p.relative_to(ROOT)))
# Preserve the licenses shipped in the exact upstream snapshot.
with ZipFile(out/'third-party-licenses.zip','w',ZIP_DEFLATED) as z:
    for p in upstream.rglob('*'):
        if p.is_file() and '.git' not in p.parts and any(x in p.name.lower() for x in ['license','copying','notice']):
            z.write(p,str(p.relative_to(upstream)))
for p in sorted(out.glob('*.zip')):
    with ZipFile(p) as z: assert z.testzip() is None
lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt']
(out/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
print('Motor empacotado, sem modelos, com licencas e fontes upstream/patches.')
