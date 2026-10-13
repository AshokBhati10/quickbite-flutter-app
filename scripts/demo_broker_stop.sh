#!/bin/sh
# Broker stop: accept an order into the outbox while RabbitMQ is down,
# restart, show eventual completion.
# Usage: sh scripts/demo_broker_stop.sh
set -eu
docker compose stop rabbitmq
echo "broker stopped. Place an order now (202 accepted, outbox waits):"
echo "  curl -s -X POST localhost:8000/api/v1/orders ... "
echo "then: docker compose start rabbitmq"
echo "and watch the order reach DRIVER_ASSIGNED."
