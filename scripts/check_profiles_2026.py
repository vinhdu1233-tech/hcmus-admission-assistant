"""Offline audit of official HCMUS 2026 program descriptions.

Run after pulling code:
  python -m src.database.db
  python scripts/check_profiles_2026.py

This checker verifies data integrity and official domains, not that the
university has never updated the webpages after the review date.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAJORS = ROOT / "data" / "curated" / "majors_2026.json"
PROFILES = ROOT / "data" / "curated" / "program_profiles_2026.json"


def official_url(url: str) -> bool:
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    return (p.scheme == "https"
            and (host == "hcmus.edu.vn" or host.endswith(".hcmus.edu.vn"))
            and p.username is None and p.password is None)


def main() -> int:
    majors = json.loads(MAJORS.read_text(encoding="utf-8"))["majors"]
    curated = json.loads(PROFILES.read_text(encoding="utf-8"))
    profiles = curated["profiles"]
    codes = [item["code"] for item in majors]
    profile_codes = [item["code"] for item in profiles]
    missing = sorted(set(codes) - set(profile_codes))
    unknown = sorted(set(profile_codes) - set(codes))
    invalid_sources = [item["code"] for item in profiles
                       if not official_url(item["source_url"])]
    missing_metadata = [item["code"] for item in profiles
                        if not item.get("summary") or not item.get("reviewed_on")]

    print(f"Majors in 2026 admissions dataset: {len(codes)}")
    print(f"Profiles with source-backed summaries: {len(profiles)}")
    print(f"Unique profile IDs: {len(set(profile_codes))}")
    print(f"Missing: {missing}")
    print(f"Unknown codes: {unknown}")
    print(f"Untrusted URLs: {invalid_sources}")
    print(f"Missing summary/review date: {missing_metadata}")
    print(f"Recorded source discrepancies: {len(curated.get('review_flags', []))}")

    for warning in curated.get("review_flags", []):
        print(f"REVIEW NOTE {warning['code']}: {warning['reason']}")

    ok = (len(codes) == len(profiles) == len(set(profile_codes)) == 39
          and not missing and not unknown and not invalid_sources
          and not missing_metadata)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
