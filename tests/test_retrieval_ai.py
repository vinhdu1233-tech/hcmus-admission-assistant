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
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "none")
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
    monkeypatch.setenv("AI_PROVIDER", "openai")
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
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key-only")
    assert explain_with_ai("Em thích lập trình", candidates) is None


def test_gemini_sdk_mock_returns_valid_codes(monkeypatch):
    # Run Gemini integration without a real API call or key.
    from google import genai
    candidates = retrieve_majors("Em thích Python, lập trình năm 2026?", 2026, 5)
    target = candidates[0]["code"]
    called = {"closed": False}

    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-3.5-flash-lite"
            assert kwargs["config"].response_mime_type == "application/json"
            assert target in kwargs["contents"]
            return types.SimpleNamespace(text=json.dumps({
                "recommendations": [{
                    "code": target,
                    "reason": "Ngành này liên quan đến sở thích lập trình được nêu trong câu hỏi."
                }]
            }))

    class FakeClient:
        def __init__(self, api_key, http_options):
            assert api_key == "mock-gemini-only"
            self.models = FakeModels()

        def close(self):
            called["closed"] = True

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-only")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    result = explain_with_ai("Em thích lập trình", candidates)
    assert list(result) == [target]
    assert called["closed"]


def test_gemini_invalid_code_falls_back_without_network(monkeypatch):
    from google import genai
    candidates = retrieve_majors("Em thích Python, lập trình năm 2026?", 2026, 5)

    class FakeModels:
        def generate_content(self, **kwargs):
            return types.SimpleNamespace(text=json.dumps({
                "recommendations": [{
                    "code": "FAKE_MAJOR_ID",
                    "reason": "Nội dung được tạo ra không dựa trên mã ngành được cung cấp."
                }]
            }))

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

        def close(self):
            pass

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-only")
    assert explain_with_ai("Em thích lập trình", candidates) is None


def test_ollama_local_structured_output_without_network(monkeypatch):
    """Mock the local HTTP server: model can only recommend retrieved codes."""
    from urllib import request
    candidates = retrieve_majors("Em thích lập trình năm 2026?", 2026, 5)
    target = candidates[0]["code"]
    called = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, length):
            return json.dumps({
                "response": json.dumps({"recommendations": [{
                    "code": target,
                    "reason": "Bạn quan tâm lập trình và ngành này có từ khóa đó trong dữ liệu."
                }]}, ensure_ascii=False)
            }, ensure_ascii=False).encode("utf-8")

    def fake_urlopen(req, timeout):
        assert req.full_url == "http://127.0.0.1:11434/api/generate"
        body = json.loads(req.data)
        assert body["model"] == "qwen3:4b"
        assert body["stream"] is False and body["think"] is False
        assert target in body["format"]["properties"]["recommendations"]["items"]["properties"]["code"]["enum"]
        called.append(body)
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    result = explain_with_ai("Em thích lập trình", candidates)
    assert result and target in result
    assert len(called) == 1


def test_ollama_unknown_major_falls_back(monkeypatch):
    from urllib import request
    candidates = retrieve_majors("Em thích lập trình năm 2026?", 2026, 5)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, length):
            return json.dumps({
                "response": json.dumps({"recommendations": [{
                    "code": "FAKE_MAJOR",
                    "reason": "Đây là một ngành không có trong database."
                }]})
            }).encode("utf-8")

    monkeypatch.setattr(request, "urlopen", lambda req, timeout: FakeResponse())
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    assert explain_with_ai("Em thích lập trình", candidates) is None


def test_ollama_unavailable_returns_retrieval_fallback(monkeypatch):
    from urllib import error, request

    def offline(req, timeout):
        raise error.URLError("offline")

    monkeypatch.setattr(request, "urlopen", offline)
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    candidates = retrieve_majors("Em thích lập trình năm 2026?", 2026, 5)
    assert explain_with_ai("Em thích lập trình", candidates) is None
