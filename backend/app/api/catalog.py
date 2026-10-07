"""The fixed capability and trait lists (public: the manual pickers need them)."""

from fastapi import APIRouter
from sqlalchemy import select

from app.auth import SessionDep
from app.models import Capability, Trait
from app.schemas import CapabilityOut, TraitOut

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/capabilities", response_model=list[CapabilityOut])
async def list_capabilities(session: SessionDep) -> list[Capability]:
    return list(
        await session.scalars(select(Capability).order_by(Capability.category, Capability.name))
    )


@router.get("/traits", response_model=list[TraitOut])
async def list_traits(session: SessionDep) -> list[Trait]:
    return list(await session.scalars(select(Trait).order_by(Trait.name)))
