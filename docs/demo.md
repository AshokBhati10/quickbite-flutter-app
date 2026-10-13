# Demo script (assignment §17, reproducible from a clean checkout)

1. `docker compose up -d postgres rabbitmq`, then `migrate seed init-topology`,
   then the api/workers/dispatcher/scheduler services (see README).
2. Sign in through Flutter (`customer@quickbite.test`) and browse the seeded menu.
3. Place an order: show rapid 202 acceptance, then PENDING → PAID → CONFIRMED →
   DRIVER_ASSIGNED, the notification feed, and history.
4. Repeat checkout with the same idempotency key: same order ID, no new effects.
5. `sh scripts/demo_notification_backlog.sh`: place several orders, show backlog
   with unaffected completion, restart, drain with no duplicates.
6. `sh scripts/demo_fail_twice.sh` then `sh scripts/demo_always_fail.sh`: show
   retry timestamps, terminal UI, and quarantine contents (`scripts/inspect_backlog.py`).
7. `sh scripts/demo_kill_recovery.sh`: kill at a transaction/ack boundary,
   recover, show uniqueness of payment/assignment/history records.
8. `sh scripts/demo_broker_stop.sh`: accept into the outbox, restart, eventual completion.
9. `scripts/load.py` with 1 vs 3 payment workers: report latency/throughput.
10. Show web, Android, (iOS if Mac) customer flow incl. narrow layout + safe
    network retry; sign in as admin for cross-customer filtering and verify a
    customer is denied the same endpoint.
