import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .runtime import DATA_SCHEMA

class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'central.sqlite3'
        with self.db() as db:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version>DATA_SCHEMA:raise ValueError('Esta base foi criada por uma versão mais nova. Use o aplicativo atualizado; dados preservados.')
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS profiles(model TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, reasoning TEXT NOT NULL DEFAULT '', stats TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS benchmarks(id TEXT PRIMARY KEY, created REAL NOT NULL, value TEXT NOT NULL);
            ''')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY, name TEXT NOT NULL, mime TEXT NOT NULL, kind TEXT NOT NULL, size INTEGER NOT NULL, text TEXT NOT NULL, data BLOB NOT NULL, vision BLOB, warning TEXT NOT NULL, sha256 TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS message_attachments(message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE, attachment_id TEXT NOT NULL REFERENCES attachments(id), PRIMARY KEY(message_id,attachment_id));
            CREATE TABLE IF NOT EXISTS agent_revisions(id TEXT PRIMARY KEY, conversation TEXT NOT NULL, path TEXT NOT NULL, previous BLOB, after_sha TEXT NOT NULL, created REAL NOT NULL, restored INTEGER NOT NULL DEFAULT 0);
            ''')
            with db:
                db.executescript("""
                CREATE TABLE IF NOT EXISTS imported_extensions(id TEXT PRIMARY KEY,parent TEXT,kind TEXT NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL,version TEXT NOT NULL,instructions TEXT NOT NULL DEFAULT '',root TEXT NOT NULL DEFAULT '',source TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS extension_files(package TEXT NOT NULL REFERENCES imported_extensions(id) ON DELETE CASCADE,path TEXT NOT NULL,data BLOB NOT NULL,mode INTEGER NOT NULL DEFAULT 384,PRIMARY KEY(package,path));
                CREATE TABLE IF NOT EXISTS mcp_servers(id TEXT PRIMARY KEY,package TEXT,name TEXT NOT NULL,config TEXT NOT NULL,selected TEXT NOT NULL DEFAULT '[]',tools TEXT NOT NULL DEFAULT '[]');
                """)
            imported_columns={row[1] for row in db.execute('PRAGMA table_info(imported_extensions)')}
            if 'implicit' not in imported_columns:db.execute('ALTER TABLE imported_extensions ADD COLUMN implicit INTEGER NOT NULL DEFAULT 1')
            revision_columns={row[1] for row in db.execute('PRAGMA table_info(agent_revisions)')}
            if 'restored' not in revision_columns:db.execute('ALTER TABLE agent_revisions ADD COLUMN restored INTEGER NOT NULL DEFAULT 0')
            attachment_columns={row[1] for row in db.execute('PRAGMA table_info(attachments)')}
            if 'vision' not in attachment_columns:db.execute('ALTER TABLE attachments ADD COLUMN vision BLOB')
            message_columns={row[1] for row in db.execute('PRAGMA table_info(messages)')}
            if 'created' not in message_columns:db.execute('ALTER TABLE messages ADD COLUMN created REAL')
            columns={row[1] for row in db.execute('PRAGMA table_info(conversations)')}
            if 'kind' not in columns:
                db.execute("ALTER TABLE conversations ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat'")
            db.execute('PRAGMA user_version='+str(DATA_SCHEMA))
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Banco inconsistente. Preserve o arquivo antes de restaurar um backup.')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.db() as db:
            row = db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))

    def profile(self, model):
        with self.db() as db:
            row = db.execute('SELECT value FROM profiles WHERE model=?',(model,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_profile(self, model, value):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO profiles VALUES (?,?)',(model,json.dumps(value)))

    def conversation(self, title, kind='chat'):
        cid = uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT INTO conversations(id,title,created,kind) VALUES (?,?,?,?)',(cid,title,time.time(),kind))
        return cid

    def messages(self, cid):
        with self.db() as db:
            rows=[dict(row) | {'stats':json.loads(row['stats'])} for row in db.execute('SELECT * FROM messages WHERE conversation=? ORDER BY id',(cid,))]
            for row in rows:
                for activity in row['stats'].get('activities',[]):
                    rid=(activity.get('result') or {}).get('revision')
                    if rid:
                        revision=db.execute('SELECT restored FROM agent_revisions WHERE id=?',(rid,)).fetchone()
                        if revision:activity['result']['restored']=bool(revision[0])
                row['attachments']=[dict(a) for a in db.execute('SELECT a.id,a.name,a.mime,a.kind,a.size,a.warning,a.sha256 FROM attachments a JOIN message_attachments m ON m.attachment_id=a.id WHERE m.message_id=?',(row['id'],))]
            return rows

    def add_message(self, cid, role, content, reasoning='', stats=None, attachments=None, created=None):
        with self.db() as db:
            cur = db.execute('INSERT INTO messages(conversation,role,content,reasoning,stats,created) VALUES (?,?,?,?,?,?)',
                             (cid,role,content,reasoning,json.dumps(stats or {},ensure_ascii=False),time.time() if created is None else created))
            mid=cur.lastrowid
            for aid in attachments or []:
                db.execute('INSERT INTO message_attachments VALUES (?,?)',(mid,aid))
            return mid

    def backup(self):
        dest = self.directory / ('backup-'+str(time.time_ns())+'.sqlite3')
        with self.db() as source, sqlite3.connect(dest) as target:
            source.backup(target)
        return dest
