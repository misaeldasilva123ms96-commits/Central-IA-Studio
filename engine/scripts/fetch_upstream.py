"""Obtém somente o commit público fixado, sem clonar o histórico inteiro."""
from pathlib import Path
import subprocess
import sys
COMMIT='d1044bc82712fbf08996080bef6298b24a27e9c7'
root=Path(sys.argv[1]).resolve()
if not root.exists():
    root.mkdir(parents=True)
    subprocess.run(['git','init',str(root)],check=True)
    subprocess.run(['git','-C',str(root),'remote','add','origin','https://github.com/ggml-org/llama.cpp.git'],check=True)
    subprocess.run(['git','-C',str(root),'fetch','--depth','1','origin',COMMIT],check=True)
    subprocess.run(['git','-C',str(root),'checkout','--detach','FETCH_HEAD'],check=True)
if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=COMMIT:
    raise RuntimeError('Diretorio upstream nao corresponde ao commit fixado')
