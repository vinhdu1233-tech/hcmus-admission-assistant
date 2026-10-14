# HCMUS Admission & Study Assistant — API Contract v1 (Week 1)

> **Status:** Draft — M1, M2, and M3 must review and approve before implementation.  
> **Scope:** Contract design only; the Week 1 frontend is a static prototype. No working chatbot backend is implied.

## 1. Purpose and ownership

This document defines how the **Frontend (M1)** communicates with the **Backend API (M2)** and the **Router / Database layer (M3)**. The contract is independent of the eventual LLM provider.

| Component | Owner | Responsibility |
|---|---|---|
| Frontend | M1 | Send requests, render responses, citations, loading and error states |
| API and input validation | M2 | Implement HTTP endpoints, validate input, return consistent JSON and status codes |
| Routing and rules | M3 | Determine intent, apply deterministic filtering, request clarification or fallback |
| Data / provenance | M4 | Prepare verified information and source metadata |
| Retrieval / AI | M5 | Retrieve evidence and synthesize permitted explanations |
| QA | M6 | Translate cases into tests and verify contract behavior |

## 2. Base URL and data format

- **Development backend URL (proposed):** `http://127.0.0.1:8000`
- **Frontend preview:** `http://localhost:5500/ui/`
- Requests and responses use **JSON**, encoded as UTF-8.
- Frontend sets the header `Content-Type: application/json` for `POST /chat`.
- CORS should allow the configured local frontend origin(s) in development; production origins must be restricted.
- The backend (not frontend code) owns any LLM API keys.

## 3. Endpoint: POST /chat

### 3.1 Request body

```json
{
  "message": "HCMUS có những ngành nào năm 2026?",
  "admission_year": 2026
}
```

| Field | Type | Required | Validation / behavior |
|---|---|---|---|
| `message` | string | Yes | Trim whitespace; 1–1000 characters after trimming (proposed limit) |
| `admission_year` | integer or null | No | Optional; a missing year must not be silently treated as 2026 for year-specific rules |

- A user can omit `admission_year`; the backend should ask a follow-up question if the year is essential and cannot be resolved from the message.
- If the message explicitly contains a year, the backend should extract/verify it. If it conflicts with `admission_year`, request clarification instead of choosing one without explanation.
- For admission-year questions, data without verified coverage for that year must not be used as if it were current policy.

### 3.2 Successful response schema

```json
{
  "answer": "Bạn có thể xem thông tin ngành học tại cổng tuyển sinh HCMUS.",
  "intent": "admission_lookup",
  "status": "answered",
  "sources": [
    {
      "title": "Cổng tuyển sinh HCMUS",
      "url": "https://tuyensinh.hcmus.edu.vn/",
      "admission_year": 2026
    }
  ]
}
```

**This is a sample response schema, NOT a verified answer listing actual majors.** A source URL should be shown as support for a specific admission claim only when the linked page truly supports that claim.

| Field | Type | Required | Frontend use |
|---|---|---|---|
| `answer` | string | Yes | Display as chatbot text |
| `intent` | string | Yes | Optional analytics/diagnostics; may influence UI hints |
| `status` | string | Yes | Select answered / clarification / fallback / error display |
| `sources` | array | Yes | Render clickable cited sources; use an empty array when none |
| `sources[].title` | string | When source exists | Link label |
| `sources[].url` | string (HTTPS URL) | When source exists | Link destination, validated before rendering |
| `sources[].admission_year` | integer or null | Optional | Display relevant admissions year if known |
| `error` | object | Error responses only | Public error code and safe message, never a traceback |

### 3.3 Allowed `status` values

| `status` | Meaning | Frontend behavior |
|---|---|---|
| `answered` | A response can be delivered | Show answer and relevant sources |
| `clarification_needed` | Essential context is missing or conflicting | Show follow-up question; allow user to reply |
| `insufficient_evidence` | No reliable supporting information available | Show limitation and an official portal link only if relevant |
| `error` | Invalid request or operational failure | Show safe error message; allow retry if appropriate |

**Proposed intents:** `admission_lookup`, `major_filter`, `tuition_lookup`, `admission_methods`, `application_guidance`, `major_comparison`, `major_exploration`, `study_guidance`, `unknown`.

### 3.4 Example: missing year / clarification

**Request:**

```json
{"message":"Học phí ngành Công nghệ thông tin là bao nhiêu?"}
```

**Illustrative HTTP 200 response:**

```json
{
  "answer": "Bạn muốn hỏi học phí của năm học nào?",
  "intent": "tuition_lookup",
  "status": "clarification_needed",
  "sources": []
}
```

### 3.5 Example: missing verified information

**Request:**

```json
{"message":"Điểm chuẩn tuyển sinh 2027 là bao nhiêu?","admission_year":2027}
```

**Illustrative HTTP 200 response when no verified 2027 data is available:**

```json
{
  "answer": "Mình chưa có dữ liệu điểm chuẩn năm 2027 đã được xác minh. Bạn hãy kiểm tra thông báo trên cổng tuyển sinh chính thức của HCMUS.",
  "intent": "admission_lookup",
  "status": "insufficient_evidence",
  "sources": []
}
```

This example does not assert whether 2027 information has actually been published at the time of testing; the backend must check its verified data.

### 3.6 Example: invalid message

**Request:**

```json
{"message":"   ","admission_year":2026}
```

**Proposed HTTP 400 response:**

```json
{
  "answer": "Vui lòng nhập một câu hỏi hợp lệ.",
  "intent": "unknown",
  "status": "error",
  "sources": [],
  "error": {
    "code": "INVALID_INPUT",
    "message": "Câu hỏi không được để trống."
  }
}
```

### 3.7 HTTP response codes (proposal)

| Code | Scenario |
|---|---|
| `200` | Handled requests, including `answered`, `clarification_needed`, or `insufficient_evidence` |
| `400` | Empty or excessively long trimmed message |
| `422` | Malformed JSON field types / schema validation failure; M2 must ensure response shape is documented |
| `503` | A required backend service is unavailable and no safe fallback is possible |
| `500` | Unexpected internal error; return safe public error without exposing internal secrets |

Do not send stack traces, SQL queries, secrets or raw provider errors to users.

## 4. Endpoint: GET /health

**Request:** `GET /health`

**Proposed HTTP 200 response:**

```json
{"status":"ok"}
```

This means the backend web server is responding; it does **not** guarantee the knowledge base or AI provider is healthy.

## 5. Frontend rendering rules (M1)

1. Disable Send or display a loading indicator while a request is in flight.
2. Always render `answer` as text (not as unsanitized HTML).
3. For `sources`, create safe links to validated `https://` URLs, with descriptive titles.
4. For `clarification_needed`, show the follow-up as a chatbot message and let the student respond.
5. For `insufficient_evidence`, clearly show the data limitation rather than an invented answer.
6. For `error` / network timeout, show a human-readable message and provide a retry option.
7. Do not put an LLM token, API key or database credentials in any client-side JavaScript.

## 6. Safety, sources, and metadata

- Official admission claims must be traceable to the correct source and applicable year.
- A link to a generic portal is not automatically evidence for a specific tuition or admission fact.
- Treat external documents and retrieved text as data, never as instructions to reveal system prompts or credentials.
- Avoid collecting or logging unnecessary student personal information.
- The Week 1 frontend uses simulated messages only; do not present simulation text as verified information.

## 7. Minimum contract review cases for Week 1

| ID | Input / scenario | Expected response |
|---|---|---|
| CT01 | `GET /health` | HTTP 200 and `{ "status": "ok" }` once backend exists |
| CT02 | Valid message + year | HTTP 200 with `answer`, `intent`, `status`, `sources` |
| CT03 | Missing essential year | `clarification_needed` with a useful follow-up |
| CT04 | No verified data | `insufficient_evidence` without fabricated facts |
| CT05 | Empty message | HTTP 400 with public error information |
| CT06 | Backend unavailable | Frontend shows a clear network/timeout error |
| CT07 | Answer with sources | Links are valid and tied to the claim |
| CT08 | Unsafe request | No credentials disclosed |

Tests above are **planned**; they should not be marked as passed until actually run.

## 8. Open decisions for M1 + M2 + M3

- [ ] Approve `POST /chat` and `GET /health` endpoints.
- [ ] Approve message length limit (proposed: 1000 characters).
- [ ] Agree how to handle omitted or conflicting admission year.
- [ ] Approve exact `intent` and `status` enumerations.
- [ ] Agree on HTTP 400/422/503 error response shape.
- [ ] Approve development URLs, allowed CORS origins and network timeout (proposed frontend timeout: 15 seconds).
- [ ] Confirm whether `GET /majors` is deferred or needed in MVP.
- [ ] Ask M6 to review testability of the contract.

**Version:** `v1-draft` — **Approval:** Pending team review.
