# HCMUS Admission & Study Assistant
# Project brief / Problem boundary — DRAFT FOR TEAM REVIEW
**Project Goal**

To develop a web-based intelligent virtual assistant that helps prospective HCMUS students access verified admission information, explore academic programs, and receive general study preparation guidance through a natural-language chatbot.

The assistant will use information collected from official HCMUS sources, combine deterministic search and filtering with AI-assisted responses, and provide traceable source references whenever answering factual admission questions.

## 1. Project
**HCMUS Admission & Study Assistant** — independent CSC10014 student prototype, not an official HCMUS service.

## 2. Problem statement
High school students considering HCMUS must sometimes navigate multiple official announcements to understand majors, methods, years and preparation resources. The team hypothesizes that a searchable assistant with citations may make that information easier to locate and understand. Validate this hypothesis through short interviews or a small usability test; don't assert it is proven.

## 3. Target users
- Primary: Grade 11–12 students considering admission to HCMUS.
- Secondary: Incoming HCMUS freshmen seeking general study-preparation guidance.

## 4. In scope (MVP)
1. Look up admissions information **for years present in the verified database**.
2. Browse majors and filter by published categories/subject combinations.
3. Ask natural-language questions about retrieved information; provide official citations.
4. Provide **general** study tips labeled as advice, not official policies.
5. Ask clarification for missing major or year; gracefully abstain if evidence absent.

## 5. Non-goals
- Admission application submission or account management.
- Guaranteed admission predictions or future admission scores.
- Access to private university/student records.
- Full university-wide real-time synchronization.
- Unrestricted autonomous browsing by LLM.

## 6. Computational Thinking
**Decomposition:** input → validation → classification/routing → rules/search/LLM → verify evidence → answer.
**Abstraction:** treat a source as `{title, url, admission_year, published_at, checked_at, content}`.
**Algorithms:** deterministic major/year filtering, relevance ranking, fallback rules.
**Evaluation:** repeatable benchmark + error taxonomy + before/after improvement.

## 7. Constraints & assumptions
- Team of six, eight-week **internal implementation plan**. The academic project sheet presents a ten-week arc; follow instructor/LMS deadlines for official submissions.
- Public official HCMUS documents; no access to any official admissions API is assumed.
- Deployment is optional until agreed; a reproducible local demo is acceptable as planned.
- Backend and UI must integrate by W5.

## 8. Proposed measurable success criteria (targets, not measured results)
- At least 10 representative use cases.
- At least 40 varied evaluation cases by W6.
- Factual admissions answers contain checkable year/source references; otherwise abstain.
- All defined critical end-to-end demo paths functional by W5.
- One documented before/after improvement by W7.

## 9. Open decisions
- [ ] Do we cover all university majors or an initial subset?
- [ ] Which exact admissions year(s) will the initial database support?
- [ ] How will source updates be reviewed and how often?
- [ ] Which LLM API and budget are permitted?
- [ ] Instructor confirms domain and final deadline.
