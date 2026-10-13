#!/bin/sh
# Notification backlog: stop notification worker, place orders, show other
# stages finish, restart and drain with no duplicates.
# Usage: sh scripts/demo_notification_backlog.sh
set -eu
docker compose stop notification-worker
echo "notification worker stopped. Place several orders; they still complete."
echo "Then: docker compose start notification-worker"
echo "and verify each event produced exactly one notification."
