"""Smart onboarding (F1): suggest from a bio, then confirm the chosen chips."""

from fastapi import APIRouter
from sqlalchemy import delete

from app.auth import CurrentUserDep, SessionDep, SettingsDep
from app.events import record_event
from app.models import Member, MemberSkill, MemberTrait, Need, Offer
from app.onboarding import SuggestionsUnavailable, get_suggester
from app.profiles import member_me
from app.schemas import (
    MemberMe,
    OnboardingConfirmIn,
    OnboardingSuggestIn,
    OnboardingSuggestOut,
    Suggestions,
)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.post("/suggest", response_model=OnboardingSuggestOut)
async def suggest(
    body: OnboardingSuggestIn, user: CurrentUserDep, session: SessionDep, settings: SettingsDep
) -> OnboardingSuggestOut:
    """Suggest needs, offers, skills and traits from free text. Never fails: without an
    API key, or if the model is unavailable, it returns source="manual" and the UI
    shows the pickers. The text itself is not stored or logged."""
    suggester = get_suggester(settings)
    out: OnboardingSuggestOut
    if suggester is None:
        out = OnboardingSuggestOut(
            source="manual", fallback_reason="no_api_key", suggestions=Suggestions()
        )
    else:
        try:
            suggestions = await suggester.suggest(body.text, body.role)
            out = OnboardingSuggestOut(source="llm", suggestions=suggestions)
        except SuggestionsUnavailable:
            out = OnboardingSuggestOut(
                source="manual", fallback_reason="llm_unavailable", suggestions=Suggestions()
            )
    s = out.suggestions
    await record_event(
        session,
        "onboarding.suggested",
        actor_id=user.member_id,
        payload={
            "source": out.source,
            "fallback_reason": out.fallback_reason,
            "counts": {
                "needs": len(s.needs),
                "offers": len(s.offers),
                "skills": len(s.skills),
                "traits": len(s.traits),
            },  # fmt: skip
        },
    )
    await session.commit()
    return out


@router.post("/confirm", response_model=MemberMe)
async def confirm(body: OnboardingConfirmIn, user: CurrentUserDep, session: SessionDep) -> MemberMe:
    """Save the person's final selection. Replaces their current needs, offers, skills
    and traits in one transaction."""
    mid = user.member_id
    member = await session.get_one(Member, mid)
    if body.bio is not None:
        member.bio = body.bio
    await session.execute(
        Need.__table__.update()
        .where(Need.owner_type == "member", Need.owner_id == mid, Need.active)
        .values(active=False)
    )
    await session.execute(
        Offer.__table__.update().where(Offer.member_id == mid, Offer.active).values(active=False)
    )
    await session.execute(delete(MemberSkill).where(MemberSkill.member_id == mid))
    await session.execute(delete(MemberTrait).where(MemberTrait.member_id == mid))

    needs = {n.capability_id: n.text for n in body.needs}
    offers = {o.capability_id: o.text for o in body.offers}
    skills = {s.capability_id: s.level for s in body.skills}
    session.add_all(
        Need(owner_type="member", owner_id=mid, capability_id=c, text=t) for c, t in needs.items()
    )
    session.add_all(Offer(member_id=mid, capability_id=c, text=t) for c, t in offers.items())
    if member.role == "student":
        session.add_all(
            MemberSkill(member_id=mid, capability_id=c, level=lv) for c, lv in skills.items()
        )
    session.add_all(MemberTrait(member_id=mid, trait_id=t) for t in body.trait_ids)
    await record_event(
        session,
        "onboarding.confirmed",
        actor_id=mid,
        payload={
            "needs": sorted(needs),
            "offers": sorted(offers),
            "skills": sorted(skills) if member.role == "student" else [],
            "traits": body.trait_ids,
        },  # fmt: skip
    )
    await session.commit()
    await session.refresh(member)
    return await member_me(session, member, user.claims.is_demo)
