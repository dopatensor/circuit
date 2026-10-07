"""Login state and demo personas (F9 backend)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.auth import (
    DEMO_SUBJECT_PREFIX,
    SessionDep,
    SettingsDep,
    TokenClaims,
    get_token_claims,
    issue_demo_token,
)
from app.events import record_event
from app.models import Member
from app.schemas import AuthMe, DemoLoginIn, MemberSummary, Persona, TokenOut
from app.seed.stories import DEMO_PERSONAS, DEMO_STORIES

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_demo(settings) -> None:
    if not settings.demo_auth:
        # 404, not 403: in a real deployment these endpoints simply don't exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/demo/personas", response_model=list[Persona])
async def list_personas(settings: SettingsDep, session: SessionDep) -> list[Persona]:
    """The seeded people the persona switcher can log in as (DEMO_AUTH only)."""
    _require_demo(settings)
    subjects = [f"{DEMO_SUBJECT_PREFIX}{key}" for key, _, _ in DEMO_PERSONAS]
    members = {
        m.auth_subject: m
        for m in (
            await session.scalars(select(Member).where(Member.auth_subject.in_(subjects)))
        ).all()
    }
    personas = []
    for key, number, story in DEMO_PERSONAS:
        m = members.get(f"{DEMO_SUBJECT_PREFIX}{key}")
        if m is not None:  # missing only if the seed hasn't been loaded
            personas.append(
                Persona(
                    key=key,
                    member_id=m.id,
                    role=m.role,
                    display_name=m.display_name,
                    verification_level=m.verification_level,
                    story=story,
                    story_number=number,
                    story_title=DEMO_STORIES[number],
                )
            )
    return personas


@router.post("/demo/login", response_model=TokenOut)
async def demo_login(
    body: DemoLoginIn, request: Request, settings: SettingsDep, session: SessionDep
) -> TokenOut:
    """Get a token for a seeded member (DEMO_AUTH only). Any seeded member key works."""
    _require_demo(settings)
    member = await session.scalar(
        select(Member).where(Member.auth_subject == f"{DEMO_SUBJECT_PREFIX}{body.persona}")
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown persona")
    token, expires_in = issue_demo_token(settings, member)
    request.state.user_id = str(member.id)
    await record_event(session, "auth.demo_login", actor_id=member.id)
    await session.commit()
    return TokenOut(
        access_token=token, expires_in=expires_in, member=MemberSummary.model_validate(member)
    )


@router.get("/me", response_model=AuthMe)
async def auth_me(
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: SessionDep,
) -> AuthMe:
    """Who the token belongs to, and whether they have created a profile yet."""
    member = await session.scalar(select(Member).where(Member.auth_subject == claims.subject))
    if member is not None:
        request.state.user_id = str(member.id)
    return AuthMe(
        subject=claims.subject,
        is_demo=claims.is_demo,
        has_profile=member is not None,
        member=MemberSummary.model_validate(member) if member else None,
    )
