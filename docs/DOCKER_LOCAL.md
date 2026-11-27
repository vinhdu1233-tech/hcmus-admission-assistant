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
The Docker local default is AI_PROVIDER=none (verified retrieval remains available; no paid API). For a supported remote provider, set DOCKER_AI_PROVIDER=gemini or openai and provide the corresponding key in .env. Recreate the service with up -d. The current Ollama client is local-host dependent; a host Ollama instance is not automatically reachable from a container. Do not assume the existing local Ollama setup works unchanged.

## Stop, restart, update
    docker compose -f compose.product.yml stop
    docker compose -f compose.product.yml start
    docker compose -f compose.product.yml down
    git pull --ff-only
    docker compose -f compose.product.yml up -d --build

Do not use down -v unless intentionally deleting all account, calendar, reminder and key data.

## Physical phone
Localhost on the Mac is not localhost on an iPhone. The local Compose binds to loopback on purpose and is not a public deployment. Actual mobile Web Push requires a reachable HTTPS origin, a stable production VAPID key and subject, a continuously running worker and device permission (iOS 16.4+ Home Screen web app). Do not expose MailHog or this development configuration over a public tunnel. A production Compose/service configuration must set Secure cookies, real SMTP, exact PUBLIC_ORIGIN and persistent private secrets. Real delivery still needs a physical-device test.
