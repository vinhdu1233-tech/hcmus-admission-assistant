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
