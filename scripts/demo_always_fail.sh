#!/bin/sh
# Always-fail: payment reaches PAYMENT_FAILED, one quarantine record,
# one dead-letter message. Usage: sh scripts/demo_always_fail.sh
set -eu
export PAYMENT_MODE=always-fail
docker compose up -d payment-worker
echo "payment worker set to always-fail; place an order, then watch:"
echo "  .venv/bin/python scripts/inspect_backlog.py"
echo "Reset with: PAYMENT_MODE=ok docker compose up -d payment-worker"
