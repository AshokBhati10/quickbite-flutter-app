# QuickBite Project Plan

Source of truth: `QuickBite - Revised Full-Stack Assignment.md` (section numbers `§` below refer to it). Nothing outside the assignment is added. Optional extensions (§19) are out of scope.

## 1. Goal

A Flutter client (web, Android, iOS) talking only to a FastAPI service. Orders are processed asynchronously through RabbitMQ by four independent workers, with a transactional outbox, idempotency, bounded retries, and quarantine. PostgreSQL is the source of truth.

## 2. Tooling (all free / open source)

| Purpose | Tool |
| --- | --- |
| Backend | Python (supported release, e.g. 3.12), FastAPI, Pydantic, SQLAlchemy, Alembic, aio-pika, uvicorn |
| Auth | passlib[bcrypt] or argon2-cffi; PyJWT |
| DB | PostgreSQL (pinned image tag) |
| Broker | RabbitMQ with management plugin (pinned image tag) |
| Frontend | Flutter stable + Dart; `http` or `dio`; Riverpod (documented choice); `flutter_secure_storage` (mobile only, behind an adapter); `shared_preferences` (cart draft, pending checkout key) |
| Containers | Docker, Docker Compose, nginx (serves Flutter web, SPA fallback) |
| Backend tests | pytest, pytest-asyncio, httpx, real Postgres + RabbitMQ via Compose (testcontainers optional) |
| Frontend tests | flutter_test, integration_test |
| Load test | Python script (httpx/asyncio) or Locust (free) |
| Platforms | Chrome; Android SDK emulator (free); iOS simulator needs macOS+Xcode (free but requires Mac; if unavailable, label iOS validation pending per §13) |
| Docs | Markdown, Mermaid diagrams; OpenAPI exported from FastAPI |

Pin all image tags and dependencies; commit lockfiles (`requirements.lock`/`uv.lock`, `pubspec.lock`); record exact versions in README (§4).

## 3. Repository layout (§13)

```
backend/
  app/api/        routes, auth, schemas, error envelope, CORS
  app/domain/     models, state machine, services, config
  app/messaging/  topology, envelopes, publisher, consumer base
  workers/        payment, restaurant, delivery, notification, outbox_dispatcher, retry_scheduler
  migrations/     Alembic
  tests/
frontend/         lib/ test/ integration_test/ android/ ios/ web/
infra/            Dockerfiles, nginx.conf, rabbitmq definitions
scripts/          seed, load, failure, duplicate/recovery demos
docs/             contract, architecture, evidence, report
compose.yaml
.env.example
README.md
```

## 4. Architecture summary (§3, §9, §10)

- Flutter -> FastAPI (REST only; polling). No broker/DB credentials in client.
- API commits order + history + idempotency record + outbox event in one transaction, returns 202.
- Outbox dispatcher: claims rows with `FOR UPDATE SKIP LOCKED`, publishes with publisher confirms and `mandatory=True`, marks sent only after confirm and no unroutable return.
- Exchange `quickbite.orders` (durable topic). Queues (durable, non-exclusive, not auto-delete):
  - `payment.queue` <- `order.created`
  - `restaurant.queue` <- `order.paid`
  - `delivery.queue` <- `order.confirmed`
  - `notification.queue` <- `order.#`
- `quickbite.dead` (durable direct) -> `orders.dead-letter.queue`, routing key `failed`.
- Retry scheduler turns due `retry_jobs` into outbox rows published to the default exchange with the failing consumer's queue name as routing key.
- Topology declared before dispatching (by a deliberate init step and idempotently by dispatcher/workers).

## 5. Domain and data model (§6)

Tables: users, restaurants, menu_items, orders, order_items, order_status_history, simulated_payments, driver_assignments (plus seeded drivers), notifications, processed_events, outbox_events, retry_jobs, quarantine_records, idempotency_keys (required by §7 for stored response/hash).

Key constraints:
- `idempotency_keys`: unique (user_id, key); stores canonical request hash, response body, order_id.
- `processed_events`: unique (consumer_name, event_id).
- `simulated_payments`: unique order_id. `driver_assignments`: unique order_id.
- `notifications`: unique (customer_id, event_id).
- `order_status_history`: unique (order_id, order_version).
- `outbox_events`: unique publication identity.
- `retry_jobs`: unique (consumer_name, event_id, attempt).
- Money: integer minor units + currency (INR). Timestamps UTC timezone-aware.

State machine: PENDING->PAID->CONFIRMED->DRIVER_ASSIGNED; PENDING->PAYMENT_FAILED; PAID->FAILED; CONFIRMED->FAILED. Transitions via row lock (`SELECT ... FOR UPDATE`) plus version check. No backward moves.

Limits (documented): max 20 distinct items, quantity 1..20, address length bounds.

## 6. API (§7, §8)

Endpoints exactly as §7 table under `/api/v1`, plus `/health/live`, `/health/ready` (checks DB and broker with bounded timeouts; 503 if required dependency down; documents that broker-down still accepts orders via outbox, so readiness semantic is documented explicitly).

Cross-cutting: `page`/`page_size` (max 100), list shape `{items,page,page_size,total}`; error envelope `{code,message,details,request_id}` including validation errors; status codes 401/403/404/409/422; request-id middleware; CORS with explicit origins; JWT expiring tokens; password hashing; no logging of tokens/passwords/full addresses; startup config validation; OpenAPI exported to `docs/openapi.json`.

## 7. Events and workers (§9-§12)

- Envelope fields: event_id, schema_version, event_type, order_id, order_version, occurred_at, correlation_id, causation_id, data. AMQP `message_id = event_id`, content type JSON, persistent.
- Consumer sequence: validate -> lock -> processed_events check -> state/version check -> apply transition + effect rows + outgoing outbox events -> commit -> ack. Duplicate: ack with no effect. Stale no-op: mark processed. Unexpected prerequisite: bounded deferred retry or quarantine.
- Retry policy default: 1 attempt + 3 retries at ~2s, 10s, 30s (configurable), then quarantine. Permanent declines/malformed skip retries.
- On transient failure: rollback; in one transaction insert retry_job + scheduled outbox row; then ack. If that fails, do not ack; back off and reconnect.
- On exhaustion: transaction writes quarantine_record + outbox to `quickbite.dead`; payment -> PAYMENT_FAILED + `order.payment.failed`; restaurant/delivery -> FAILED + `order.failed`; notification -> keep order status, record notification failure. Ack after commit.
- Manual acks, finite prefetch, reconnect backoff, graceful shutdown on SIGTERM.
- Deterministic demo controls (config/env or protected scripts only, never checkout fields): payment succeed / fail-twice-then-succeed / always-fail / crash at checkpoint; restaurant failure; delivery failure; notification failure.
- Structured JSON logs: service, request/correlation ID, order ID, event ID, attempt, transition, elapsed, result.

## 8. Flutter app (§5)

Screens: Sign-in; Restaurant list; Menu; Cart + checkout; Order acknowledgement; Order details (timeline, status, driver, notifications, failure explanation); Paginated order history; Admin order overview (status filters, pagination).

Architecture: centralized API client, typed models, Riverpod providers, reusable widgets; UI/state/API separation.

Behaviors: explicit loading/empty/success/validation/auth-expired/offline states; persisted pending checkout key + request, disabled submit while active, timeout -> safe retry with same key; local cart draft; polling ~2s on order details with stop on terminal/background/dispose, backoff on failure, refresh on resume; responsive phone/desktop; semantic labels, contrast, text scaling, keyboard navigation; token in memory on web and secure storage on mobile via conditional-import adapters; `--dart-define=API_BASE_URL`; notification failure not shown as payment failure.

## 9. Packaging (§13)

Compose services: postgres, rabbitmq (management), migrate (one-shot), seed (one-shot), api, payment-worker, restaurant-worker, delivery-worker, notification-worker, outbox-dispatcher, retry-scheduler, web (nginx). Healthchecks, named volumes, no `container_name`, no fixed worker host ports, internal DB/broker ports private (management UI bound to 127.0.0.1). `.env.example` with placeholders only.

## 10. Testing strategy (§14)

Every phase ends with unit tests then integration tests (real Postgres/RabbitMQ for backend). Acceptance matrix from §14 is mapped to phases in the task file. Final load/scaling: >=100 orders, 1 vs 3 payment workers, >=2 repeats each, report machine, concurrency, p50/p95, total time, orders/s, backlog.

## 11. Deliverables (§16) and demo (§17)

Repo with lockfiles; README (prereqs, commands, accounts, URLs, per-platform API addresses, troubleshooting); API + event docs; architecture diagram; web build, debug APK, iOS simulator evidence (or labeled pending); test results and screenshots; engineering report; demo script covering the 10 steps in §17.

## 12. Milestone mapping (§15)

| Milestone | Phases |
| --- | --- |
| 1 | 0, 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 5 |
| 6 | 6 |
| 7 | 7, 8 |

## 13. Risks

- No Mac: iOS validated as pending, documented honestly (§13).
- Local hardware may miss p95 < 500 ms: report honestly with analysis (§14).
- Flutter web must not import mobile-only plugins: use conditional-import adapters.
