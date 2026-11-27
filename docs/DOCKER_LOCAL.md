# Chạy HCMUS Guide bằng Docker Desktop (Mac/Windows)
Local development only. MailHog intercepts mail; no external email is sent. The web/API/worker run in one container, MailHog in another. Existing admissions data is initialized by the app, product data and development keys persist in a named volume. The backend is not exposed directly.

## Start
From the repository root (macOS):
    git fetch origin
    git switch feat/week1-auth-calendar-monitoring
    git pull --ff-only
    test -f .env || cp .env.example .env
    docker compose -f compose.product.yml up -d --build
    docker compose -f compose.product.yml ps
    docker compose -f compose.product.yml logs -f guide

Open http://localhost:8080/ and http://localhost:8025/ (MailHog). Exit log follow with Ctrl+C (containers continue running). MailHog runs amd64 under emulation on Apple Silicon; Docker Desktop must support x86 emulation. SMTP uses mailhog:1025 inside Docker, not localhost. If an old MailHog instance occupies 8025, stop that instance first. Do not start the old standalone compose at the same time.

## Admin
    docker compose -f compose.product.yml exec guide python -m scripts.create_product_admin --email admin@example.test --username admin

Enter your own password twice; do not use real student data in the development service. Register a Student in the browser, get the six-digit OTP from MailHog, finish registration and log in. The Admin account is created once; repeating the command for an existing account will not silently overwrite it.

## Verify update approval
Use two browser profiles (Admin and Student). As Student follow a method. As Admin create a future test event using the supported official source form and clearly label it TEST (not official information). As Student accept its initial proposal and set both start and end reminder offsets. As Admin change the dates. The public calendar changes; personal plan stays on the old revision. Choose Defer, then Accept, and verify dates and retained offsets. To verify Reject use another test update. Old personal dates are clearly marked. Use a test DB only.

## Optional AI
The Docker local default is AI_PROVIDER=none (verified retrieval remains available; no paid API). For a supported remote provider, set DOCKER_AI_PROVIDER=gemini or openai and provide the corresponding key in .env. Recreate the service with up -d. For local Ollama inside Docker, use the optional compose.ollama.yml overlay. It shares guide's network namespace so the existing loopback-only client still works without code changes. Start and pull the model:

    docker compose -f compose.product.yml -f compose.ollama.yml up -d --build --force-recreate
    docker compose -f compose.product.yml -f compose.ollama.yml exec ollama ollama pull qwen3:4b

Use both -f arguments when stopping or updating this optional stack. Model downloads require internet and several GB of storage. Docker Desktop on macOS typically uses CPU inference; native macOS Ollama may be faster. This optional model path is not part of the standard CI smoke test. A host Ollama instance is not automatically reachable from a container.

## Stop, restart, update
    docker compose -f compose.product.yml stop
    docker compose -f compose.product.yml start
    docker compose -f compose.product.yml down
    git pull --ff-only
    docker compose -f compose.product.yml up -d --build

Do not use down -v unless intentionally deleting all account, calendar, reminder and key data.

## Physical phone
Localhost on the Mac is not localhost on an iPhone. The local Compose binds to loopback on purpose and is not a public deployment. Actual mobile Web Push requires a reachable HTTPS origin, a stable production VAPID key and subject, a continuously running worker and device permission (iOS 16.4+ Home Screen web app). Do not expose MailHog or this development configuration over a public tunnel. A production Compose/service configuration must set Secure cookies, real SMTP, exact PUBLIC_ORIGIN and persistent private secrets. Real delivery still needs a physical-device test.

## Recommended on Mac: native Ollama + Docker
Install/open native Ollama from https://ollama.com/download/mac, then run `ollama pull qwen3:4b` in the Mac terminal (not docker exec). Confirm `curl http://127.0.0.1:11434/api/tags` works. Stop the containerized Ollama using `docker compose -f compose.product.yml -f compose.ollama.yml stop ollama`, then use `docker compose -f compose.product.yml -f compose.ollama-native.yml up -d --build --remove-orphans`. Keep the named database volume. Do not combine the two Ollama overlays. The new overlay routes to the Docker Desktop host alias. Check connectivity from guide: `docker compose -f compose.product.yml -f compose.ollama-native.yml exec guide python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).read().decode())"`. Keep native Ollama running and do not expose its unauthenticated port to the public network. If host alias fails, inspect Docker Desktop networking before widening bind addresses. Native model performance and network reachability must be verified on the actual Mac. AI remains restricted to major exploration; other intents use existing rules and SQLite.

## Account workspace and DBeaver
The Docker supervisor sets REQUIRE_ACCOUNT_CHAT=1. Guest chat is rejected, each signed-in account gets server-side chat threads and messages; question_logs remains the separate 30-day Admin operational audit. Checklist is automatically saved/restored per user/year/method/path; older browser-local anonymous plans are not silently imported. Clicking calendar link saves and opens filtered calendar. Calendar candidate publication now verifies and marks processed in one transaction; rejecting leaves the official dates unchanged.
The product database is /data/product.sqlite3 inside the guide container, separate from /data/admissions.sqlite3. To inspect a consistent read-only snapshot in DBeaver, use SQLite's online backup (works with WAL; do not copy just the live .sqlite3 file). Example:

    docker compose -f compose.product.yml -f compose.ollama-native.yml exec -T guide python -c "import sqlite3; s=sqlite3.connect('/data/product.sqlite3'); d=sqlite3.connect('/tmp/product-inspect.sqlite3'); s.backup(d); d.close(); s.close()"
    docker compose -f compose.product.yml -f compose.ollama-native.yml cp guide:/tmp/product-inspect.sqlite3 ./product-inspect.sqlite3
    docker compose -f compose.product.yml -f compose.ollama-native.yml exec guide rm -f /tmp/product-inspect.sqlite3

Open product-inspect.sqlite3 in DBeaver's SQLite connection. This is a point-in-time copy, not live, and contains private account data: do not commit or share it. Passwords are bcrypt hashes; OTPs and session tokens are hashed, not plaintext. Use a disposable copy for SQL experiments. No need to expose database ports. Re-export to refresh.

## Workspace R2 troubleshooting
After pulling, run docker compose -f compose.product.yml -f compose.ollama-native.yml up -d --build --force-recreate --remove-orphans. Verify http://localhost:8080/api/config shows release workspace-r2 and version 1.1.0. If not, verify branch, project directory, container and port before testing. Use the same hostname localhost (not alternating 127.0.0.1) for auth cookies. New or changed official milestones appear in every Student's in-app inbox; targeted followers / existing plans receive personal proposals and eligible Web Push. Unchanged edits and rejected proposals do not create notices. This is prospective (no retroactive announcements). The Dashboard sidebar separates six workspaces. Checklist GET now verifies account_id, and same-origin account changes clear/reload other tabs.
