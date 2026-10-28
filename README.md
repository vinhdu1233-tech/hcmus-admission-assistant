# HCMUS Admission & Study Assistant — Team 5

> Independent CSC10014 student project. **Not an official HCMUS website.**
> All admissions requirements must be checked against current official HCMUS notices.

## Features

1. **Verified Admission Lookup:** Chat interface for admission questions; sourced database and retrieval still require full integration.
2. **Major Exploration:** Chat interface for questions about programs and student interests; recommendation logic/LLM is a separate backend workstream.
3. **Application Checklist & Progress Tracker:** Choose an admission year and method, then track method-specific tasks. The 2026 Method 2 includes separate THPT or ĐGNL paths with transcript requirements; the 2025 Method 2 and Method 3 use different exam results. Checklist progress is saved locally per selection.

The checklist is **personal planning guidance**, not an official mandatory-document checklist, admission decision, or automatic application submission.

## Start the website — Node.js 18+

```bash
cd ui
npm start
```

Open **http://localhost:5500/** or **http://localhost:5500/#planner** for the checklist.

If port 5500 is busy:

```bash
PORT=5501 npm start
```

No `npm install` is needed (zero third-party Node dependencies). Default mode is **DEMO**; the chat is not real admissions retrieval.

## Connect to FastAPI

In terminal 1, from repository root (Python 3.10+ environment with backend dependencies installed):

```bash
python -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

In terminal 2:

```bash
cd ui
CHAT_MODE=api PORT=5501 npm start
```

Open **http://localhost:5501/**. The Node.js frontend sends `POST /api/chat` to its local proxy, which forwards to FastAPI `POST /chat`. The existing FastAPI scaffold does not yet deliver official retrieved answers.

## Checks

```bash
cd ui && npm run check
cd ..
node tests/test_planner_methods.mjs
python -m pytest -q tests/test_api_smoke.py
```

For browser QA: change year 2025/2026; switch method 2 vs 3 in 2025; choose THPT vs ĐGNL under method 2 in 2026; tick boxes, reload, and check persistence. On 2027, no official method/checklist should be fabricated.

## Project layout

- `ui/index.html`, `ui/style.css`, `ui/app.js` — website and fullscreen chat
- `ui/admission-methods.js` — method and task configuration with official links
- `ui/server.mjs` — Node.js server and FastAPI proxy
- `src/api/main.py` — Python FastAPI scaffold
- `docs/` — scope, architecture, API contract, design, and weekly log
- `tests/` — initial smoke and planner configuration checks

## Sources and limitations

- Official HCMUS admissions portal: https://tuyensinh.hcmus.edu.vn/
- 2026 Method 2 (THPT or ĐGNL combined with transcript): https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-2/
- 2025 Methods 2 and 3: https://tuyensinh.hcmus.edu.vn/thong-bao-ve-phuong-thuc-xet-tuyen-2-va-3-nam-2025/

Admission rules can change by year and program. Do not commit API keys or private student data. The project uses Issues, feature branches, PRs, and peer review.
