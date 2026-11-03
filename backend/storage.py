import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'central.sqlite3'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS profiles(model TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, reasoning TEXT NOT NULL DEFAULT '', stats TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS benchmarks(id TEXT PRIMARY KEY, created REAL NOT NULL, value TEXT NOT NULL);
            ''')
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

    def conversation(self, title):
        cid = uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT INTO conversations VALUES (?,?,?)',(cid,title,time.time()))
        return cid

    def messages(self, cid):
        with self.db() as db:
            return [dict(row) | {'stats':json.loads(row['stats'])} for row in db.execute('SELECT * FROM messages WHERE conversation=? ORDER BY id',(cid,))]

    def add_message(self, cid, role, content, reasoning='', stats=None):
        with self.db() as db:
            cur = db.execute('INSERT INTO messages(conversation,role,content,reasoning,stats) VALUES (?,?,?,?,?)',
                             (cid,role,content,reasoning,json.dumps(stats or {},ensure_ascii=False)))
            return cur.lastrowid

    def backup(self):
        dest = self.directory / ('backup-'+str(time.time_ns())+'.sqlite3')
        with self.db() as source, sqlite3.connect(dest) as target:
            source.backup(target)
        return dest
