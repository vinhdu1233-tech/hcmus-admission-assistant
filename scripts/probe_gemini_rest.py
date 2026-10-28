"""One direct Gemini REST call to isolate SDK issues from Gemini API availability.

Unlike models.list, generateContent verifies live inference from your API key.
Safe output: prints only model, HTTP code and success, never API keys or payloads.
Run from repository root: python scripts/probe_gemini_rest.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

key = os.getenv("GEMINI_API_KEY", "").strip()
model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()

if not key:
    print("GEMINI_API_KEY: MISSING. Configure .env first.")
    sys.exit(2)
if not model or not all(c.isalnum() or c in ".-_" for c in model):
    print("Invalid model name")
    sys.exit(2)

url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent"
payload = {
    "contents": [{"parts": [{"text": "Xin chào"}]}],
    "generationConfig": {
        "thinkingConfig": {"thinkingLevel": "minimal"},
        "maxOutputTokens": 128
    },
}
request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "x-goog-api-key": key},
    method="POST",
)
print("Model:", model)
print("Test: direct REST generateContent (one request, no SDK, no Search grounding)")
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
        text = "".join(
            part.get("text", "")
            for candidate in result.get("candidates", [])
            for item in candidate.get("content", {}).get("parts", [])
            if (part := item)
        )
        print("HTTP STATUS:", response.status)
        print("RESPONSE:", text.strip()[:160] or "(response contains no text)")
except urllib.error.HTTPError as exc:
    print("HTTP STATUS:", exc.code)
    print("REST RESULT: FAILED")
    print("For 503/504, see official Gemini API status/troubleshooting.")
    sys.exit(1)
except (urllib.error.URLError, TimeoutError, OSError) as exc:
    print("NETWORK ERROR TYPE:", type(exc).__name__)
    print("REST RESULT: FAILED")
    sys.exit(1)
