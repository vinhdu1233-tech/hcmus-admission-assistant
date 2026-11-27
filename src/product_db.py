"""Isolated account/calendar SQLite store; never replaces the admissions dataset."""
from __future__ import annotations
import os, sqlite3, threading
from pathlib import Path
from contextlib import contextmanager
from src.database.db import database_path
from dotenv import load_dotenv
load_dotenv()
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student','admin')),
 failed INTEGER NOT NULL DEFAULT 0, lock_round INTEGER NOT NULL DEFAULT 0,
 locked_until REAL NOT NULL DEFAULT 0, hard_locked INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS otps (
 email TEXT NOT NULL, purpose TEXT NOT NULL, digest TEXT NOT NULL,
 expires REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, sent_at REAL NOT NULL,
 PRIMARY KEY(email,purpose)
);
CREATE TABLE IF NOT EXISTS otp_sends (email TEXT NOT NULL, sent_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS otp_sends_time ON otp_sends(sent_at);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS session_users ON sessions(user_id);
CREATE TABLE IF NOT EXISTS question_logs (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 question TEXT NOT NULL, intent TEXT NOT NULL, status TEXT NOT NULL,
 latency_ms REAL NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS logs_date ON question_logs(created_at);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
 year INTEGER, method TEXT, title TEXT NOT NULL, starts REAL NOT NULL, ends REAL NOT NULL,
 source_url TEXT, note TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
 CHECK(ends>=starts), CHECK((user_id IS NOT NULL AND source_url IS NULL)
 OR (user_id IS NULL AND source_url IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS reminders (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 edge TEXT NOT NULL CHECK(edge IN ('start','end')),
 days_before INTEGER NOT NULL CHECK(days_before IN (0,1,4,7)),
 created_at REAL NOT NULL, UNIQUE(user_id,event_id,edge,days_before)
);
CREATE TABLE IF NOT EXISTS push_subscriptions (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 endpoint TEXT UNIQUE NOT NULL, subscription TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS notices (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, dedupe_key TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
 notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
 subscription_id INTEGER NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
 attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL,
 sent_at REAL, state TEXT NOT NULL DEFAULT 'pending', PRIMARY KEY(notice_id,subscription_id)
);
CREATE TABLE IF NOT EXISTS method_follows (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, method TEXT NOT NULL,
 PRIMARY KEY(user_id,method)
);
CREATE TABLE IF NOT EXISTS monitor_sources (
 url TEXT PRIMARY KEY, label TEXT NOT NULL, checked_at REAL, successful_at REAL,
 last_digest TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL REFERENCES monitor_sources(url),
 digest TEXT NOT NULL, content TEXT NOT NULL, fetched_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS snapshot_url ON snapshots(url,id);
CREATE TABLE IF NOT EXISTS changes (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL REFERENCES monitor_sources(url),
 previous_id INTEGER NOT NULL REFERENCES snapshots(id),
 current_id INTEGER NOT NULL REFERENCES snapshots(id),
 summary TEXT NOT NULL, detected_at REAL NOT NULL, reviewed_at REAL,
 review_note TEXT NOT NULL DEFAULT '', UNIQUE(previous_id,current_id)
);

CREATE TABLE IF NOT EXISTS deadline_candidates (
 id INTEGER PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
 year INTEGER NOT NULL, method TEXT NOT NULL, title TEXT NOT NULL,
 starts REAL, ends REAL NOT NULL, evidence TEXT NOT NULL, precision_note TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending', reviewed_at REAL, reviewed_by INTEGER REFERENCES users(id),
 UNIQUE(snapshot_id,method,title,ends,evidence)
);
CREATE TABLE IF NOT EXISTS notice_reads (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
 read_at REAL NOT NULL, PRIMARY KEY(user_id,notice_id)
);
CREATE TABLE IF NOT EXISTS checklist_progress (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 year INTEGER NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL,
 tasks TEXT NOT NULL, updated_at REAL NOT NULL,
 PRIMARY KEY(user_id,year,method,path)
);
"""
_guard=threading.Lock()
_initialized=set()
def path():
    return Path(os.getenv("HCMUS_PRODUCT_DB_PATH") or database_path().with_suffix(".product.sqlite3"))
def _open(p):
    c=sqlite3.connect(str(p), timeout=15)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=15000")
    return c
def initialize():
    p=path().resolve()
    with _guard:
        if p not in _initialized or not p.exists():
            p.parent.mkdir(parents=True,exist_ok=True)
            c=_open(p)
            try:
                c.execute("PRAGMA journal_mode=WAL")
                c.executescript(SCHEMA)
                from src.product_seed import seed
                seed(c)
                c.commit()
            finally:c.close()
            _initialized.add(p)
    return p
@contextmanager
def db(write=False):
    c=_open(initialize())
    try:
        if write:c.execute("BEGIN IMMEDIATE")
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:c.close()
