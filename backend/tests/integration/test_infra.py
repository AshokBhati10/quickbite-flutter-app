"""Phase 0 infra integration: postgres + rabbitmq reachable and healthy."""

import asyncio
import os

import aio_pika
import asyncpg


def _pg_dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", "postgresql://quickbite:quickbite@localhost:5432/quickbite"
    )


def _amqp_url() -> str:
    return os.environ.get(
        "TEST_AMQP_URL", "amqp://quickbite:quickbite@localhost:5672/%2F"
    )


async def _check_postgres() -> str:
    conn = await asyncpg.connect(_pg_dsn())
    try:
        version = await conn.fetchval("SELECT version()")
        assert "PostgreSQL" in version
        return version
    finally:
        await conn.close()


async def _check_rabbitmq() -> None:
    connection = await aio_pika.connect_robust(_amqp_url())
    try:
        channel = await connection.channel()
        # RabbitMQ 4 forbids transient non-exclusive queues: exclusive probe.
        await channel.declare_queue(
            "phase0.probe", durable=False, exclusive=True, auto_delete=True
        )
    finally:
        await connection.close()


def test_postgres_and_rabbitmq_reachable() -> None:
    async def _main() -> None:
        version = await _check_postgres()
        print(f"\npostgres: {version.split(',')[0]}")
        await _check_rabbitmq()
        print("rabbitmq: probe queue declared ok")

    asyncio.run(_main())
