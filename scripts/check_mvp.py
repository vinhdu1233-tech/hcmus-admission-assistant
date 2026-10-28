"""Offline, no-provider-charge MVP checklist for HCMUS Guide.

Runs FastAPI + SQLite + Retrieval regression tests, then available local
Feature-3 Node tests. Browser localStorage persistence needs a manual check.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = [
    "tests/test_api_smoke.py",
    "tests/test_db_router.py",
    "tests/test_retrieval_ai.py",
    "tests/test_official_profiles.py",
]


def run(command: list[str], env: dict[str, str]) -> bool:
    print("\n$ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    return result.returncode == 0


def main() -> int:
    env = {**os.environ, "AI_PROVIDER": "none", "OPENAI_API_KEY": "",
           "GEMINI_API_KEY": ""}
    print("HCMUS MVP checks — real paid/cloud API calls disabled")

    if not run([sys.executable, "-m", "pytest", "-q", *TEST_FILES], env):
        print("\nFAIL: Backend/Feature 1-2 automated tests")
        return 1
    print("\nPASS: Backend, Feature 1, Feature 2 (mock AI + source checks)")

    node = shutil.which("node")
    planner = ROOT / "ui" / "admission-methods.js"
    planner_test = ROOT / "tests" / "test_planner_methods.mjs"

    if not node or not planner.exists() or not planner_test.exists():
        print("\nCHECK MANUALLY: Feature 3 Node tests are missing in this checkout.")
        print("Your local untracked ui/admission-methods.js and "
              "tests/test_planner_methods.mjs may exist on Mac but not GitHub.")
        print("Do not claim Feature 3 passed until files are available and tested.")
    else:
        if not run([node, "--check", str(planner)], env):
            return 1
        if not run([node, "--test", str(planner_test)], env):
            print("FAIL: Feature 3 checklist config tests")
            return 1
        print("PASS: Feature 3 config automated tests")

    print("\nMANUAL BROWSER QA:")
    print("1. Feature 1: search A01 2026; verify valid major list + HCMUS source.")
    print("2. Feature 2: ask 'Em thích Python và toán, nên chọn ngành nào năm 2026?'")
    print("   Confirm local Ollama explanation + HCMUS profile citations.")
    print("3. Feature 2: unrelated interests -> clarification, no made-up program.")
    print("4. Feature 3: choose 2025 PT2 and 2026 PT2; verify distinct checklist steps.")
    print("5. Feature 3: mark steps, reload browser, check progress persists.")
    print("6. Feature 3: switch selection and verify progress is tracked separately.")
    print("7. Confirm mobile layout and no browser console/network errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
