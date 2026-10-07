"""Admin actions (MVP: partner admins with level 3)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, SessionDep, require_admin
from app.events import record_event
from app.models import Member
from app.schemas import MemberSummary, VerificationUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])
AdminUser = Annotated[CurrentUser, Depends(require_admin())]


@router.put("/members/{member_id}/verification", response_model=MemberSummary)
async def set_verification_level(
    member_id: uuid.UUID, body: VerificationUpdate, admin: AdminUser, session: SessionDep
) -> Member:
    """Set a member's verification level (F7). Level 3 means 'role verified by admin'."""
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    previous = member.verification_level
    member.verification_level = body.level
    await record_event(
        session,
        "member.verification_changed",
        actor_id=admin.member_id,
        target_type="member",
        target_id=member.id,
        payload={"from": previous, "level": body.level, "via": "admin"},
    )
    await session.commit()
    await session.refresh(member)
    return member
