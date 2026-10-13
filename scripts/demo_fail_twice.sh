#!/bin/sh
# Fail-twice-then-succeed: shows ~2s/10s retry delays, one payment, recovery.
# Usage: sh scripts/demo_fail_twice.sh
set -eu
export PAYMENT_MODE=fail-twice-then-succeed
docker compose up -d payment-worker
echo "payment worker set to fail-twice-then-succeed; place an order, then watch:"
echo "  .venv/bin/python scripts/inspect_backlog.py"
echo "Delays come from RETRY_DELAYS_S (default 2,10,30)."
