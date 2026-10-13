"""FastAPI app: request-id middleware, CORS, health, /api/v1 routes."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.requests import Request

from app.api.errors import install_error_handlers
from app.api.routes import admin, auth, orders, restaurants
from app.core.config import get_settings
from app.core.db import init_db
from app.core.logging import configure_logging

configure_logging()


def create_app() -> FastAPI:
    settings = get_settings()
    init_db(settings.DATABASE_URL)

    app = FastAPI(title="QuickBite API", version="1.0.0")

    @app.middleware("http")
    async def _request_id(request: Request, call_next):
        request.state.request_id = request.headers.get(
            "X-Request-ID", f"req_{uuid.uuid4().hex[:12]}"
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["Location"],
    )
    install_error_handlers(app)

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        from fastapi.responses import JSONResponse

        from app.core.db import session_factory

        checks = {}
        ok = True
        try:
            factory = session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "up"
        except Exception:
            checks["database"] = "down"
            ok = False
        # Broker-down still accepts orders via the outbox (assignment §7), so
        # readiness reports the broker state without hiding that semantic.
        try:
            import asyncio

            import aio_pika

            connection = await asyncio.wait_for(
                aio_pika.connect_robust(settings.AMQP_URL), timeout=3
            )
            await connection.close()
            checks["broker"] = "up"
        except Exception:
            checks["broker"] = "down"
        if not ok:
            return JSONResponse(status_code=503, content={"status": "down", **checks})
        return {"status": "ready", **checks}

    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(restaurants.router, prefix="/api/v1", tags=["restaurants"])
    app.include_router(orders.router, prefix="/api/v1", tags=["orders"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    return app


app = create_app()
