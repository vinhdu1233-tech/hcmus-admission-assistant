"""Offline checks for source-backed 2026 descriptions and all 3 feature interfaces."""
import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.assistant.retrieval import retrieve_majors
from src.database.db import connect, initialize_database, all_majors
from scripts.discover_program_profiles import build_review, score_match, parse_catalog


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_PROVIDER", "none")
    monkeypatch.setenv("HCMUS_DB_PATH", str(tmp_path / "unit.sqlite3"))
    initialize_database()


def test_verified_profiles_are_joined_to_2026_majors():
    rows = all_majors(2026)
    assert len(rows) == 39
    verified = [r for r in rows if r.get("official_profile")]
    assert len(verified) >= 5
    assert all(r["profile_source_url"].startswith(
        "https://tuyensinh.hcmus.edu.vn/") for r in verified)


def test_unknown_ai_program_code_not_silently_bound_to_profile():
    with connect() as db:
        row = db.execute(
            "SELECT * FROM program_profiles WHERE year=2026 AND major_code='7480107'"
        ).fetchone()
    assert row is None  # Program page prints a different program code.


def test_lexical_retrieval_includes_provenance():
    found = retrieve_majors("Em thích lập trình và toán, nên chọn ngành nào năm 2026?", 2026, 5)
    assert found
    assert any(row.get("official_profile") for row in found)


def test_feature1_official_a01_filter_and_year_check():
    with TestClient(app) as client:
        result = client.post("/chat", json={
            "message": "Ngành nào xét tuyển A01 năm 2026?"
        }).json()
        assert result["status"] == "answered"
        assert result["intent"] == "major_filter"
        assert "Trí tuệ nhân tạo" in result["answer"]
        assert result["sources"]
        newer = client.post("/chat", json={
            "message": "Ngành nào xét tuyển A01 năm 2027?"
        }).json()
        assert newer["status"] == "insufficient_evidence"


def test_feature2_official_profile_links_and_conversational_question():
    with TestClient(app) as client:
        result = client.post("/chat", json={
            "message": "Em thích Python, lập trình và toán, nên chọn ngành nào năm 2026?"
        }).json()
    assert result["status"] == "answered"
    assert result["intent"] == "major_exploration"
    assert "Bạn thích hơn" in result["answer"]
    assert any("nganh-" in s["url"] or "nhom-nganh-" in s["url"] for s in result["sources"])


def test_feature2_missing_evidence_asks_follow_up():
    with TestClient(app) as client:
        result = client.post("/chat", json={
            "message": "Em thích đá bóng và nấu ăn, nên chọn ngành nào năm 2026?"
        }).json()
    assert result["status"] == "clarification_needed"
    assert result["sources"] == []


def test_catalog_parser_restricts_to_official_domain():
    html = """<a href="https://tuyensinh.hcmus.edu.vn/nganh-khoa-hoc-may-tinh-chuong-trinh-tien-tien/">
       Ngành Khoa học máy tính (Chương trình tiên tiến)</a>
       <a href="https://example.com/forged-profile/">Ngành Trí tuệ nhân tạo</a>"""
    candidates = parse_catalog(html)
    assert len(candidates) == 1
    assert "tuyensinh.hcmus.edu.vn" in candidates[0]["url"]


def test_candidate_review_does_not_auto_approve():
    majors = [{"code":"7480107", "name":"Trí tuệ nhân tạo"}]
    candidates = [{"title":"Ngành Trí tuệ nhân tạo",
                   "url":"https://tuyensinh.hcmus.edu.vn/nganh-tri-tue-nhan-tao/"}]
    result = build_review(majors, candidates, set())
    assert result[0]["review_status"] == "needs_manual_review"
    assert "7480207" in result[0]["warning"]
    assert score_match("Trí tuệ nhân tạo", "Ngành Trí tuệ nhân tạo") > 0.5
