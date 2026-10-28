# HCMUS Guide — Retrieval + AI (Feature 2 MVP)

## What is implemented

- SQLite 2026 data: program **name/code/quota/combinations** and source URL from the official HCMUS admissions table.
- Local **BM25-style lexical retrieval** in `src/assistant/retrieval.py`. Searches program names and editorial tags; supports Vietnamese accent normalization and a small synonym dictionary. No vector embeddings, external database, or API key required.
- Optional OpenAI **Responses API + JSON Schema** in `src/assistant/ai.py`. The model may explain why the retrieved *candidate programs* relate to the user's interests. The server only accepts program codes returned from retrieval, then renders official names and HCMUS sources from SQLite. Unknown IDs and provider failures cause a local fallback.
- Router integration in `src/assistant/router.py` for major exploration intent; Feature 1 SQL lookups and Feature 3 checklist remain separate.

**Evidence limitation:** The 2026 admissions table does **not** supply complete course curricula, job outcomes, salary expectations, personal aptitude measurements or guaranteed admission. `tags` are **group-authored hints**, not official HCMUS program descriptions. Suggestions are **exploratory, not a determination of personal fit**. To improve quality, curate verified departmental/program descriptions with per-paragraph URLs in a subsequent data-ingestion task.

## Install on macOS (run at repository root)

```bash
cd ~/Downloads/hcmus-admission-assistant
source .venv/bin/activate
python -m pip install -r requirements-backend-dev.txt
python -m src.database.db
python -m pytest -q tests/test_api_smoke.py tests/test_db_router.py tests/test_retrieval_ai.py
```

If you have unstaged local frontend changes, **stash or commit them before** doing `git pull --rebase origin feat/mvp-sqlite-router`. Do not use `git reset --hard` to resolve a rebase conflict.

## Enable AI (optional)

1. Get your own API key from https://platform.openai.com/api-keys. API usage is billed separately from the ChatGPT subscription and requires API access/billing.
2. Create `.env` at repository root: `cp .env.example .env`.
3. Open `.env` **locally** and set `OPENAI_API_KEY=your_key_here`; choose `OPENAI_MODEL=gpt-6-luna` or another accessible Responses API model that supports Structured Outputs.
4. Restart FastAPI **after** editing the environment. Never send your key in chat, browser client code, screenshots, GitHub commits, logs, or pull requests. `.gitignore` already excludes `.env`.

Without a key the server still returns retrieved candidates, explicitly labeled as **non-AI** fallback. API errors or a model response containing an unknown program code also fall back locally without leaking error details to students.

## Run end-to-end

Terminal 1 (repository root):

```bash
source .venv/bin/activate
python -m uvicorn src.api.main:app --reload --port 8000
```

Terminal 2:

```bash
cd ~/Downloads/hcmus-admission-assistant/ui
CHAT_MODE=api PORT=5501 npm start
```

Open http://localhost:5501/ and ask:

- `Em thích lập trình, Python và toán, nên chọn ngành nào năm 2026?`
- `Em thích vật lý và điện tử, gợi ý ngành phù hợp năm 2026?`
- `Em thích đá bóng và nấu ăn, nên chọn ngành nào năm 2026?` (should ask for more relevant interests, rather than fabricate a matched program)
- `Ngành nào xét tuyển A01 năm 2026?` (Feature 1 stays deterministic; all 39 records fit under the 50-row cap)

Or call the API directly:

```bash
curl -s http://127.0.0.1:8000/chat \\
  -H 'Content-Type: application/json' \\
  -d '{"message":"Em thích lập trình và toán, nên chọn ngành nào năm 2026?"}' \\
  | python -m json.tool
```

Expected: `intent: major_exploration`, `status: answered`, HCMUS links in `sources`, 39/39 coverage (assuming the validated 39-row seed is imported). A visible explanation beginning with `AI hỗ trợ` means the provider returned a valid structured response; `AI chưa cấu hình hoặc tạm không khả dụng` means the local fallback was used. Tests **mock AI responses** and do not verify your personal API key, billing, or model access.

## Architecture

```text
Browser (Node :5501)
  -> POST /api/chat -> FastAPI (:8000) -> intent router
     -> SQLite (39 2026 program rows) -> lexical retrieval -> top 5 candidates
        -> Optional Responses API / JSON Schema -> validate known program codes
           -> server renders official program names and URL citation
        -> Missing key / failure -> local retrieval explanation
```

Reference: https://developers.openai.com/api/docs/guides/text and https://developers.openai.com/api/docs/guides/structured-outputs
