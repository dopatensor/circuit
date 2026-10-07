"""Startup map for students (F2 backend).

- /nearby: startups within a radius of a point (distance is a hard filter), sorted
  by distance or by skill match.
- /bbox: startups inside the visible map rectangle, for panning and zooming.

Both return the same pin shape: hiring status (pin colour), sector, open roles,
interest count and, for students, the "match to my skills" score.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geography
from sqlalchemy import cast, exists, func, null, or_, select

from app.auth import LEVEL_BROWSE, CurrentUser, SessionDep, SettingsDep, require_level
from app.events import record_event
from app.geo import member_center, point
from app.jobs import job_roles, match_out, member_skills, startup_need_caps
from app.models import Event, Job, JobCapability, Need, Startup
from app.profiles import lat_lng_columns
from app.schemas import JobBrief, LatLng, MapResult, MapStartup

router = APIRouter(prefix="/api/map", tags=["map"])
BrowseUser = Annotated[CurrentUser, Depends(require_level(LEVEL_BROWSE))]

MAX_RADIUS_KM = 50.0
MAX_RESULTS = 300


def _filters(hiring: bool | None, sector: str | None, capability: str | None) -> list:
    filters = [Startup.location.is_not(None)]
    if hiring is not None:
        filters.append(Startup.hiring == hiring)
    if sector:
        filters.append(Startup.sector == sector)
    if capability:
        # Either an open role asks for it, or the startup has an active need for it.
        filters.append(
            or_(
                exists().where(
                    Job.startup_id == Startup.id,
                    Job.status == "open",
                    JobCapability.job_id == Job.id,
                    JobCapability.capability_id == capability,
                ),
                exists().where(
                    Need.owner_type == "startup",
                    Need.owner_id == Startup.id,
                    Need.capability_id == capability,
                    Need.active,
                ),
            )
        )
    return filters


async def _pins(session, rows, user: CurrentUser) -> list[MapStartup]:
    """Turn query rows (Startup, lat, lng, distance_km) into pins, with 4 extra queries
    in total (not per startup)."""
    ids = [r.Startup.id for r in rows]
    if not ids:
        return []
    id_strings = [str(i) for i in ids]
    interest = Event.type == "startup.interest"
    counts = dict(
        (
            await session.execute(
                select(Event.target_id, func.count(func.distinct(Event.actor_id)))
                .where(interest, Event.target_type == "startup", Event.target_id.in_(id_strings))
                .group_by(Event.target_id)
            )
        ).all()
    )
    mine = set(
        (
            await session.scalars(
                select(Event.target_id).where(
                    interest, Event.actor_id == user.member_id, Event.target_id.in_(id_strings)
                )
            )
        ).all()
    )
    roles = await job_roles(session, ids)
    skills: dict[str, int] = {}
    needs: dict[uuid.UUID, list[str]] = {}
    if user.role == "student":
        skills = await member_skills(session, user.member_id)
        needs = await startup_need_caps(session, ids)

    pins = []
    for r in rows:
        s = r.Startup
        pins.append(
            MapStartup(
                id=s.id,
                name=s.name,
                sector=s.sector,
                stage=s.stage,
                hiring=s.hiring,
                location=LatLng(lat=r.lat, lng=r.lng),
                distance_km=round(r.distance_km, 2) if r.distance_km is not None else None,
                jobs=[
                    JobBrief(**{k: j[k] for k in ("id", "title", "type", "paid", "compensation")})
                    for j in roles.get(s.id, [])
                ],
                claimed=s.claimed_by_member_id is not None,
                interest_count=counts.get(str(s.id), 0),
                interested=str(s.id) in mine,
                match=match_out(skills, roles.get(s.id, []), needs.get(s.id, []))
                if user.role == "student"
                else None,
            )
        )
    return pins


@router.get("/startups/nearby", response_model=MapResult)
async def nearby(
    user: BrowseUser,
    session: SessionDep,
    settings: SettingsDep,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float, Query(gt=0, le=MAX_RADIUS_KM)] = 10.0,
    hiring: bool | None = None,
    sector: str | None = None,
    capability: str | None = None,
    min_match: Annotated[int | None, Query(ge=0, le=100)] = None,
    sort: Literal["distance", "match"] = "distance",
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS)] = 100,
) -> MapResult:
    """Startups within radius_km of (lat, lng). Without a point we use your profile
    location, or the city centre if you haven't set one."""
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Send both lat and lng")
    if lat is None:
        lat, lng = await member_center(session, user.member_id, settings)
    origin = point(lat, lng)
    slat, slng = lat_lng_columns(Startup.location)
    distance_km = (func.ST_Distance(Startup.location, origin) / 1000.0).label("distance_km")
    rows = (
        await session.execute(
            select(Startup, slat, slng, distance_km)
            .where(
                *_filters(hiring, sector, capability),
                func.ST_DWithin(Startup.location, origin, radius_km * 1000.0),
            )
            .order_by(distance_km, Startup.id)
            .limit(MAX_RESULTS)
        )
    ).all()
    pins = await _pins(session, rows, user)
    if min_match is not None and user.role == "student":
        pins = [p for p in pins if p.match and p.match.score >= min_match]
    if sort == "match" and user.role == "student":
        pins.sort(key=lambda p: (-(p.match.score if p.match else 0), p.distance_km or 0))
    await record_event(
        session,
        "map.nearby_searched",
        actor_id=user.member_id,
        payload={
            "radius_km": radius_km,
            "hiring": hiring,
            "sector": sector,
            "capability": capability,
            "sort": sort,
            "results": len(pins),
        },  # fmt: skip
    )
    await session.commit()
    return MapResult(
        center=LatLng(lat=lat, lng=lng), radius_km=radius_km, total=len(pins), items=pins[:limit]
    )


@router.get("/startups/bbox", response_model=MapResult)
async def in_bbox(
    user: BrowseUser,
    session: SessionDep,
    min_lat: Annotated[float, Query(ge=-90, le=90)],
    min_lng: Annotated[float, Query(ge=-180, le=180)],
    max_lat: Annotated[float, Query(ge=-90, le=90)],
    max_lng: Annotated[float, Query(ge=-180, le=180)],
    hiring: bool | None = None,
    sector: str | None = None,
    capability: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS)] = MAX_RESULTS,
) -> MapResult:
    """Startups inside the rectangle the map is currently showing."""
    if min_lat >= max_lat or min_lng >= max_lng:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Empty bounding box")
    envelope = cast(func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326), Geography)
    slat, slng = lat_lng_columns(Startup.location)
    rows = (
        await session.execute(
            select(Startup, slat, slng, null().label("distance_km"))
            .where(
                *_filters(hiring, sector, capability),
                func.ST_Intersects(Startup.location, envelope),
            )
            .order_by(Startup.hiring.desc(), Startup.name, Startup.id)
            .limit(limit)
        )
    ).all()
    pins = await _pins(session, rows, user)
    return MapResult(center=None, radius_km=None, total=len(pins), items=pins)
