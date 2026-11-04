"""Browse directories on the local Studio host without uploading model files."""
import os
import string
from pathlib import Path

def browse_folders(value: str = ''):
    path = Path(value).expanduser() if value else Path.home()
    try:
        path = path.resolve(strict=True)
        if not path.is_dir():
            raise ValueError('Selecione uma pasta, não um arquivo.')
        children = []
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_dir():
                        children.append({'name':entry.name,'path':str(path/entry.name)})
                except OSError:
                    continue
        children.sort(key=lambda item:item['name'].casefold())
    except (OSError, RuntimeError) as error:
        raise ValueError('Não foi possível abrir esta pasta. Confira o caminho e a permissão de acesso.') from error
    roots = [Path.home()]
    if os.name == 'nt':
        roots += [Path(letter+':/') for letter in string.ascii_uppercase if Path(letter+':/').is_dir()]
    else:
        roots += [Path('/')]
    return {'path':str(path),'parent':str(path.parent) if path.parent!=path else None,
            'roots':[{'name':str(p),'path':str(p)} for p in dict.fromkeys(roots)],'directories':children}
