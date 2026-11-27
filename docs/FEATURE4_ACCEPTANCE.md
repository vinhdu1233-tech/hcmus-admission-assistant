# Feature 4 — Smart Admission Monitoring & Alerts
Scope: HCMUS Guide, PR #14. No Apple/Google/Outlook export or synchronization.

## Acceptance
- Date extraction supports explicit Vietnamese d/m/yyyy ranges and end-only deadlines. Unknown hours, missing years, invalid dates and ambiguous methods must not be silently treated as official. Candidates include the source excerpt and require Admin review; end-only proposals require Admin to establish the start or enter a point deadline. Review and publishing are separate actions. Listing pages discover a bounded set of official dated notices; not a general-purpose crawler.
- Calendar has month/week/day/agenda views, search and upcoming deadline countdown. 2026 records are historical and cover selected published events, not every institution deadline. Common August events are repeated per method. No 2027 date is invented.
- Notification center includes unread counts, read/read-all and an event link. F3 users explicitly link a checklist to their account or load an existing saved plan. Subsequent edits to that linked plan in the current page session sync. Reminders include the number of unfinished tasks in the last saved matching year/method plan. No silent upload of shared localStorage. This is plan-level progress, not a guarantee of actual application submission.
- No cloud calendar export.
- Web Push still needs real VAPID, HTTPS, continuous worker and physical-device permission/delivery tests.

## Proposed F4 SLO and measurement
| Dimension | SLI | Proposed target | Evidence |
|---|---|---|---|
| Correctness | Explicit ranges correctly extracted and unsafe proposals withheld | 100% of supported acceptance fixtures; zero unreviewed publication | tests/test_feature4.py |
| Latency | p95 calendar API response in localhost | <= 500 ms on 50 requests | run benchmark on frozen build |
| Stability | Fault-free scheduler cycles, duplicate logical notices | >=99/100 cycles, zero duplicate notices for same event revision | repeated controlled clock tests |
| Capacity | 3 authenticated users with isolated plans | all 3 receive only their own data | integration simulation |
| Delivery | Physical device receipt within 2 minutes under test conditions | proposed, not yet established | actual iOS/Android test |
Human usability: observe at least five students performing filter, add event, set both reminder offsets and locate official source. Record unassisted task completion. Do not present browser automation as real student evidence.

## Deployment
Dockerfile and compose.product.yml package API, Node and ONE worker. Create .env first, use a durable /data volume and stable VAPID key outside source control, set a real SMTP provider; do not expose MailHog. Use a single always-on deployment behind HTTPS; set COOKIE_SECURE=1 and PUBLIC_ORIGIN to the exact public URL. Mount the private key as a secret file readable by uid 10001. Admin provisioning: docker compose -f compose.product.yml exec guide python -m scripts.create_product_admin --email YOUR_EMAIL --username admin. Local compose listens at localhost:8080, not public. Production requires hosting/domain/TLS configuration and backup; no hosting service was provisioned by this change. Refer to WEEK1_PRODUCT_SETUP.md for physical phone procedure.

## Added historical sources (2026)
- https://tuyensinh.hcmus.edu.vn/2026-thong-bao-mo-cong-nop-ho-so-minh-chung/
- https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-2/
- https://tuyensinh.hcmus.edu.vn/2026-thong-bao-thoi-gian-cong-bo-ket-qua-va-thong-tin-lien-quan-den-nhap-hoc/
