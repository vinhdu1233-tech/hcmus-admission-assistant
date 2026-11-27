# HCMUS Guide — Week 1 product setup and acceptance
Branch: feat/week1-auth-calendar-monitoring. The existing F1/F2/F3 source data, intent router, retrieval and checklist remain intact. This extends the prototype, not the university's official admissions services.

## 1. Architecture and scope

Browser -> Node same-origin proxy -> FastAPI -> existing admissions SQLite + independent product SQLite. The new store is a sibling product.sqlite3 by default. Set HCMUS_PRODUCT_DB_PATH to a persistent mounted path in deployment. Do not discard either database. All user records and tokens are isolated from the admissions dataset. The periodic worker is a separate persistent process; run exactly one instance for this prototype.

- Student registration: email verification with 6-digit, single-use OTP, ten-minute expiry, cooldown 60 seconds and five attempts; student role is server assigned.
- Password: minimum seven characters with uppercase, a digit and a printable special character; no whitespace; maximum 72 UTF-8 bytes (bcrypt limit). Use longer passwords in practice. bcrypt cost 12. No plaintext password stored.
- Login: after four consecutive incorrect passwords, lock for 15 minutes and revoke sessions. If four more consecutive wrong passwords occur after the temporary lock expires, permanent lock until an authorized Admin unlocks. Successful login resets consecutive errors but not the previous lock strike. Admin unlock resets both. Password reset never bypasses either lock. Admin accounts are operator-provisioned, not selectable at sign-up.
- Auth cookies: random opaque token, SHA-256 stored in DB, HttpOnly, SameSite=Strict, expires after 8 hours. Enable Secure on HTTPS deployment. Clear previous chat context cookie on login/logout/reset. Guest F1 remains available by design, matching the earlier SLA/SLO.
- Admin dashboard: server-side authorization; question log with username, timestamp, intent, status, latency and full question detail, chronological sort and inclusive calendar-date filters, pagination, intent counts; account unlock; official calendar/source review. Only signed-in questions are logged; visible notice before chat/registration, obvious credential-bearing inputs redacted; retention 30 days (worker cleanup, also on writes). Not suitable for real student personal data until privacy review.
- Calendar: month grid, Vietnam time (UTC+7), filters year and method (1a/1b/2), historical 2026 dates clearly marked, no invented 2027 dates. Create/edit/delete private events, separate start/end reminders at 7, 4, 1 or 0 days; method-follow updates. Official seed entries are a deliberately limited example, not a complete admission timetable.
- Source monitoring: default 24 hours, adjustable in MONITOR_INTERVAL_HOURS (minimum 1 hour). Monitor allowlisted HTTPS HCMUS admissions pages, store snapshots, compare normalized content, detect changes, record before/after diff, report failures and preserve last successful snapshot. A changed web page is not automatically a verified deadline. Admin adds official sources, compares notices and updates/approves calendar events. Updates recalculate future reminder times; users following the method receive change notifications. No unsupported-year guessing.
- Reminder worker: checks due times every 30 seconds between cycles; creates in-app notices and push delivery records, retries failures, removes stale subscriptions, avoids duplicate notices on normal cycles. Missed reminders older than 24 hours are not sent; server must remain running. Do not claim exact delivery timing, zero duplicates across crashes, uptime or real-phone delivery without tests.
- Web Push: opt-in, PWA manifest, service worker, VAPID and browser subscription. On supported iPhone/iPad (iOS/iPadOS 16.4+) add web app to Home Screen and open it there. Android/desktop use compatible browser. HTTPS required except localhost for development. No SMS implemented. No private data offline cache.
- F2 advanced AI expansion is deliberately deferred to members. F3 remains a personal checklist; real application submission is not implemented or represented as official.

## 2. Local setup on Mac

From repository root, use Python 3.13, Node 22, and Docker Desktop for the local SMTP catcher.

    git fetch origin
    git switch feat/week1-auth-calendar-monitoring
    python3.13 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements-backend-dev.txt

If you do not already have .env, copy .env.example to .env (do not overwrite existing local configuration). Generate a random OTP secret:

    python -c "import secrets; print(secrets.token_hex(32))"

Paste it into HCMUS_OTP_SECRET in .env. For local email:

    docker compose -f compose.mailhog.yml up -d

MailHog inbox: http://127.0.0.1:8025 ; SMTP: 127.0.0.1:1025. MailHog does not deliver real external email and must never be publicly exposed. For a real mail provider use SMTP_MODE=starttls or ssl with appropriate SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and verified SMTP_FROM. Do not commit secrets.

Initialize and pre-provision a real local admin (enter password when prompted; choose your own address and username; no default account/password is committed):

    python -m src.database.db
    python -m scripts.create_product_admin --email admin@example.test --username admin

Terminal A:

    source .venv/bin/activate
    python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000

Terminal B:

    CHAT_MODE=api PORT=5501 API_ORIGIN=http://127.0.0.1:8000 node ui/server.mjs

Terminal C:

    source .venv/bin/activate
    python -m src.product_worker

Web: http://127.0.0.1:5501/ ; calendar: http://127.0.0.1:5501/portal.html#calendar ; account: http://127.0.0.1:5501/portal.html#account ; admin login automatically opens Dashboard. A locked final admin can be recovered by an authorized operator with local database access using python -m scripts.create_product_admin --recover-admin ID (only admin rows allowed). No public recovery endpoint.

One-cycle monitor/worker (without external fetching):

    python -m src.product_worker --once --skip-monitor

## 3. Real phone notifications

Generate one stable VAPID pair locally:

    python -m scripts.generate_vapid_keys

Set the printed VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY values in .env, plus VAPID_SUBJECT=mailto:operator-email. Keep private PEM outside the repository; preserve the same keys across restarts. Restart API and worker. Deploy Node behind HTTPS, keep the FastAPI upstream internal, persist both SQLite databases, run one worker continuously, set COOKIE_SECURE=1 on API and Node and set PUBLIC_ORIGIN to the exact public HTTPS URL in the Node environment. Configure real SMTP if email must arrive in users' actual inboxes.

On the phone, open the HTTPS URL, add to Home Screen if using iOS, open the installed app, sign in, open Calendar and tap Bật thông báo. Create a personal event a few minutes in the future (select both start and end as desired) and select Đúng thời điểm. Lock the phone and verify receipt. The phone may delay or suppress notifications; Web Push is best effort. Logout removes the current device subscription when available, for privacy on shared devices. If only the app is closed, notifications can still be delivered.

Important: monitor and notifications do not run on GitHub after the CI job ends. CI exercises code; it is not a continuously running deployment.

## 4. Acceptance and reproducible tests

    AI_PROVIDER=none python -m pytest -q tests
    node --test tests/test_conversation_proxy.mjs tests/test_planner_methods.mjs tests/test_web_product.mjs

For SMTP integration, start MailHog and run RUN_MAILHOG_TEST=1 python -m pytest -q tests/test_product_mailhog.py. The dedicated product-week1 GitHub Actions workflow also starts MailHog and runs actual Chrome through the live Node proxy, FastAPI and SQLite, capturing browser screenshots and results. It tests password/OTP flows, the two lock stages (time advanced in a test DB rather than waiting 15 minutes), admin RBAC, question logging, ownership of personal calendars, independent start/end offsets, deduplication, monitoring changes, and notification queue behavior. Mock Web Push transport does not establish real phone delivery.

Manual release checks still required: real SMTP delivery (if using external provider), iOS/Android physical-device delivery, public HTTPS/worker deployment, ongoing source fetch verification, and review of admissions dates and privacy policy. The previous F1 SLO results were obtained on a different frozen build; rerun benchmarks on the final integrated build before reporting new compliance numbers.

## 5. Official seed source references
- 1a online submission: https://tuyensinh.hcmus.edu.vn/2026-thong-bao-mo-cong-dang-ky-phuong-thuc-1a/
- 1b online submission: https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-1b/
- 2 evidence extension (limited categories): https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-gia-han-nop-ho-so-minh-chung/
- 2 preferences: https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-2/
- Platform requirements: https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/
