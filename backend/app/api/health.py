"""Liveness (/health) and dependency (/health/deps) checks."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import get_engine

router = APIRouter(tags=["health"])

REQUIRED_EXTENSIONS = ("postgis", "vector")


class Health(BaseModel):
    status: Literal["ok"]


class DepCheck(BaseModel):
    ok: bool
    detail: str


class DepsHealth(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, DepCheck]


@router.get("/health", response_model=Health)
async def health() -> Health:
    """The process is up. Does not touch the database."""
    return Health(status="ok")


@router.get(
    "/health/deps",
    response_model=DepsHealth,
    responses={503: {"model": DepsHealth, "description": "A dependency is unavailable"}},
)
async def health_deps(
    response: Response, engine: Annotated[AsyncEngine, Depends(get_engine)]
) -> DepsHealth:
    """Checks Postgres is reachable and has the PostGIS and pgvector extensions."""
    checks: dict[str, DepCheck] = {}
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SHOW server_version"))).scalar_one()
            checks["postgres"] = DepCheck(ok=True, detail=f"server {version}")
            rows = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = ANY(:names)"),
                {"names": list(REQUIRED_EXTENSIONS)},
            )
            installed = {name: version for name, version in rows}
            for ext in REQUIRED_EXTENSIONS:
                checks[ext] = (
                    DepCheck(ok=True, detail=f"version {installed[ext]}")
                    if ext in installed
                    else DepCheck(ok=False, detail="extension not installed")
                )
    except Exception as exc:  # any connection failure means "down"; don't leak the URL
        checks["postgres"] = DepCheck(ok=False, detail=f"unreachable ({type(exc).__name__})")

    healthy = all(c.ok for c in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return DepsHealth(status="ok" if healthy else "degraded", checks=checks)
