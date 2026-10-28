"""Small, source-aware SQLite database for verified admissions records.
No external MySQL/Docker service required. Never infer missing data.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / 'data' / 'processed' / 'hcmus.sqlite3'
SEED = ROOT / 'data' / 'curated' / 'majors_2026.json'

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
CREATE INDEX IF NOT EXISTS idx_combinations_year_code ON major_combinations(year, combination);
"""


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
               s.url as source_url,
               s.title as source_title FROM majors m JOIN sources s ON s.id=m.source_id
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
