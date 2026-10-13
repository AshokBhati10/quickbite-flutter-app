**Important Environment Constraints:** Do not modify the remote machine's system configuration. Do not install, upgrade, or uninstall system-wide software or modify system Python. Verify existing tools and versions only. Use a project-local `.venv` for all Python dependencies. Keep all project files and configurations inside the repository, and do not modify or delete unrelated Docker containers, images, volumes, or resources. If a required tool is missing, stop and ask for approval before installing anything.

# QuickBite Build Tasks (execution checklist)

Follow in order. Reference: `PROJECT_PLAN.md` and `QuickBite - Revised Full-Stack Assignment.md` (§ = section). Add nothing beyond the assignment.

**Rule for every phase:** finish tasks -> run **unit tests** -> run **integration tests** -> fix until green -> tick the phase gate -> only then start the next phase. Save test output to `docs/evidence/phase-N/`.

---

## Phase 0 - Environment and scaffolding

- [ ] 0.1 Verify existing Python, Docker + Compose, Flutter stable, and Android SDK/emulator installations. Record versions. Do not install, upgrade, or modify system-wide tools. If any required tool is missing, report it and wait for approval.
- [ ] 0.2 Create repo layout from PROJECT_PLAN §3; `git init`; `.gitignore` (env files, build output, keystores).
- [ ] 0.3 Backend: virtualenv, install FastAPI, Pydantic, SQLAlchemy, Alembic, aio-pika, uvicorn, PyJWT, password-hash lib, pytest, pytest-asyncio, httpx; generate lockfile.
- [ ] 0.4 Frontend: `flutter create` with web/android/ios; add deps; commit `pubspec.lock`.
- [ ] 0.5 `compose.yaml` with pinned postgres and rabbitmq (management) images, named volumes, healthchecks, management bound to 127.0.0.1.
- [ ] 0.6 `.env.example` (DATABASE_URL, AMQP_URL, JWT settings, CORS origins, simulated delays, demo failure controls, retry policy).
- [ ] 0.7 Config module with startup validation (fail fast on missing/invalid).

**Tests**
- [ ] Unit: config validation (valid, missing, malformed values).
- [ ] Integration: `docker compose up postgres rabbitmq` becomes healthy; a script connects to both.
- [ ] Gate 0 passed.

## Phase 1 - Schema, state machine, auth, seed (Milestone 1)

- [ ] 1.1 SQLAlchemy models for all tables in PROJECT_PLAN §5 with all unique constraints.
- [ ] 1.2 Alembic initial migration; migration run as a deliberate one-shot step.
- [ ] 1.3 State machine module: allowed transitions, terminal states, version-checked apply function (row lock).
- [ ] 1.4 Money helpers (integer minor units, currency).
- [ ] 1.5 Password hashing, JWT issue/verify (expiry, validated claims, server secret).
- [ ] 1.6 Seed command (repeatable): customer and admin accounts, restaurants, menu items (incl. one inactive item), second restaurant, drivers.
- [ ] 1.7 FastAPI app skeleton: request-id middleware, error envelope (incl. validation errors), CORS with explicit origins, `/health/live`, `/health/ready` (bounded timeouts).
- [ ] 1.8 `POST /auth/login`, `GET /me`, auth dependencies (401, role checks 403).
- [ ] 1.9 Structured JSON logging helper (no tokens/passwords/full addresses).
- [ ] 1.10 Flutter scaffold: folder structure, API client, `API_BASE_URL` dart-define, Riverpod setup, sign-in screen with loading / invalid-credential / network-error states, token storage adapters (memory for web, secure storage for mobile via conditional import).

**Tests**
- [ ] Unit: every valid and invalid transition; backward transition rejected; JWT expiry/tamper; hash verify; error envelope shape.
- [ ] Integration (real Postgres): migrate up/down, seed twice with no duplicates, login success/failure, `/me`, expired token -> 401, readiness 503 when DB down.
- [ ] Flutter: widget tests for sign-in states; `flutter analyze` clean.
- [ ] Gate 1 passed.

## Phase 2 - Browsing, checkout, idempotency, outbox write (Milestone 2)

- [ ] 2.1 `GET /restaurants`, `GET /restaurants/{id}/menu` with pagination (max page_size 100) and list envelope.
- [ ] 2.2 Checkout schema validation: reject inactive items, mixed restaurants, quantity outside 1..20, more than 20 distinct items, invalid address, client-supplied price/customer/total fields ignored or rejected.
- [ ] 2.3 Server-side total computation from current menu; item snapshots in order_items.
- [ ] 2.4 `POST /orders`: require Idempotency-Key; canonical request hash; single transaction writes order, initial history, idempotency record (with stored response), outbox `order.created` event; return 202 with Location.
- [ ] 2.5 Idempotency: same key+payload returns same response/Location with no new rows; different payload -> 409; concurrent identical requests -> exactly one order (unique constraint + conflict handling).
- [ ] 2.6 `GET /orders` (own, status filter, pagination), `GET /orders/{id}`, `/history`, `/notifications` (owner or admin; others get 404).
- [ ] 2.7 `GET /admin/orders` and `GET /admin/summary` (status counts, pending outbox/retry/quarantine counts, oldest pending outbox age).
- [ ] 2.8 Document limits; export `docs/openapi.json`.

**Tests**
- [ ] Unit: total calculation, validators, canonical hash, pagination bounds.
- [ ] Integration (real Postgres): invalid/mixed/inactive items leave no order/outbox rows; atomic rollback when outbox insert fails; customer cannot see another's order; customer gets 403 on admin routes; missing token 401; same-key replay; changed payload 409; 20 concurrent identical POSTs -> 1 order, 1 outbox row.
- [ ] Gate 2 passed.

## Phase 3 - Broker topology, dispatcher, workers (Milestone 3)

- [ ] 3.1 Topology module: `quickbite.orders` topic, four queues with bindings (`order.created`, `order.paid`, `order.confirmed`, `order.#`), `quickbite.dead` direct + `orders.dead-letter.queue` (key `failed`); idempotent declare; an init step runs it before dispatch.
- [ ] 3.2 Envelope builder/validator (all required fields, schema_version check, message_id = event_id, JSON, persistent).
- [ ] 3.3 Outbox dispatcher: claim with `FOR UPDATE SKIP LOCKED`/lease, publisher confirms, `mandatory=True`, handle unroutable returns, mark sent only after confirm, delayed retry on failure, reconnect with backoff, graceful shutdown.
- [ ] 3.4 Consumer base class: manual ack, finite prefetch, reconnect backoff, graceful shutdown, processing sequence per assignment §10 (validate, lock, processed_events check, state check, transition + effects + child outbox events in one transaction, commit, ack).
- [ ] 3.5 Payment worker: PENDING->PAID (simulated payment row, order-based idempotency id) or PAYMENT_FAILED + `order.payment.failed`; emits `order.paid`.
- [ ] 3.6 Restaurant worker: PAID->CONFIRMED (emits `order.confirmed`) or FAILED (`order.failed`).
- [ ] 3.7 Delivery worker: assign seeded driver; CONFIRMED->DRIVER_ASSIGNED (emits `order.driver.assigned`) or FAILED.
- [ ] 3.8 Notification worker: persist customer notification for every supported event; ignore valid future types with structured log; never changes order status.
- [ ] 3.9 Child events: causation_id = incoming event_id, correlation_id retained.
- [ ] 3.10 Simulated delays configurable per stage.
- [ ] 3.11 Compose services: migrate, seed, api, four workers, dispatcher (no fixed container names/ports).

**Tests**
- [ ] Unit: envelope validation, routing-key matching table (`order.#` matches `order.payment.failed` and `order.driver.assigned`; `order.*` would not), transition decisions per worker.
- [ ] Integration (real Postgres + RabbitMQ): happy path reaches DRIVER_ASSIGNED with exactly one payment, one assignment, one notification per event; redelivered identical event causes no repeated effects; unroutable publish (binding removed) leaves outbox row unsent; dispatcher crash after publish/before mark-sent gives duplicate that is deduplicated; two dispatcher instances never double-claim; stopped consumer's queue persists and holds messages.
- [ ] Gate 3 passed.

## Phase 4 - Retries, quarantine, failure injection (Milestone 4)

- [ ] 4.1 Retry policy config (default 1 + 3 retries, 2/10/30 s) and README note.
- [ ] 4.2 Transient failure path: rollback, then one transaction inserts retry_job (unique consumer/event/attempt) + scheduled targeted outbox row; ack only after that commit; if it fails, do not ack and back off.
- [ ] 4.3 Retry scheduler process: makes due retry_jobs eligible; dispatcher publishes via default exchange with routing key = failing queue; event_id preserved, attempt counter incremented.
- [ ] 4.4 Exhaustion path: quarantine_record + outbox to `quickbite.dead`; payment -> PAYMENT_FAILED + `order.payment.failed`; restaurant/delivery -> FAILED + `order.failed`; notification keeps order status and records notification failure; ack after commit.
- [ ] 4.5 Permanent failures and malformed/unknown-schema messages skip retries and go to quarantine; malformed without valid order ref mutates no order.
- [ ] 4.6 Deferred retry or quarantine for unexpected future-state prerequisites (out-of-order events).
- [ ] 4.7 Failure injection (env/protected scripts only): payment ok / fail-twice-then-succeed / always-fail / crash at checkpoint (before commit, after commit before ack); restaurant failure; delivery failure; notification failure. Verify checkout cannot select them.
- [ ] 4.8 Scripts in `scripts/`: run each scenario by stable order ID, inspect retry_jobs/quarantine, duplicate-delivery and kill/recover demos.
- [ ] 4.9 Quarantined envelopes retain original event, source consumer/queue, attempts, failure code, timestamps; inspectable in RabbitMQ management UI.

**Tests**
- [ ] Unit: retry delay selection, attempt counting, decision (retry vs quarantine vs permanent).
- [ ] Integration (real services): fail-twice then succeed (delays ~2s/10s observed, one payment); always-fail -> PAYMENT_FAILED, one quarantine record, one dead-letter message; restaurant/delivery terminal -> FAILED; notification failure does not alter order status and other stages finish; stop notification worker, run several orders, restart, backlog drains with no duplicate notifications; kill worker mid-processing and after-commit-before-ack, restart, no lost/repeated effects; stop RabbitMQ after accept, restart, order completes; retry failure leaves message unacked; out-of-order/duplicate events with 3 payment workers never regress state; retry goes only to the failing queue.
- [ ] Gate 4 passed.

## Phase 5 - Flutter features (Milestone 5)

- [ ] 5.1 Restaurant list + menu screens (names, price, currency, availability, empty state).
- [ ] 5.2 Cart: quantities, removal, subtotal, address field, validation, single-restaurant rule, local draft persistence.
- [ ] 5.3 Checkout: generate UUID key, persist pending key+request until outcome known, disable button while active, timeout shows retry with same key, no automatic new order.
- [ ] 5.4 Order acknowledgement screen (server ID, accepted total, status).
- [ ] 5.5 Order details: timeline from history, status, driver, notifications, readable failure explanation; notification failure not shown as payment failure.
- [ ] 5.6 Polling: ~2 s while visible; stop on terminal/dispose/background; backoff on failure; refresh on resume.
- [ ] 5.7 Order history: pagination, pull-to-refresh, navigate to details, independent refresh.
- [ ] 5.8 Admin overview: status filters, pagination, read-only.
- [ ] 5.9 Auth expiry: prompt sign-in, stop protected background requests.
- [ ] 5.10 Responsive layouts (phone and desktop, no overflow); semantics labels, contrast, keyboard navigation, text scaling.
- [ ] 5.11 Web: SPA routing with deep links; no mobile-only imports on web.
- [ ] 5.12 nginx image for built web app with SPA fallback; Compose `web` service; CORS origin configured.

**Tests**
- [ ] Unit: models JSON parsing, cart logic, polling controller (start/stop/backoff), pending-checkout persistence.
- [ ] Widget: checkout validation, double-tap prevention, timeout retry with same key, status/failure rendering, empty/error/offline/expired-auth states, overflow checks at phone and desktop sizes, large text scale.
- [ ] Integration (`integration_test` against running Compose stack): sign-in -> menu -> checkout -> tracking -> history; admin filter; customer denied admin endpoint.
- [ ] Gate 5 passed.

## Phase 6 - Full verification and platform checks (Milestone 6)

- [ ] 6.1 Run complete backend suite and map each row of §14 table to a named test; fill gaps.
- [ ] 6.2 Security/config tests: CORS allowed vs disallowed origin, no wildcard with credentials, exposed Location header, no secrets/broker/DB creds in repo or Flutter build (grep scan), no token/password/address in logs.
- [ ] 6.3 Web: browser run, deep-link reload check, network-timeout/connection-loss demo recovering with same key.
- [ ] 6.4 Android: emulator run with `API_BASE_URL=http://10.0.2.2:8000`; build debug APK; capture screenshots (phone layout).
- [ ] 6.5 iOS: on macOS run simulator and build; capture evidence. If no Mac, label iOS validation **pending** and write build plan; do not claim three-platform completion.
- [ ] 6.6 Verify failed orders readable in UI on each platform.
- [ ] 6.7 Store results/screenshots in `docs/evidence/`.

**Tests**
- [ ] Re-run all unit + integration suites (backend, Flutter) from a clean checkout and clean volumes.
- [ ] Gate 6 passed.

## Phase 7 - Load and scaling (Milestone 7)

- [ ] 7.1 Load script: >=100 orders, fixed successful simulation, documented per-stage delays, configurable concurrency.
- [ ] 7.2 Collect: machine/resources, concurrency, order count, API p50/p95, total processing time, orders/s, queue backlog samples.
- [ ] 7.3 Run 1 payment worker vs 3 (`docker compose up -d --scale payment-worker=3`), same workload, each repeated >=2 times; make payment the bottleneck (documented delay).
- [ ] 7.4 Show distribution across workers (per-worker counts from logs); confirm API latency independent of payment delay.
- [ ] 7.5 Record results honestly, including any miss of p95 < 500 ms, with analysis.

**Tests**
- [ ] Sanity: after each run all orders terminal, no duplicate payments/assignments/notifications (SQL uniqueness checks), outbox/retry backlog zero.
- [ ] Gate 7 passed.

## Phase 8 - Documentation and packaging (Milestone 7)

- [ ] 8.1 README: prerequisites, exact versions, clean-install sequence (env, build, migrate, seed, start), test accounts, URLs, per-platform API addresses (tested ones), run/build/test commands for web, Android, iOS, troubleshooting, retry policy, readiness semantics.
- [ ] 8.2 `docs/`: API contract (money units, state machine, errors, idempotency, pagination), event schema, `openapi.json`.
- [ ] 8.3 Architecture/event-flow diagram (persistence, outbox, retry scheduling, quarantine, client boundary).
- [ ] 8.4 Engineering report: retry safety, deduplication, outbox recovery, security choices, measured scaling, limitations (at-least-once, not exactly-once; payment simulation caveat; single-node broker).
- [ ] 8.5 Demo script covering all 10 steps of §17, reproducible from a clean checkout; recording or live-demo notes.
- [ ] 8.6 Web build/image, debug APK; verify no populated secret files are present.

**Tests**
- [ ] Follow README literally on a clean clone with fresh volumes; every command works; full suites pass.
- [ ] Gate 8 passed.

---

## Phase 9 - Blind audit

Performed last, as a fresh reviewer who has **not** relied on the builder's notes: use only the assignment file and the repository as submitted.

- [ ] 9.1 Re-read the assignment from scratch; derive a checklist directly from §5-§14, §16, §17 without consulting PROJECT_PLAN.md or this file.
- [ ] 9.2 From a clean clone and fresh volumes, follow only the README. Record every place it fails or is ambiguous.
- [ ] 9.3 Verify each checklist item against code and running system (not against claims in docs): topology (`order.#`), outbox confirms + mandatory, ack-after-commit, unique constraints, retry policy, quarantine contents, state machine, server-side pricing, idempotency, access control, CORS, secrets scan, pinned versions/lockfiles, Compose scaling (no container_name/fixed ports).
- [ ] 9.4 Independently re-run: happy path, idempotent replay, notification-stopped scenario, fail-twice and always-fail, worker kill, broker stop, 1 vs 3 workers (at least a reduced run), admin vs customer access.
- [ ] 9.5 Check evidence: screenshots/test logs exist for each platform; unverified items (e.g. iOS) are explicitly marked pending, not claimed.
- [ ] 9.6 Check that nothing outside assignment scope (optional extensions) was added or presented as required.
- [ ] 9.7 Score against the §18 rubric per criterion; write `docs/blind-audit.md` with pass/fail per item, findings, severity, and remediation.
- [ ] 9.8 Fix all findings, re-run affected tests, and re-audit the fixed items until no required item fails.
- [ ] Gate 9 passed -> project complete.
