"""FastAPI application factory."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.config import Settings, get_settings
from app.db import get_engine
from app.logging import RequestLoggingMiddleware, configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        structlog.get_logger("app").info("startup", env=settings.env, demo_auth=settings.demo_auth)
        yield
        await get_engine().dispose()

    app = FastAPI(title="Circuit API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Added last so it is the outermost layer and also times CORS handling.
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health.router)
    return app


app = create_app()
