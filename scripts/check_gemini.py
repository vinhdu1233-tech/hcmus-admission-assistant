"""Optional real Gemini API connectivity check; does NOT display the API key.

Run from repository root: python scripts/check_gemini.py
This makes ONE small provider request, within an eligible Free Tier quota.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

key = os.getenv("GEMINI_API_KEY", "").strip()
model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

print("AI_PROVIDER =", os.getenv("AI_PROVIDER", "(not set)"))
print("GEMINI_MODEL =", model)
print("GEMINI_API_KEY =", "configured" if key else "missing")

if not key:
    print("Create .env at the repository root and set GEMINI_API_KEY before testing.")
    sys.exit(2)

try:
    from google import genai
    from google.genai import types

    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000)) as client:
        result = client.models.generate_content(
            model=model,
            contents="Trả lời đúng một từ: OK",
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=64,
            ),
        )
    print("Gemini request: SUCCESS")
    print("Response:", (result.text or "(empty)")[:80])
except Exception as exc:
    print("Gemini request: FAILED")
    print("Error class:", type(exc).__name__)
    print("HTTP/code:", getattr(exc, "code", getattr(exc, "status_code", "N/A")))
    print("Possible causes: invalid key, unavailable model, Free Tier rate limit, network timeout.")
    # Never print the raw exception; it could include request details.
    sys.exit(1)
