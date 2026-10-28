"""Discover candidate HCMUS program-profile pages for the 39 admissions codes.

Run: python scripts/discover_program_profiles.py
Optional: python scripts/discover_program_profiles.py --fetch-excerpts

Creates a *review queue* at data/processed/program_profile_candidates_2026.json.
It does NOT overwrite curated/verified data or the SQLite database.
"""
from __future__ import annotations
import argparse
from difflib import SequenceMatcher
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "https://tuyensinh.hcmus.edu.vn/khoa-dao-tao/"
MAJORS = ROOT / "data/curated/majors_2026.json"
VERIFIED = ROOT / "data/curated/program_profiles_2026.json"
OUTPUT = ROOT / "data/processed/program_profile_candidates_2026.json"


def normalize(value: str) -> str:
    x = unicodedata.normalize("NFD", value.casefold())
    return "".join(c for c in x if unicodedata.category(c) != "Mn").replace("đ", "d")


def clean_title(value: str) -> str:
    text = normalize(value)
    for prefix in ("nhom nganh ", "nganh ", "chuong trinh "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = re.sub(r"\([^)]*ct\s*:\s*\d+[^)]*\)", "", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def score_match(major: str, title: str) -> float:
    """Candidate ranking only, not proof that admission/program codes match."""
    a, b = clean_title(major), clean_title(title)
    if not a or not b:
        return 0.0
    score = SequenceMatcher(None, a, b).ratio()
    aw, bw = set(a.split()), set(b.split())
    overlap = len(aw & bw) / max(len(aw | bw), 1)
    score = 0.55 * score + 0.45 * overlap
    # Prevent a standard program page automatically matching a DKD or TT variant.
    for marker in ("tang cuong tieng anh", "tien tien", "nhom nganh"):
        is_a = marker in normalize(major)
        is_b = marker in normalize(title)
        if is_a != is_b:
            score *= 0.65
    return round(score, 4)


def fetch_html(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "tuyensinh.hcmus.edu.vn":
        raise ValueError("External domain forbidden")
    req = Request(url, headers={"User-Agent": "HCMUS-guide-coursework-review/1.0"})
    with urlopen(req, timeout=20) as response:
        return response.read(2_000_000).decode("utf-8", errors="replace")


def parse_catalog(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    options: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        link = urljoin(CATALOG, a["href"]).split("#", 1)[0]
        parsed = urlparse(link)
        if parsed.hostname != "tuyensinh.hcmus.edu.vn":
            continue
        if not re.match(r"^(?:Nhóm ngành|Ngành)\s+", label, re.IGNORECASE):
            continue
        if link in seen:
            continue
        seen.add(link)
        options.append({"title": label, "url": link})
    return options


def excerpt_from_html(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # Human review only; avoid navigation and unrelated footer material.
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in soup.select("main p, article p, .entry-content p")
    ]
    useful = [p for p in paragraphs if 45 <= len(p) <= 750]
    return " ".join(useful[:3])[:1000]


def build_review(majors: list[dict], candidates: list[dict], verified_codes: set[str]) -> list[dict]:
    records = []
    for major in majors:
        ranked = sorted(
            ({**c, "match_score": score_match(major["name"], c["title"])} for c in candidates),
            key=lambda x: (-x["match_score"], x["title"]),
        )
        records.append({
            "code": major["code"],
            "name": major["name"],
            "review_status": "already_verified" if major["code"] in verified_codes else "needs_manual_review",
            "matches": [x for x in ranked[:3] if x["match_score"] >= 0.28],
            "warning": (
                "HCMUS 2026 admissions code 7480107 differs from program-profile 7480207; "
                "verify before approving profile."
                if major["code"] == "7480107" else ""
            ),
        })
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-excerpts", action="store_true",
                        help="Fetch top candidate profile pages (respectfully, one page at a time)")
    args = parser.parse_args()

    majors = json.loads(MAJORS.read_text(encoding="utf-8"))["majors"]
    approved = json.loads(VERIFIED.read_text(encoding="utf-8"))
    verified_codes = {x["code"] for x in approved["profiles"]}
    catalog = parse_catalog(fetch_html(CATALOG))
    records = build_review(majors, catalog, verified_codes)

    if args.fetch_excerpts:
        cache = {}
        for entry in records:
            if entry["review_status"] == "already_verified":
                continue
            if not entry["matches"]:
                continue
            suggestion = entry["matches"][0]
            url = suggestion["url"]
            if suggestion["match_score"] < 0.50:
                continue
            if url not in cache:
                try:
                    cache[url] = excerpt_from_html(fetch_html(url))
                except Exception as exc:
                    cache[url] = "FETCH ERROR (" + type(exc).__name__ + ")"
                time.sleep(0.5)
            suggestion["excerpt_to_verify"] = cache[url]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "year": 2026,
        "source_catalog": CATALOG,
        "note": "Candidate URLs and excerpts only; NOT verified descriptions and NOT imported into SQLite.",
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Admissions records:", len(records))
    print("Previously verified profiles:", len(verified_codes))
    print("Unreviewed records:", sum(r["review_status"] == "needs_manual_review" for r in records))
    print("Saved review queue:", OUTPUT)


if __name__ == "__main__":
    main()
