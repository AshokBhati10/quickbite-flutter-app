#!/bin/sh
# Kill a worker mid-processing and recover: no lost/repeated effects.
# Usage: sh scripts/demo_kill_recovery.sh [service]
# Default service: payment-worker.
set -eu
SERVICE="${1:-payment-worker}"
CID="$(docker compose ps -q "$SERVICE")"
echo "killing $SERVICE ($CID) mid-processing..."
docker compose kill -s SIGKILL "$SERVICE"
sleep 2
docker compose up -d "$SERVICE"
echo "restarted; verify uniqueness:"
echo "  .venv/bin/python scripts/inspect_backlog.py"
echo "  SELECT order_id, COUNT(*) FROM simulated_payments GROUP BY order_id HAVING COUNT(*) > 1;"
