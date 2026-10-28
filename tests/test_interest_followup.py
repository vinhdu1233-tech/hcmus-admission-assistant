"""AI's own exploration questions accept short answers within the same session.

All tests are offline: Retrieval + SQLite are exercised, Ollama is mocked off.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.assistant.conversation import interest_reply
from src.database.db import initialize_database


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("HCMUS_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AI_PROVIDER", "none")
    initialize_database()


def chat(client, session, message):
    result = client.post("/chat", json={"conversation_id": session, "message": message})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize("choice,expected", [
    ("xây dựng ứng dụng", "ứng dụng"),
    ("mình thích làm app", "ứng dụng"),
    ("giải bài toán thuật toán", "thuật toán"),
    ("mình chọn thuật toán", "thuật toán"),
    ("phân tích dữ liệu", "dữ liệu"),
    ("em thích thống kê", "dữ liệu"),
    ("data science", "dữ liệu"),
])
def test_recognize_short_followup_choices(choice, expected):
    assert interest_reply(choice)[0] == expected


@pytest.mark.parametrize("choice,domain_keyword", [
    ("xây dựng ứng dụng", "phần mềm"),
    ("giải thuật toán", "máy tính"),
    ("phân tích dữ liệu", "dữ liệu"),
])
def test_after_ai_question_short_focus_gets_program_recommendations(choice, domain_keyword):
    session = str(uuid4())
    with TestClient(app) as client:
        first = chat(client, session, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        assert first["intent"] == "major_exploration"
        assert first["status"] == "answered"
        assert "Bạn thích hơn việc xây dựng ứng dụng" in first["answer"]

        second = chat(client, session, choice)
    assert second["status"] == "answered"
    assert second["intent"] == "major_exploration"
    assert "hướng bạn vừa chọn" in second["answer"]
    assert domain_keyword in second["answer"].lower()
    assert second["sources"]
    assert all("hcmus.edu.vn" in s["url"] for s in second["sources"])


def test_can_follow_up_twice_with_different_interests():
    session = str(uuid4())
    with TestClient(app) as client:
        chat(client, session, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        app_reply = chat(client, session, "xây dựng ứng dụng")
        data_reply = chat(client, session, "phân tích dữ liệu")
    assert app_reply["intent"] == data_reply["intent"] == "major_exploration"
    assert "hướng bạn vừa chọn" in data_reply["answer"]


def test_exploration_with_missing_year_then_short_interest():
    session = str(uuid4())
    with TestClient(app) as client:
        pending = chat(client, session, "Em thích lập trình, nên chọn ngành nào?")
        assert pending["status"] == "clarification_needed"
        answered = chat(client, session, "2026")
        assert answered["status"] == "answered"
        narrowed = chat(client, session, "phân tích dữ liệu")
    assert narrowed["intent"] == "major_exploration"
    assert narrowed["status"] == "answered"
    assert narrowed["sources"]


def test_independent_admission_question_does_not_get_treated_as_interest():
    session = str(uuid4())
    with TestClient(app) as client:
        chat(client, session, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        reply = chat(client, session, "Ngành nào xét A01?")
    assert reply["intent"] == "major_filter"
    assert reply["status"] == "answered"
    assert "A01 năm 2026" in reply["answer"]


def test_reset_prevents_reusing_an_exploration_question():
    session = str(uuid4())
    with TestClient(app) as client:
        chat(client, session, "Em thích lập trình, nên chọn ngành nào năm 2026?")
        chat(client, session, "bắt đầu lại")
        reply = chat(client, session, "phân tích dữ liệu")
    assert reply["status"] == "clarification_needed"
    assert reply["sources"] == []


def test_unknown_short_reply_does_not_invent_a_focus():
    session = str(uuid4())
    with TestClient(app) as client:
        chat(client, session, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        reply = chat(client, session, "đá bóng")
    assert reply["intent"] != "major_exploration" or reply["status"] != "answered"


def test_no_context_does_not_interpret_short_choice_as_followup():
    with TestClient(app) as client:
        reply = chat(client, str(uuid4()), "giải thuật toán")
    assert reply["status"] == "clarification_needed"
