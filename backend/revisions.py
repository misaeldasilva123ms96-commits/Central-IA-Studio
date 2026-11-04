"""User-requested undo, protected against overwriting subsequent edits."""
import difflib
import hashlib
import os
from pathlib import Path
import uuid


def revision_preview(store,rid):
    with store.db() as db:row=db.execute('SELECT * FROM agent_revisions WHERE id=?',(rid,)).fetchone()
    if row is None:raise ValueError('Revisão não encontrada.')
    target=Path(row['path'])
    if target.resolve()!=target:raise ValueError('O caminho mudou desde a edição.')
    if target.is_file():
        with target.open('rb') as stream:current=stream.read(128*1024+1)
    else:current=None
    unchanged=current is not None and hashlib.sha256(current).hexdigest()==row['after_sha']
    previous=bytes(row['previous']) if row['previous'] is not None else None
    return row,current,previous,unchanged


def undo_revision(store,rid):
    row,current,previous,unchanged=revision_preview(store,rid)
    if row['restored'] or not unchanged:raise ValueError('O arquivo foi alterado depois desta edição ou ela já foi desfeita. Nenhum arquivo foi sobrescrito.')
    target=Path(row['path'])
    if previous is None:target.unlink()
    else:
        temporary=target.with_name('.central-undo-'+uuid.uuid4().hex+'.tmp')
        try:
            temporary.write_bytes(previous);os.chmod(temporary,target.stat().st_mode & 0o777);os.replace(temporary,target)
        finally:temporary.unlink(missing_ok=True)
    with store.db() as db:db.execute('UPDATE agent_revisions SET restored=1 WHERE id=?',(rid,))
    return {'restored':True,'path':str(target),'removed_created_file':previous is None}
