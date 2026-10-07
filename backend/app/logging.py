"""Structured JSON logging and the per-request log middleware (F10).

One JSON line per request: request_id, method, path, status, duration_ms, user_id.
Only the path is logged, never the query string, headers or body, so names, emails,
phone numbers and tokens cannot leak into logs.
"""

import logging
import sys
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def _incoming_request_id(request: Request) -> str:
    # Accept a caller's id only if it looks like an id, so arbitrary text can't be logged.
    value = request.headers.get(REQUEST_ID_HEADER, "")
    if 0 < len(value) <= 64 and all(c.isalnum() or c in "-_" for c in value):
        return value
    return uuid.uuid4().hex


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _incoming_request_id(request)
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            structlog.get_logger("http").info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                # Set by the auth dependency (Phase 2); None for anonymous requests.
                user_id=getattr(request.state, "user_id", None),
            )
            structlog.contextvars.clear_contextvars()
