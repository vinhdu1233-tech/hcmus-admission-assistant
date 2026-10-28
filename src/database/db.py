"""Small, source-aware SQLite database for verified admissions records.
No external MySQL/Docker service required. Never infer missing data.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / 'data' / 'processed' / 'hcmus.sqlite3'
SEED = ROOT / 'data' / 'curated' / 'majors_2026.json'
PROFILES_SEED = ROOT / 'data' / 'curated' / 'program_profiles_2026.json'

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY, year INTEGER NOT NULL, title TEXT NOT NULL,
  url TEXT NOT NULL, checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS majors (
  year INTEGER NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL,
  quota INTEGER, tags_json TEXT NOT NULL, source_id INTEGER NOT NULL,
  PRIMARY KEY(year, code), FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS major_combinations (
  year INTEGER NOT NULL, major_code TEXT NOT NULL, combination TEXT NOT NULL,
  PRIMARY KEY(year, major_code, combination),
  FOREIGN KEY(year, major_code) REFERENCES majors(year, code)
);
CREATE TABLE IF NOT EXISTS admission_methods (
  year INTEGER NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL,
  summary TEXT NOT NULL, source_url TEXT NOT NULL,
  PRIMARY KEY(year, code)
);
CREATE TABLE IF NOT EXISTS program_profiles (
  year INTEGER NOT NULL, major_code TEXT NOT NULL,
  summary TEXT NOT NULL, source_url TEXT NOT NULL, reviewed_on TEXT NOT NULL,
  PRIMARY KEY(year, major_code),
  FOREIGN KEY(year, major_code) REFERENCES majors(year, code)
);
CREATE INDEX IF NOT EXISTS idx_combinations_year_code ON major_combinations(year, combination);
"""


def official_hcmus_url(url: str) -> bool:
    """Only HTTPS on the genuine HCMUS domain or its subdomains."""
    try:
        parts = urlsplit(url)
    except (TypeError, ValueError):
        return False
    hostname = (parts.hostname or "").lower()
    return (parts.scheme == "https"
            and (hostname == "hcmus.edu.vn" or hostname.endswith(".hcmus.edu.vn"))
            and parts.username is None and parts.password is None
            and parts.port in (None, 443)
            and not any(char in str(url) for char in ("\\n", "\\r")))


def database_path() -> Path:
    return Path(os.environ.get('HCMUS_DB_PATH') or DEFAULT_DB)


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = sqlite3.connect(str(path or database_path()))
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize_database(path: Path | None = None, seed_path: Path | None = None) -> Path:
    """Idempotent creation; import JSON seed exactly once per record."""
    path = Path(path or database_path())
    seed_path = Path(seed_path or SEED)
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = json.loads(seed_path.read_text(encoding='utf-8'))
    year = seed['year']
    with connect(path) as db:
        db.executescript(SCHEMA)
        source = seed['source']
        db.execute('INSERT OR REPLACE INTO sources(id,year,title,url,checked_at) VALUES (1,?,?,?,?)',
                   (year,source['title'],source['url'],seed['verified_on']))
        for item in seed['majors']:
            db.execute('INSERT OR REPLACE INTO majors(year,code,name,quota,tags_json,source_id) VALUES (?,?,?,?,?,1)',
                       (year,item['code'],item['name'],item['quota'],json.dumps(item['tags'],ensure_ascii=False)))
            db.execute('DELETE FROM major_combinations WHERE year=? AND major_code=?',(year,item['code']))
            db.executemany('INSERT INTO major_combinations(year,major_code,combination) VALUES (?,?,?)',
                           [(year,item['code'],code) for code in item['combinations']])
        # Import only manually reviewed official profiles. Raw scrape candidates
        # must never be injected into the assistant's evidence store.
        if PROFILES_SEED.exists() and year == 2026:
            profiles = json.loads(PROFILES_SEED.read_text(encoding='utf-8'))
            if profiles['year'] != year:
                raise ValueError('Program profile admission year mismatch')
            known_codes = {major['code'] for major in seed['majors']}
            items = profiles['profiles']
            codes = [profile['code'] for profile in items]
            if len(codes) != len(set(codes)) or not set(codes).issubset(known_codes):
                raise ValueError('Duplicate or unknown verified program profile code')
            if any(not official_hcmus_url(p.get('source_url'))
                   or not p.get('reviewed_on') or not p.get('summary')
                   for p in items):
                raise ValueError('Program profiles require official HCMUS URLs and manual review')
            db.execute('DELETE FROM program_profiles WHERE year=?', (year,))
            db.executemany(
                'INSERT INTO program_profiles(year,major_code,summary,source_url,reviewed_on) VALUES (?,?,?,?,?)',
                [(year,p['code'],p['summary'],p['source_url'],p['reviewed_on']) for p in items]
            )
        for item in seed['methods']:
            db.execute('INSERT OR REPLACE INTO admission_methods(year,code,name,summary,source_url) VALUES (?,?,?,?,?)',
                       (year,item['code'],item['name'],item['summary'],item['url']))
    return path


def ensure_database() -> Path:
    path=database_path()
    if not path.exists():
        return initialize_database(path)
    return path


def search_majors(year:int,combination:str|None=None,limit:int=15) -> list[dict]:
    ensure_database()
    sql='''SELECT m.year,m.code,m.name,m.quota,s.title as source_title,s.url as source_url
      FROM majors m JOIN sources s ON s.id=m.source_id'''
    params: list[str | int] = [year]
    if combination:
        sql+=' JOIN major_combinations c ON c.year=m.year AND c.major_code=m.code'
        sql+=' WHERE m.year=? AND c.combination=?';params.append(combination)
    else:
        sql+=' WHERE m.year=?'
    sql+=' ORDER BY m.name LIMIT ?';params.append(limit)
    with connect() as db:
        return [dict(r) for r in db.execute(sql,params)]


def all_majors(year:int) -> list[dict]:
    ensure_database()
    with connect() as db:
        rows=db.execute('''SELECT m.code,m.name,m.quota,m.tags_json,
               (SELECT GROUP_CONCAT(c.combination, ', ') FROM major_combinations c
                WHERE c.year=m.year AND c.major_code=m.code) AS combinations,
               s.url as source_url, s.title as source_title,
               p.summary as official_profile, p.source_url as profile_source_url,
               p.reviewed_on as profile_reviewed_on
               FROM majors m JOIN sources s ON s.id=m.source_id
               LEFT JOIN program_profiles p ON p.year=m.year AND p.major_code=m.code
               WHERE m.year=? ORDER BY m.name''',(year,)).fetchall()
    return [dict(r) for r in rows]


def get_methods(year:int) -> list[dict]:
    ensure_database()
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM admission_methods WHERE year=? ORDER BY code',(year,))]


def count_majors(year:int) -> int:
    ensure_database()
    with connect() as db:
        return int(db.execute('SELECT COUNT(*) FROM majors WHERE year=?',(year,)).fetchone()[0])

if __name__ == '__main__':
    db_file = initialize_database()
    print(f'Database initialized: {db_file}')
    print('2026 majors in current verified subset:', count_majors(2026))
