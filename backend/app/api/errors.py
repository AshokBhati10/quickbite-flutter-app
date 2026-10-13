"""Consistent error envelope {code, message, details, request_id}."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def envelope(code: str, message: str, request_id: str, details=None) -> dict:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "request_id": request_id,
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", "-")
        status = exc.status_code
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
        }.get(status, "http_error")
        return JSONResponse(
            status_code=status,
            content=envelope(code, str(exc.detail), request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "-")
        return JSONResponse(
            status_code=422,
            content=envelope(
                "validation_error",
                "Request validation failed.",
                request_id,
                {"errors": exc.errors()},
            ),
        )
