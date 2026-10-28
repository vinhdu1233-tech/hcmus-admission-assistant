"""Offline regression tests: no network or real OpenAI key required."""
import json
import sys
import types

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.assistant.retrieval import retrieve_majors
from src.assistant.ai import explain_with_ai
from src.database.db import initialize_database


@pytest.fixture(autouse=True)
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("HCMUS_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initialize_database()


def test_retrieval_finds_programs_and_official_source():
    matches = retrieve_majors("Em thích Python, lập trình và toán, nên học ngành nào?", 2026, 5)
    assert matches
    assert any("Công nghệ thông tin" in m["name"] or "máy tính" in m["name"].lower()
               or "Trí tuệ nhân tạo" in m["name"] for m in matches)
    assert all(m["source_url"].startswith("https://tuyensinh.hcmus.edu.vn/") for m in matches)
    assert all(m.get("quota") is not None for m in matches)


def test_unrelated_interests_are_not_forced_into_a_major():
    assert retrieve_majors("Em thích đá bóng và nấu ăn", 2026) == []


def test_no_api_key_uses_explicit_non_ai_fallback():
    with TestClient(app) as client:
        r = client.post("/chat", json={"message": "Em thích lập trình và toán năm 2026?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "major_exploration"
    assert body["status"] == "answered"
    assert "AI chưa cấu hình" in body["answer"]
    assert body["sources"]


def test_unrelated_query_asks_for_clarification():
    with TestClient(app) as client:
        result = client.post("/chat", json={"message": "Em thích đá bóng và nấu ăn năm 2026?"}).json()
    assert result["status"] == "clarification_needed"
    assert result["sources"] == []


def test_ai_sdk_mock_only_allows_retrieved_code(monkeypatch):
    candidates = retrieve_majors("Em thích lập trình", 2026, 5)
    chosen = candidates[0]["code"]
    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["store"] is False
            assert "json_schema" == kwargs["text"]["format"]["type"]
            assert kwargs["text"]["format"]["schema"]["properties"]["recommendations"]["items"]["properties"]["code"]["enum"]
            return types.SimpleNamespace(output_text=json.dumps({"recommendations": [
                {"code": chosen, "reason": "Vì bạn thích lập trình, ngành này có từ khóa tương ứng."}
            ]}))
    class FakeOpenAI:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "mock-key-only"
            self.responses = FakeResponses()
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key-only")
    got = explain_with_ai("Em thích lập trình", candidates)
    assert list(got) == [chosen]
    assert "lập trình" in got[chosen]


def test_ai_rejects_unknown_program_codes(monkeypatch):
    candidates = retrieve_majors("Em thích lập trình", 2026, 5)
    class FakeResponses:
        def create(self, **kwargs):
            return types.SimpleNamespace(output_text=json.dumps({
                "recommendations": [{"code": "FAKE_PROGRAM", "reason": "Thông tin không hợp lệ do AI tạo."}]
            }))
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key-only")
    assert explain_with_ai("Em thích lập trình", candidates) is None
