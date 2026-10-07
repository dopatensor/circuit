"""FastAPI application factory."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    catalog,
    circuits,
    dashboard,
    health,
    intros,
    jobs,
    matches,
    members,
    needs,
    onboarding,
    startup_map,
    startups,
)
from app.config import Settings, get_settings
from app.db import get_engine
from app.logging import RequestLoggingMiddleware, configure_logging
from app.scheduler import start_scheduler


def create_app(settings: Settings | None = None) -> FastAPI:
    explicit_settings = settings is not None
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        structlog.get_logger("app").info("startup", env=settings.env, demo_auth=settings.demo_auth)
        scheduler = start_scheduler(settings) if settings.scheduler_enabled else None
        yield
        if scheduler:
            scheduler.shutdown(wait=False)
        await get_engine().dispose()

    app = FastAPI(title="Circuit API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Date lets the app show "Last updated <time>" for data served offline from cache.
        expose_headers=["X-Request-ID", "Date"],
    )
    # Added last so it is the outermost layer and also times CORS handling.
    app.add_middleware(RequestLoggingMiddleware)
    for module in (
        health,
        auth,
        catalog,
        members,
        needs,
        startups,
        startup_map,
        jobs,
        matches,
        intros,
        circuits,
        dashboard,
        onboarding,
        admin,
    ):
        app.include_router(module.router)
    if explicit_settings:
        # Tests (and scripts) can run the app with their own settings.
        app.dependency_overrides[get_settings] = lambda: settings
    return app


app = create_app()
