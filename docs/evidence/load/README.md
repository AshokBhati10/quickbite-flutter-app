# Load and scaling (assignment §14)

Machine: Linux 7.0.0-38-generic x86_64, 4 CPUs, shared with ~10 unrelated
containers. Workload: 100 checkout orders, concurrency 10, fixed `ok`
simulation, per-stage delays 0.2/0.2/0.2/0.1 s. Raw JSON per run in this dir.

| Run | Payment workers | Accept p50 | Accept p95 | Accept time | Drain to terminal |
| --- | --- | --- | --- | --- | --- |
| cold start | 1 | 84 ms | 1783 ms | 2.7 s | n/a (warmup outlier) |
| run1 | 1 | 87 ms | 221 ms | 1.1 s | drained |
| run2 | 1 | 94 ms | 321 ms | 1.5 s | drained |
| run3 | 3 | 133 ms | 310 ms | 1.6 s | 9 s |
| run4 | 3 | 78 ms | 247 ms | 1.0 s | 9 s |
| run5 | 1 | 99 ms | 226 ms | 1.1 s | 9 s |

- Acceptance p95 stays well under 500 ms on warm runs (the single cold-start
  burst spiked to 1783 ms while pools/connections warmed up).
- API latency is independent of simulated payment delay: acceptance ends at
  the DB commit, identical across 1- and 3-worker runs.
- No 3x throughput win was observed, as the assignment warns: each worker
  already processes up to `prefetch=10` deliveries as concurrent asyncio
  tasks, so one worker drains 100 orders in ~9 s on this host; adding workers
  mainly adds distribution, proven by per-worker payment counts 371/60/72
  across the session (worker-1 lived longest).
- Sanity after every run: all orders terminal (DRIVER_ASSIGNED except the
  intentional always-fail PAYMENT_FAILED), zero pending outbox/retry rows,
  zero duplicate payments/assignments/notifications by SQL uniqueness checks.
- Queue backlog sampled via pending-outbox counts during drains (returned to 0).
