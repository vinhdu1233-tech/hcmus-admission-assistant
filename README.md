# HCMUS Admission & Study Assistant — Week 1 starter

> Student prototype for CSC10014. **Not an official HCMUS product.** No live admissions integration and no AI backend in Week 1.

## Goal
A web-based assistant to help high-school students find sourced HCMUS admissions information, explore majors and get general study preparation suggestions.

## How to preview frontend (Week 1)

1. Install Python 3.10+ (or use VS Code Live Server).
2. From the repository root run: `python3 -m http.server 5500` (Windows may use `py -m http.server 5500`).
3. Open `http://localhost:5500/ui/`.
4. This is a static UI prototype. The message form has clearly labeled simulated responses; real backend integration starts later.

## Basic local check

```bash
python3 scripts/check_env.py
python3 -m unittest discover -s tests -v
```

## Week 1 deliverables
- `docs/brief/project_scope.md`, `docs/brief/use_cases.md`
- `docs/design/system_architecture.md`, `docs/design/api_contract.md`
- `docs/design/ui_wireframes.md`, the prototype under `ui/`
- `docs/team.md`, `docs/issues/week01_issues.md`, `docs/weekly-log/week01.md`
- Approved and merged PRs; `v0.1-brief` tag after milestone acceptance

## Planned technologies (subject to team approval)
Frontend: vanilla HTML/CSS/JavaScript; backend: Python FastAPI; local data: SQLite + curated official HCMUS pages; retrieval: search and rule filtering; LLM: optional configured API with fallback. The code for these features **does not exist yet**.

## Privacy / sources
Never commit `.env`, tokens, API keys, personal student data or scraped restricted resources. Do not claim information is updated in real time unless verified. Use official HCMUS references and include the admission year.

## Team workflow
Create an Issue → own branch → small commits → PR with test evidence → peer review → merge. See `docs/team.md` and `docs/issues/week01_issues.md`.
