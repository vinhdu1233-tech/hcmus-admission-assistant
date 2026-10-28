"""Multi-turn FastAPI tests: source-backed results without real AI calls."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.assistant.conversation import ConversationManager, standalone_year
from src.database.db import initialize_database


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setenv("HCMUS_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AI_PROVIDER", "none")
    initialize_database()


def send(client, session, message, year=None):
    payload = {"message": message, "conversation_id": session}
    if year is not None:
        payload["admission_year"] = year
    result = client.post("/chat", json=payload)
    assert result.status_code == 200, result.text
    return result.json()


def test_standalone_year_recognizes_natural_short_answers():
    for message in ("2026", "năm 2026", "2026 nhé", "năm 2026 ạ", "mình chọn năm 2026"):
        assert standalone_year(message) == 2026
    assert standalone_year("Ngành nào A01 năm 2026?") is None


def test_missing_year_then_year_alone_resumes_original_question():
    session = str(uuid4())
    with TestClient(app) as client:
        first = send(client, session, "Ngành nào xét A01?")
        assert first["status"] == "clarification_needed"
        assert "năm" in first["answer"].lower()

        # Frontend also sends admission_year extracted from a year-only message.
        second = send(client, session, "2026", year=2026)
        assert second["status"] == "answered"
        assert second["intent"] == "major_filter"
        assert "A01" in second["answer"]
        assert "Trí tuệ nhân tạo" in second["answer"]
        assert second["sources"]


def test_short_answer_nam_2026_preserves_question_and_source():
    session = str(uuid4())
    with TestClient(app) as client:
        send(client, session, "HCMUS xét tuyển bằng phương thức nào?")
        resumed = send(client, session, "năm 2026")
    assert resumed["status"] == "answered"
    assert resumed["intent"] == "admission_methods"
    assert "1a" in resumed["answer"]
    assert resumed["sources"]


def test_follow_up_changes_combination_but_preserves_year():
    session = str(uuid4())
    with TestClient(app) as client:
        send(client, session, "Ngành nào xét A01 năm 2026?")
        next_turn = send(client, session, "Còn B00 thì sao?")
    assert next_turn["status"] == "answered"
    assert next_turn["intent"] == "major_filter"
    assert "B00 năm 2026" in next_turn["answer"]
    assert "Sinh học" in next_turn["answer"]
    assert next_turn["sources"]


def test_follow_up_can_change_year_and_unsupported_year_is_not_invented():
    session = str(uuid4())
    with TestClient(app) as client:
        send(client, session, "Ngành nào xét A01 năm 2026?")
        changed = send(client, session, "còn năm 2027", year=2027)
        assert changed["status"] == "insufficient_evidence"
        assert "2027" in changed["answer"]
        updated = send(client, session, "2026 nhé", year=2026)
        assert updated["status"] == "answered"
        assert "A01" in updated["answer"]


def test_two_sessions_never_share_pending_questions():
    a, b = str(uuid4()), str(uuid4())
    with TestClient(app) as client:
        send(client, a, "Ngành nào xét A01?")
        innocent = send(client, b, "2026", year=2026)
        resumed = send(client, a, "2026", year=2026)
    assert "Trí tuệ nhân tạo" not in innocent["answer"]
    assert innocent["status"] == "clarification_needed"
    assert "Trí tuệ nhân tạo" in resumed["answer"]


def test_explicit_new_year_beats_saved_year():
    session = str(uuid4())
    with TestClient(app) as client:
        send(client, session, "Ngành nào xét A01 năm 2026?")
        answer = send(client, session, "Ngành nào xét B00 năm 2027?", year=2027)
    assert answer["status"] == "insufficient_evidence"
    assert "2027" in answer["answer"]


def test_reset_discarded_context():
    session = str(uuid4())
    with TestClient(app) as client:
        send(client, session, "Ngành nào xét A01?")
        reset = send(client, session, "bắt đầu lại")
        alone = send(client, session, "2026", year=2026)
    assert reset["status"] == "answered"
    assert alone["status"] == "clarification_needed"
    assert "A01" not in alone["answer"]


def test_old_clients_without_conversation_id_remain_stateless():
    with TestClient(app) as client:
        a = client.post("/chat", json={"message": "Ngành nào xét A01?"}).json()
        b = client.post("/chat", json={"message": "2026", "admission_year": 2026}).json()
    assert a["status"] == "clarification_needed"
    assert b["status"] == "clarification_needed"


def test_context_expires_and_is_bounded():
    current = [10.0]
    manager = ConversationManager(ttl_seconds=60, max_sessions=2, clock=lambda: current[0])
    assert manager.answer("Ngành nào xét A01?", None, "a")["status"] == "clarification_needed"
    current[0] += 1
    assert manager.answer("Ngành nào xét A01?", None, "b")["status"] == "clarification_needed"
    current[0] += 1
    assert manager.answer("Ngành nào xét A01?", None, "c")["status"] == "clarification_needed"
    # Oldest 'a' is evicted.
    assert manager.answer("2026", None, "a")["status"] == "clarification_needed"
    current[0] += 61
    assert manager.answer("2026", None, "c")["status"] == "clarification_needed"


def test_bad_uuid_returns_422():
    with TestClient(app) as client:
        response = client.post("/chat", json={
            "message": "Ngành nào xét A01?", "conversation_id": "not-a-uuid"
        })
    assert response.status_code == 422
