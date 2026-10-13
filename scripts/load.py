"""Load test: >=100 orders, fixed successful simulation, measured latency.

Run:  .venv/bin/python scripts/load.py --orders 100 --concurrency 10
Reports machine/resources, concurrency, order count, API p50/p95, total
processing time, orders/s. Per-stage delays come from server config.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx  # noqa: E402

BASE = os.environ.get("LOAD_BASE_URL", "http://localhost:8000")
EMAIL = os.environ.get("LOAD_EMAIL", "customer@quickbite.test")
PASSWORD = os.environ.get("LOAD_PASSWORD", "Password123!")


async def login(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def place_one(
    client: httpx.AsyncClient, token: str, sem: asyncio.Semaphore, i: int
) -> float:
    body = {
        "restaurant_id": "rest_spice",
        "delivery_address": f"{i} Lake Road, Bengaluru",
        "items": [{"menu_item_id": "item_biryani", "quantity": 1}],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    async with sem:
        started = time.perf_counter()
        resp = await client.post(f"{BASE}/api/v1/orders", json=body, headers=headers)
        elapsed = (time.perf_counter() - started) * 1000
    assert resp.status_code == 202, resp.text
    return elapsed


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=30) as client:
        token = await login(client)
        sem = asyncio.Semaphore(args.concurrency)
        started = time.perf_counter()
        latencies = await asyncio.gather(
            *[place_one(client, token, sem, i) for i in range(args.orders)]
        )
        total_s = time.perf_counter() - started

    lat = sorted(latencies)
    p50 = statistics.median(lat)
    p95 = lat[int(0.95 * len(lat)) - 1]
    report = {
        "machine": platform.platform(),
        "cpu_count": os.cpu_count(),
        "concurrency": args.concurrency,
        "orders": args.orders,
        "api_p50_ms": round(p50, 1),
        "api_p95_ms": round(p95, 1),
        "total_time_s": round(total_s, 1),
        "orders_per_s": round(args.orders / total_s, 2),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
