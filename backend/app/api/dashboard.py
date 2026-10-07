"""Partner dashboard (F8): what the ecosystem lacks, where, and how it is doing.
Partner admins only."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import CurrentUser, SessionDep, SettingsDep, require_admin
from app.dashboard import gaps_by_area, gaps_by_capability, intro_acceptance, network_stats
from app.events import record_event
from app.schemas import (
    AcceptanceGroup,
    AreaGaps,
    CapabilityGap,
    GapList,
    IntroAcceptance,
    NetworkStats,
)
from app.seed.catalog import CAPABILITY_IDS

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
PartnerAdmin = Annotated[CurrentUser, Depends(require_admin())]


async def _viewed(session, admin: CurrentUser, section: str, **payload) -> None:
    await record_event(
        session, "dashboard.viewed", actor_id=admin.member_id,
        payload={"section": section, **payload},
    )  # fmt: skip
    await session.commit()


@router.get("/gaps", response_model=GapList)
async def capability_gaps(
    admin: PartnerAdmin,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GapList:
    """Per capability: active needs vs active offers, biggest gap first."""
    items = (await gaps_by_capability(session))[:limit]
    await _viewed(session, admin, "gaps")
    return GapList(items=[CapabilityGap(**i) for i in items])


@router.get("/gaps/areas", response_model=AreaGaps)
async def area_gaps(
    admin: PartnerAdmin,
    session: SessionDep,
    settings: SettingsDep,
    capability: str | None = None,
    cell_km: Annotated[float, Query(ge=0.25, le=10)] = 2.0,
) -> AreaGaps:
    """The gap on a grid of square cells (about cell_km across) for a map heat layer.
    Filter to one capability, e.g. regulatory_affairs."""
    if capability is not None and capability not in CAPABILITY_IDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown capability")
    cells = await gaps_by_area(
        session, cell_km=cell_km, center_lat=settings.city_center_lat, capability=capability
    )
    await _viewed(session, admin, "areas", capability=capability)
    return AreaGaps(
        capability_id=capability,
        cell_km=cell_km,
        max_gap=max((c["gap"] for c in cells), default=0),
        cells=cells,
    )


@router.get("/stats", response_model=NetworkStats)
async def stats(admin: PartnerAdmin, session: SessionDep) -> NetworkStats:
    result = NetworkStats(**await network_stats(session))
    await _viewed(session, admin, "stats")
    return result


@router.get("/intros", response_model=IntroAcceptance)
async def intros(admin: PartnerAdmin, session: SessionDep) -> IntroAcceptance:
    """Intro acceptance rate, local vs bridge matches. Accepted and completed intros
    count as accepted; declined and expired as not; open and withdrawn ones are left out."""
    groups = await intro_acceptance(session)
    await _viewed(session, admin, "intros")

    def out(a) -> AcceptanceGroup:
        return AcceptanceGroup(decided=a.decided, accepted=a.accepted, rate=a.rate)

    return IntroAcceptance(local=out(groups[False]), bridge=out(groups[True]))
