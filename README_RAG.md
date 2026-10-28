# HCMUS Guide — Retrieval + AI (Feature 2 MVP)

## What is implemented

- SQLite 2026 data: program **name/code/quota/combinations** and source URL from the official HCMUS admissions table.
- Local **BM25-style lexical retrieval** in `src/assistant/retrieval.py`. Searches program names and editorial tags; supports Vietnamese accent normalization and a small synonym dictionary. No vector embeddings, external database, or API key required.
- **Optional Gemini Free Tier or OpenAI** in `src/assistant/ai.py`. Choose with `AI_PROVIDER=gemini` (recommended for demo) or `AI_PROVIDER=openai`. Both return JSON with codes and reasons, which are validated against SQLite candidates; unknown codes and provider errors cause a local retrieval fallback. No key is sent to the browser.
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

## Enable Gemini Free Tier (recommended for your Mac demo)

1. In https://aistudio.google.com/api-keys , use the key already created in your **Free tier** project. Click the **copy** icon on the key row. Do not enable billing if your intention is to stay on Free tier.
2. From repository root: `cp -n .env.example .env`. Open `.env` locally and use:
   ```dotenv
   AI_PROVIDER=gemini
   GEMINI_API_KEY=PASTE_YOUR_SECRET_HERE
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
3. `source .venv/bin/activate && python -m pip install -r requirements-backend-dev.txt`.
4. Restart FastAPI after editing `.env` (stop previous server with Ctrl+C). Node UI must be started using `CHAT_MODE=api`.
5. Ask: `Em thích Python, lập trình và toán, nên chọn ngành nào năm 2026?`. If AI responds successfully, the output starts `AI hỗ trợ giải thích`. If it instead says `AI chưa cấu hình hoặc tạm không khả dụng`, Gemini is unreachable or the model, key, quota, or permissions need review; Retrieval still works.

Security:
- NEVER commit `.env`, paste keys into chat or logs, or expose a key in browser JavaScript. The server reads keys from `.env`; `.gitignore` excludes the secret file.
- No paid Google billing is required **for an eligible Free Tier project** and a Free Tier-supported model, subject to account/project and rate limits.
- Free Tier content may be used by Google to improve products; avoid real students' personal or sensitive information when demoing. See https://ai.google.dev/gemini-api/docs/pricing .
- For models and limits check https://aistudio.google.com/docs/rate-limits (per-project).
- If you previously used OpenAI, set `AI_PROVIDER=gemini`. The presence of an `OPENAI_API_KEY` alone does not cause paid API requests when Gemini is selected.

To use OpenAI instead, set `AI_PROVIDER=openai`, `OPENAI_API_KEY=your_key`, and `OPENAI_MODEL=your_accessible_model`. OpenAI billing is separate.

To force offline tests/fallback, set `AI_PROVIDER=none` in your environment.

## Tests — mock only, safe even with an API key in .env

```bash
source .venv/bin/activate
python -m pytest -q tests/test_api_smoke.py tests/test_db_router.py tests/test_retrieval_ai.py
```

The tests isolate the database and set `AI_PROVIDER=none` by default, overriding to mocked provider modes only for simulated Gemini/OpenAI calls. They do **not** validate the real key or network access.

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

Expected: `intent: major_exploration`, `status: answered`, HCMUS links in `sources`, 39/39 coverage (assuming the validated 39-row seed is imported). A visible explanation beginning with `AI hỗ trợ` means the selected provider returned a valid structured response; `AI chưa cấu hình hoặc tạm không khả dụng` means the local fallback was used. Tests **mock AI responses** and do not verify your personal API key, billing, or model access.

## Architecture

```text
Browser (Node :5501)
  -> POST /api/chat -> FastAPI (:8000) -> intent router
     -> SQLite (39 2026 program rows) -> lexical retrieval -> top 5 candidates
        -> Optional Gemini GenAI or OpenAI / structured JSON -> validate known program codes
           -> server renders official program names and URL citation
        -> Missing key / failure -> local retrieval explanation
```

Reference: https://developers.openai.com/api/docs/guides/text and https://developers.openai.com/api/docs/guides/structured-outputs
