# Phase 0 evidence

## Environment (verified 2026-10-13)

- Python 3.12.3 (venv `.venv/`), Docker 29.6.2, Compose v2.40.3
- Postgres 16.15 (`postgres:16-alpine`), RabbitMQ 4 (`rabbitmq:4-management-alpine`),
  both `healthy` — see `test-output.txt`
- Android SDK + adb 37 present, AVD `Medium_Phone` defined, Chrome present
- Flutter SDK: NOT FOUND on PATH (no system-wide install performed)

## Unit tests: 30 passed (config, state machine, money, auth, envelopes, error shape)

## Integration: postgres + RabbitMQ reachable, probe queue declared ok

## Real findings fixed in this phase

1. `aio-pika 9.4.x` cannot talk to RabbitMQ 4 → upgraded to 9.5.8 with
   `aiormq 6.9.4`; `backend/requirements.lock` regenerated.
2. RabbitMQ 4 forbids transient non-exclusive queues: test probe queues use
   `exclusive=True`. All topology queues were already durable.
