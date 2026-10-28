# UI wireframes / Information Architecture — HCMUS Guide (Node.js Edition)

Status: Frontend MVP design. This student project is not an official HCMUS website.

## Design direction

- Inspiration: editorial storytelling, full-bleed photography, generous typography, visual rhythm and whitespace.
- Identity: blue academic palette (`#102f4c`, `#eaf4fb`, `#b9d8ee`), cream-white, real HCMUS user-provided photos.
- No Pizza 4P's artwork, branding, code or copied content.

## Public page flow

1. Navigation / full-image campus hero and primary Chat CTA.
2. Project story: clear purpose + three trust principles.
3. Campus collage: 4 real user-provided photos in an asymmetrical layout.
4. Explore: admissions, majors, first-year preparation; each opens chat with a suggested question.
5. Explanation of responsible architecture / evidence-led answers.
6. Chat CTA: full-screen assistant rather than embedded small panel.
7. Official HCMUS sources and explicit independent student project disclaimer.

## Fullscreen assistant

- Button opens an actual full-viewport dialog (`position:fixed; inset:0`).
- Desktop: editorial blue sidebar + scrollable conversation panel + fixed composer.
- Mobile: single-screen conversation without sidebar; composer anchored to the bottom of the modal.
- Interactions: send button/Enter, Shift+Enter newline, suggested prompts, progress/typing, source links, closing with Escape, restore keyboard focus, focus trap.
- The server exposes `/api/config` and `/api/chat` on the same origin. Node proxies to FastAPI in API mode, avoiding browser CORS complexity.
- Demo replies do not invent admission facts or imply live AI service.

## Colors and typography

- Navy: `#102f4c`
- Ink: `#173452`
- Blue: `#3e77a7`
- Pale Blue: `#eaf4fb`
- Ice: `#f3f8fc`
- Headings: Playfair Display with Georgia fallback
- Text: DM Sans with Arial fallback

## Responsive behavior

- > 900px: desktop navigation and two-column full-screen dialog.
- 601–900px: mobile navigation, gallery simplified, fullscreen chat single-column.
- <= 600px: phone-first large type scaling, stacked gallery, safe-area-aware composer.

## MVP integration contract

POST `/api/chat` from UI → Node proxy → FastAPI POST `/chat`:

```json
{"message":"HCMUS có những ngành nào năm 2026?","admission_year":2026}
```

Reply:

```json
{"answer":"Example only","intent":"admission_lookup","status":"answered","sources":[]}
```

Never fabricate official admission information: factual answers must be verified by M4's source registry and back-end retrieval.


## Feature 3 — Dynamic Application Checklist & Progress Tracker (Oct 2026)

Replaces the original "First-Year Study Guidance" feature with an independent
non-chatbot planning interface.

- Input: admission year, officially defined admission method, optional exam path.
- 2025: 1a, 1b, 1c, 1d, 2 (THPT), 3 (ĐGNL).
- 2026: 1a, 1b, 2; method 2 offers THPT+transcript and ĐGNL+transcript paths.
- 2027: no synthetic official methods; show unavailable until verified.
- Algorithm: select year → select method → select path where required → assemble
  common + method-specific + path-specific tasks → toggle items → calculate
  round(done / total * 100) → store by year/method/path in browser localStorage.
- Users can add/remove up to 25 personal tasks; progress does not sync across devices.
- All data/links are centrally configurable in \`ui/admission-methods.js\`.
- Sources: official HCMUS admissions announcements; details must be verified
  per year, course, and applicant category. The planning checklist is not a
  legally complete list of mandatory requirements.
- No automatic admissions application, deadlines or guarantees.
- QA: \`node tests/test_planner_methods.mjs\`, \`cd ui && npm run check\`,
  then browser tests for select changes, progress, reload, narrow layout,
  and the existing fullscreen assistant.
