# QuickBite — full-stack food delivery order processing

Flutter client (web, Android, iOS) + FastAPI service + RabbitMQ workers +
PostgreSQL source of truth, with transactional outbox, idempotent checkout,
bounded retries, and quarantine.

## Prerequisites (exact versions)

| Tool | Version |
| --- | --- |
| Python | 3.12.3 |
| Docker / Compose | 29.6.2 / v2.40.3 |
| Postgres image | `postgres:16-alpine` |
| RabbitMQ image | `rabbitmq:4-management-alpine` |
| Python base image | `python:3.12-slim-bookworm` |
| nginx image | `nginx:1.27-alpine` |
| Flutter | 3.47.7 stable, Dart 3.13.5 (user-local SDK at `~/flutter-sdk/flutter`) |
| Java (Android builds) | Temurin 17 (`/usr/lib/jvm/temurin-17-jdk-amd64`) |

Python deps are pinned in `backend/requirements.txt` with the frozen
`backend/requirements.lock`. Notable: `aio-pika==9.5.*` (9.4.x cannot talk
to RabbitMQ 4 — see troubleshooting).

Current environment status (verified 2026-10-13): Python, Docker/Compose,
Android SDK + `Medium_Phone` AVD, Chrome, and a user-local Flutter 3.47.7 SDK
(`~/flutter-sdk/flutter`, not on PATH by default; no system-wide install was
performed). Web build, debug APK, widget/unit tests, and Android-emulator
integration flow are verified — see `docs/evidence/`. iOS execution remains
pending (no Mac).

## Clean-install sequence

```sh
cp .env.example .env
# edit .env: set JWT_SECRET to a long random value
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

docker compose up -d postgres rabbitmq
docker compose up migrate seed init-topology
docker compose up -d api outbox-dispatcher retry-scheduler \
  payment-worker restaurant-worker delivery-worker notification-worker

# backend tests (need services above healthy)
.venv/bin/python -m pytest backend/tests/unit -q
.venv/bin/python -m pytest backend/tests/integration -q
```

Test output for each phase gate goes to `docs/evidence/phase-N/`.

## Test accounts (seeded)

- customer: `customer@quickbite.test` / `Password123!`
- admin: `admin@quickbite.test` / `Password123!`

## URLs

- API: `http://localhost:8000`, docs at `/docs`
- RabbitMQ management: `http://localhost:15672` (quickbite/quickbite)
- Web app (after `flutter build web`): `http://localhost:8080` via Compose `web`

## Per-platform API addresses

Prefix every Flutter command with the SDK location, e.g.
`export PATH="$HOME/flutter-sdk/flutter/bin:$PATH"`.

```sh
# desktop browser
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
# Android emulator (host loopback; verified with Medium_Phone AVD)
flutter run -d <android-device> --dart-define=API_BASE_URL=http://10.0.2.2:8000
# iOS simulator (host loopback; needs macOS)
flutter run -d "iPhone 16" --dart-define=API_BASE_URL=http://localhost:8000
```

Generate platform runners once (requires Flutter SDK):

```sh
cd frontend && flutter create --org com.quickbite --project-name quickbite .
```

Builds: `flutter build web ...`, `flutter build apk ...`, iOS needs macOS +
Xcode — without a Mac, iOS execution stays **pending** with this build plan.

## Flutter tests

```sh
cd frontend
flutter test            # unit + widget
flutter analyze         # must be clean
flutter test integration_test/app_test.dart \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

## Load / scaling

```sh
.venv/bin/python scripts/load.py --orders 100 --concurrency 10
docker compose up -d --scale payment-worker=3   # repeat each setup >=2x
```

## Failure demos

```sh
sh scripts/demo_fail_twice.sh          # fail-twice-then-succeed (~2s/10s)
sh scripts/demo_always_fail.sh         # terminal PAYMENT_FAILED + quarantine
sh scripts/demo_kill_recovery.sh       # kill -9 a worker, restart, verify
sh scripts/demo_broker_stop.sh         # accept into outbox while broker down
sh scripts/demo_notification_backlog.sh
.venv/bin/python scripts/inspect_backlog.py [--order ORDER_ID]
```

Failure injection lives only in env/protected scripts (`PAYMENT_MODE`,
`RESTAURANT_MODE`, `DELIVERY_MODE`, `NOTIFICATION_MODE`); checkout has no
such fields.

## Retry policy and readiness

Default 1 attempt + 3 retries at ~2 s, 10 s, 30 s, then quarantine
(`RETRY_MAX_RETRIES`, `RETRY_DELAYS_S`). `/health/live` is process liveness;
`/health/ready` returns 503 when PostgreSQL is down. A down broker is
reported but still accepts orders: committed PENDING orders wait in the
outbox for messaging recovery (see `docs/contract.md`).

## Troubleshooting

- `aio-pika` 9.4.x against RabbitMQ 4 fails with
  `transient_nonexcl_queues ... INTERNAL_ERROR`: use `aio-pika==9.5.*`.
- Never run migrations/seeding from every worker: use the one-shot
  `migrate`, `seed`, and `init-topology` Compose services.
- No `container_name` or fixed worker host ports: services scale with
  `docker compose up -d --scale payment-worker=3`.
- Other containers on this machine (research-*, ollama, qdrant, …) are
  unrelated: do not stop or delete them.
