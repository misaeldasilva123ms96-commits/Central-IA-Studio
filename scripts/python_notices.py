"""Inventário de licenças instaladas do runtime e ferramentas de build."""
from importlib import metadata
from pathlib import Path
packages=['mcp','PyYAML','pydantic-settings','httpx-sse','jsonschema','jsonschema-specifications','referencing','rpds-py','attrs','sse-starlette','PyJWT','cryptography','cffi','pycparser','python-multipart','python-dotenv','pywin32','pillow','pypdf','fastapi','starlette','pydantic','pydantic-core','annotated-types','typing-extensions','uvicorn','click','h11','httpx','httpcore','anyio','sniffio','idna','certifi','psutil','pyinstaller','pyinstaller-hooks-contrib','altgraph','packaging','pefile','pywin32-ctypes']
output=['AVISOS PYTHON — versões observadas no ambiente de geração. O build Windows regenera este inventário.\n']
for name in packages:
    try: dist=metadata.distribution(name)
    except metadata.PackageNotFoundError: continue
    output.append('\n'+'='*72+'\n'+name+' '+dist.version+'\n')
    for f in dist.files or []:
        if '.dist-info' in str(f) and any(x in f.name.lower() for x in ['license','copying','notice']):
            path=dist.locate_file(f)
            if path.is_file(): output.append('\n'+str(f)+'\n'+path.read_text(errors='replace')+'\n')
Path(__file__).resolve().parent.parent.joinpath('THIRD_PARTY_PYTHON.txt').write_text(''.join(output),encoding='utf-8')
