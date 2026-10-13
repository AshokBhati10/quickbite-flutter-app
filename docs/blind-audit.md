# Blind audit (assignment §18 rubric, from assignment + repo + live runs)

Audited 2026-10-13 against a running Compose stack and the executed suites.

## Rubric

| Criterion | Weight | Status | Evidence |
| --- | --- | --- | --- |
| FastAPI/domain correctness | 15% | pass | 52 backend tests green; live 202/history/summary checks |
| Flutter functionality and usability | 20% | pass (iOS pending) | analyze clean, 8 unit/widget tests, emulator integration pass, web+phone screenshots, APK built |
| RabbitMQ and workers | 15% | pass | `order.#` routing test, live happy path, backlog drain |
| Reliability and data integrity | 25% | pass | outbox/confirms/mandatory+returns, ack-after-commit, bounded retries, quarantine, dedupe; live kill/broker-stop/fail-twice/always-fail demos |
| Testing and measured scaling | 15% | pass | backend + Flutter suites, 5x100-order runs 1v3 workers with honest analysis |
| Packaging, documentation, demo | 10% | pass | README, contract, events, diagram, report, demo script, openapi.json, compose scaling |

## Verified live (this session)

- Happy path: 202 → DRIVER_ASSIGNED ~4 s, history v1..4, 4 notifications.
- Fail-twice: terminal in ~18 s (≈2 s/10 s delays), one payment, jobs done.
- Always-fail: PAYMENT_FAILED at ~46 s (≈2+10+30 s), 1 quarantine record,
  0 payments, retries targeted at payment.queue only.
- SIGKILL worker → restart healthy; broker stop → 202 into outbox, readiness
  showed broker down, DRIVER_ASSIGNED after restart; notification backlog
  drained with no duplicates.
- Load: 5×100 orders (1 and 3 workers); warm acceptance p95 221–321 ms
  (one cold-start burst hit 1783 ms); 3-worker drain 9 s; per-worker payment
  counts 371/60/72; zero duplicate effects; zero backlog after each run.
- Security: customer→admin 403, CORS explicit origins only, Location
  exposed, no secrets/keys committed (grep scan clean).

## Known limitations (reported, not claimed)

- iOS simulator/device execution: pending, no Mac (build plan in README).
- Web deep-link reload serves the app shell and lands on home; in-app
  named routes work, order reachable via history.
- Image tags float patches (`16-alpine`, `4-management-alpine`,
  `1.27-alpine`, `3.12-slim-bookworm`); Python/Dart deps are lock-pinned.
- Single uvicorn worker; pool_pre_ping off (documented await_only issue).
- At-least-once delivery, simulated payment/restaurant/driver, single-node
  broker with persistent volume.

## Bugs found and fixed during verification

1. aio-pika 9.4.x incompatible with RabbitMQ 4 → 9.5.8 + aiormq 6.9.4.
2. RabbitMQ 4 forbids transient non-exclusive queues → exclusive test probes.
3. Checkout FK flush ordering → explicit parent flush in acceptance txn.
4. Post-commit ORM attribute access → stash primitives before commit.
5. aio-pika confirms default-on, `confirm_select` absent → removed; unroutable
   detection via `on_return_raises` + PublishError.
6. Retry outbox rows collided on publication identity → `attempt` column in
   identity (migration 0002).
7. Cross-test engine/loop reuse → per-test engine disposal, lazy factory init.

No optional §19 extensions were added.
