"""Integration tests for SQLite and FastAPI's deterministic Router."""
import json
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.database.db import SEED, connect, initialize_database, search_majors, count_majors
from src.assistant.router import route

@pytest.fixture(autouse=True)
def isolated_database(tmp_path,monkeypatch):
    monkeypatch.setenv('HCMUS_DB_PATH',str(tmp_path/'test.sqlite3'))
    initialize_database()

def test_sqlite_tables_and_source():
    with connect() as db:
        names={r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
        assert {'sources','majors','major_combinations','admission_methods'}<=names
        expected=len(json.loads(SEED.read_text(encoding='utf-8'))['majors'])
        assert db.execute('SELECT COUNT(*) FROM majors WHERE year=2026').fetchone()[0]==expected

def test_a01_filter_real_seed():
    names={r['name'] for r in search_majors(2026,'A01',50)}
    assert 'Trí tuệ nhân tạo' in names
    assert 'Sinh học' not in names

def test_api_flow():
    with TestClient(app) as client:
        response=client.post('/chat',json={'message':'Ngành nào xét tuyển tổ hợp A01 năm 2026?'})
    assert response.status_code==200
    result=response.json()
    assert result['intent']=='major_filter'
    assert result['status']=='answered'
    assert 'Trí tuệ nhân tạo' in result['answer']
    assert result['sources'][0]['url'].startswith('https://tuyensinh.hcmus.edu.vn/')

def test_method_lookup():
    r=route('Phương thức tuyển sinh năm 2026 là gì?',2026)
    assert r['status']=='answered' and '1a' in r['answer'] and '1b' in r['answer']

def test_major_exploration_rule_based():
    r=route('Em thích lập trình và toán, nên chọn ngành nào năm 2026?',2026)
    assert r['status']=='answered'
    assert r['intent']=='major_exploration'
    assert 'dữ liệu' in r['answer']

def test_missing_year():
    assert route('Ngành nào xét A01?',None)['status']=='clarification_needed'

def test_unverified_year():
    r=route('Học ngành nào năm 2027?',2027)
    assert r['status']=='insufficient_evidence'

def test_no_false_coverage_claim():
    r=route('HCMUS có những ngành nào năm 2026?',2026)
    actual=count_majors(2026)
    assert f'{actual}/39' in r['answer']
    if actual < 39:
        assert 'chưa đầy đủ' in r['answer']
    else:
        assert 'chưa đầy đủ' not in r['answer']

def test_no_sql_injection():
    r=route("Ngành nào A01' OR 1=1 -- năm 2026?",2026)
    assert r['status']=='answered'
    assert 'Sinh học' not in r['answer']


def test_more_than_twenty_programs_are_returned():
    # Synthetic records exist ONLY in tmp_path database created by the fixture.
    # They are NOT persisted into official JSON or the real admissions DB.
    existing = count_majors(2026)
    with connect() as db:
        for index in range(max(0, 25-existing)):
            db.execute(
                'INSERT INTO majors(year,code,name,quota,tags_json,source_id) VALUES (2026,?,?,?,?,1)',
                (f'TEST_ONLY_{index:03d}', f'Test-only program {index:03d}', None, '[]')
            )
    actual=count_majors(2026)
    assert actual >= 25
    answer=route('HCMUS có những ngành nào năm 2026?',2026)
    assert answer['status']=='answered'
    assert f'{actual}/39' in answer['answer']
    assert answer['answer'].count('\n• ') == actual


def test_major_exploration_shows_current_coverage():
    response = route('Em thích lập trình và toán, nên chọn ngành nào năm 2026?',2026)
    assert f'{count_majors(2026)}/39' in response['answer']
