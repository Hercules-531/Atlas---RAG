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
        ''')

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
