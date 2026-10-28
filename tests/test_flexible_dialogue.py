"""Contextual chat scenarios with offline SQLite and mocked/disabled Ollama.

Behavior is intentionally evidence-limited: no invented tuition or admissions
figures. Ensure a free-form response after the assistant's own question works.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.assistant.dialogue import Decision, decide_rules, contextual_major_search
from src.database.db import initialize_database


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("HCMUS_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AI_PROVIDER", "none")
    initialize_database()


def ask(client, sid, text, year=None):
    body = {"conversation_id": sid, "message": text}
    if year is not None:
        body["admission_year"] = year
    r = client.post("/chat", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("reply", [
    "lĩnh vực nghiên cứu",
    "mình thích làm thí nghiệm",
    "em muốn làm nghiên cứu trong phòng lab",
    "em thích thực hành",
])
def test_research_or_experiment_followup_without_repeating_year(reply):
    sid = str(uuid4())
    with TestClient(app) as client:
        first = ask(client, sid, "Em thích sinh học và hóa học, nên học ngành nào năm 2026?")
        assert first["intent"] == "major_exploration"
        assert first["status"] == "answered"
        narrowed = ask(client, sid, reply)
    assert narrowed["status"] == "answered"
    assert narrowed["intent"] == "major_exploration"
    assert "hướng bạn vừa chọn" in narrowed["answer"]
    assert "2026" in narrowed["answer"]
    assert narrowed["sources"]
    assert any(word in narrowed["answer"].lower() for word in ("sinh học", "hóa học", "công nghệ sinh học"))


def test_detail_uses_second_recommended_program_only():
    sid = str(uuid4())
    with TestClient(app) as client:
        first = ask(client, sid, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        second = ask(client, sid, "ngành thứ hai học gì?")
    assert second["status"] == "answered"
    assert "Thông tin giới thiệu ngành" in second["answer"]
    assert second["sources"]
    assert first["intent"] == second["intent"] == "major_exploration"


def test_ambiguous_that_program_requires_specific_choice():
    sid = str(uuid4())
    with TestClient(app) as client:
        ask(client, sid, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        response = ask(client, sid, "ngành đó học gì?")
    assert response["status"] == "clarification_needed"
    assert response["sources"] == []


def test_comparing_first_two_recommendations():
    sid = str(uuid4())
    with TestClient(app) as client:
        ask(client, sid, "Em thích lập trình và toán, nên chọn ngành nào năm 2026?")
        response = ask(client, sid, "so sánh hai ngành đầu")
    assert response["status"] == "answered"
    assert response["answer"].count("\n• ") == 2
    assert response["sources"]


def test_tuition_followup_does_not_invent_numbers():
    sid = str(uuid4())
    with TestClient(app) as client:
        ask(client, sid, "Em thích Python và toán, nên chọn ngành nào năm 2026?")
        response = ask(client, sid, "còn học phí?")
    assert response["intent"] == "tuition_lookup"
    assert response["status"] == "insufficient_evidence"
    assert response["sources"] == []
    assert "chưa có dữ liệu" in response["answer"].lower()


def test_explicit_admission_question_is_not_forced_into_interest():
    sid = str(uuid4())
    with TestClient(app) as client:
        ask(client, sid, "Em thích lập trình và toán, nên học ngành nào năm 2026?")
        response = ask(client, sid, "Ngành nào xét A01?")
    assert response["intent"] == "major_filter"
    assert "A01 năm 2026" in response["answer"]


def test_unrelated_hobby_has_no_fabricated_major_recommendation():
    sid = str(uuid4())
    with TestClient(app) as client:
        ask(client, sid, "Em thích sinh học và hóa học, nên học ngành nào năm 2026?")
        response = ask(client, sid, "mình chỉ thích đá bóng và nấu ăn")
    assert response["status"] == "clarification_needed"
    assert response["sources"] == []


def test_interest_only_shortcut_without_context_does_not_claim_grounding():
    with TestClient(app) as client:
        response = ask(client, str(uuid4()), "lĩnh vực nghiên cứu")
    assert response["status"] == "clarification_needed"


def test_contextual_search_retains_original_subject_for_generic_goal():
    rows = contextual_major_search(
        "lĩnh vực nghiên cứu", "em thích sinh học và hóa học năm 2026", 2026)
    assert rows
    assert any("sinh học" in row["name"].lower() for row in rows)


def test_rule_based_detail_priority_and_comparison():
    names=("x", "y", "z")
    assert decide_rules("ngành thứ hai học gì?", waiting_for_interest=True,
                        selected_codes=names) == Decision("detail", indices=(2,))
    assert decide_rules("so sánh hai ngành đầu", waiting_for_interest=True,
                        selected_codes=names) == Decision("compare", indices=(1, 2))


def test_local_llm_parser_mocks_novel_natural_interest(monkeypatch):
    from src.assistant import dialogue
    from urllib import request
    import json
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, _):
            return json.dumps({"response": json.dumps({
                "action": "interest", "focus": "untrusted other words", "indices": [],
            })}).encode()
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setattr(request, "urlopen", lambda req,timeout: FakeResponse())
    decision=dialogue.decide_ollama("mình thiên về nghiên cứu các phản ứng",
                                   question="em thích hóa học", year=2026,
                                   followup_prompt="Bạn thích gì?",
                                   candidate_names=["Hóa học", "Công nghệ sinh học"])
    assert decision.action == "interest"
    assert decision.focus == "mình thiên về nghiên cứu các phản ứng"
