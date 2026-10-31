import json
import sqlite3
from contextlib import contextmanager
from .config import DATA, directories

@contextmanager
def db():
    directories()
    conn = sqlite3.connect(DATA / 'atlas.sqlite3', timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,name TEXT,path TEXT,status TEXT,error TEXT DEFAULT '',progress INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,document_id TEXT,text TEXT,location TEXT);
        CREATE TABLE IF NOT EXISTS history(id TEXT PRIMARY KEY,created REAL,question TEXT,mode TEXT,result TEXT);
        CREATE TABLE IF NOT EXISTS budgets(session TEXT PRIMARY KEY,tokens INTEGER);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS parents(id TEXT PRIMARY KEY,document_id TEXT,text TEXT,location TEXT);
        CREATE TABLE IF NOT EXISTS chunk_parents(chunk_id TEXT PRIMARY KEY,parent_id TEXT,start_offset INTEGER,end_offset INTEGER);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED,text,document_id UNINDEXED);
        CREATE TRIGGER IF NOT EXISTS chunk_fts_insert AFTER INSERT ON chunks BEGIN
          INSERT INTO chunks_fts(chunk_id,text,document_id) VALUES(new.id,new.text,new.document_id); END;
        CREATE TRIGGER IF NOT EXISTS chunk_fts_delete AFTER DELETE ON chunks BEGIN
          DELETE FROM chunks_fts WHERE chunk_id=old.id;
          DELETE FROM chunk_parents WHERE chunk_id=old.id; END;
        CREATE TRIGGER IF NOT EXISTS parent_children_delete AFTER DELETE ON parents BEGIN
          DELETE FROM chunk_parents WHERE parent_id=old.id; END;
        ''')
        if not c.execute('SELECT 1 FROM settings WHERE key="fts_initialized"').fetchone():
            c.execute('DELETE FROM chunks_fts')
            c.execute('INSERT INTO chunks_fts(chunk_id,text,document_id) SELECT id,text,document_id FROM chunks')
            c.execute('INSERT INTO settings VALUES ("fts_initialized","1")')

def reserve(session, tokens, limit):
    if tokens <= 0 or tokens > limit:
        raise ValueError('Request exceeds token budget')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT OR IGNORE INTO budgets VALUES (?,0)', (session,))
        used = c.execute('SELECT tokens FROM budgets WHERE session=?', (session,)).fetchone()[0]
        if used + tokens > limit:
            raise ValueError('Session token budget exhausted')
        c.execute('UPDATE budgets SET tokens=tokens+? WHERE session=?', (tokens, session))

def rows(sql, args=()):
    with db() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
