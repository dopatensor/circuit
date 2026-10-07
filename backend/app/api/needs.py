"""Edit or retire a need or offer by id. Owners only."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.auth import CurrentUser, CurrentUserDep, SessionDep
from app.events import record_event
from app.models import Need, Offer, Startup
from app.schemas import NeedOut, NeedUpdate, OfferOut, OfferUpdate

router = APIRouter(prefix="/api", tags=["needs & offers"])


async def _owned_need(session, need_id: uuid.UUID, user: CurrentUser) -> Need:
    need = await session.get(Need, need_id)
    if need is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Need not found")
    if need.owner_type == "member":
        allowed = need.owner_id == user.member_id
    else:
        startup = await session.get(Startup, need.owner_id)
        allowed = startup is not None and startup.claimed_by_member_id == user.member_id
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your need")
    return need


async def _owned_offer(session, offer_id: uuid.UUID, user: CurrentUser) -> Offer:
    offer = await session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.member_id != user.member_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your offer")
    return offer


def _apply(item: Need | Offer, body: NeedUpdate) -> list[str]:
    changed = []
    if body.text is not None and body.text != item.text:
        item.text = body.text
        item.embedding = None  # recomputed by the matching job (Phase 4)
        changed.append("text")
    if body.active is not None and body.active != item.active:
        item.active = body.active
        changed.append("active")
    return changed


@router.patch("/needs/{need_id}", response_model=NeedOut)
async def update_need(
    need_id: uuid.UUID, body: NeedUpdate, user: CurrentUserDep, session: SessionDep
):
    need = await _owned_need(session, need_id, user)
    changed = _apply(need, body)
    await record_event(
        session, "need.updated", actor_id=user.member_id, target_type="need",
        target_id=need.id, payload={"fields": changed},
    )  # fmt: skip
    await session.commit()
    await session.refresh(need)
    return need


@router.delete("/needs/{need_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_need(need_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    """Needs are retired (active=false), not erased, so dashboard history stays correct."""
    need = await _owned_need(session, need_id, user)
    need.active = False
    await record_event(
        session, "need.retired", actor_id=user.member_id, target_type="need", target_id=need.id
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/offers/{offer_id}", response_model=OfferOut)
async def update_offer(
    offer_id: uuid.UUID, body: OfferUpdate, user: CurrentUserDep, session: SessionDep
):
    offer = await _owned_offer(session, offer_id, user)
    changed = _apply(offer, body)
    await record_event(
        session, "offer.updated", actor_id=user.member_id, target_type="offer",
        target_id=offer.id, payload={"fields": changed},
    )  # fmt: skip
    await session.commit()
    await session.refresh(offer)
    return offer


@router.delete("/offers/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_offer(offer_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    offer = await _owned_offer(session, offer_id, user)
    offer.active = False
    await record_event(
        session, "offer.retired", actor_id=user.member_id, target_type="offer", target_id=offer.id
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
