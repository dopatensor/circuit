"""Request and response shapes for the API (these become the OpenAPI spec that the
frontend's TypeScript client is generated from, so keep names stable and clear)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.seed.catalog import CAPABILITY_IDS, TRAIT_IDS

SelfAssignableRole = Literal["student", "founder", "mentor", "investor"]
Role = Literal["student", "founder", "mentor", "investor", "partner_admin"]


def _check_capability(value: str) -> str:
    if value not in CAPABILITY_IDS:
        raise ValueError(f"unknown capability: {value}")
    return value


def _check_trait(value: str) -> str:
    if value not in TRAIT_IDS:
        raise ValueError(f"unknown trait: {value}")
    return value


# A string that must be one of our fixed capability / trait ids.
CapabilityId = Annotated[str, AfterValidator(_check_capability)]
TraitId = Annotated[str, AfterValidator(_check_trait)]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


# --- catalog ------------------------------------------------------------------------------


class CapabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    category: str
    description: str


class TraitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str


# --- needs, offers, skills ----------------------------------------------------------------


class NeedIn(BaseModel):
    capability_id: CapabilityId
    text: str = Field(default="", max_length=500)


class NeedUpdate(BaseModel):
    text: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class NeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_type: Literal["member", "startup"]
    owner_id: uuid.UUID
    capability_id: str
    text: str
    active: bool
    created_at: datetime


class OfferIn(NeedIn):
    pass


OfferUpdate = NeedUpdate


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    member_id: uuid.UUID
    capability_id: str
    text: str
    active: bool
    created_at: datetime


class SkillIn(BaseModel):
    capability_id: CapabilityId
    level: int = Field(default=2, ge=1, le=3)


class TraitsIn(BaseModel):
    trait_ids: Annotated[list[TraitId], AfterValidator(_dedupe)] = Field(max_length=10)


class SkillsIn(BaseModel):
    skills: list[SkillIn] = Field(max_length=15)


# --- members ------------------------------------------------------------------------------


class MemberCreate(BaseModel):
    role: SelfAssignableRole
    display_name: str = Field(min_length=1, max_length=120)
    bio: str = Field(default="", max_length=2000)
    sector: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=120)
    college: str | None = Field(default=None, max_length=200)
    location: LatLng | None = None


class MemberUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    sector: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=120)
    college: str | None = Field(default=None, max_length=200)
    location: LatLng | None = None
    open_intro_slots: int | None = Field(default=None, ge=0, le=20)
    circuits_opt_in: bool | None = None
    linkedin_url: HttpUrl | None = None

    @field_validator("linkedin_url")
    @classmethod
    def _linkedin_only(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is not None and not (v.host or "").endswith("linkedin.com"):
            raise ValueError("must be a linkedin.com URL")
        return v


class StartupLink(BaseModel):
    startup_id: uuid.UUID
    name: str
    title: str


class MemberPublic(BaseModel):
    """What other members can see. No exact location: only the city."""

    id: uuid.UUID
    role: Role
    display_name: str
    bio: str
    sector: str | None
    city: str | None
    college: str | None
    verification_level: int
    trait_ids: list[str]
    offers: list[OfferOut]
    needs: list[NeedOut]
    startups: list[StartupLink]


class MemberMe(MemberPublic):
    """Your own profile, with private fields."""

    location: LatLng | None
    linkedin_url: str | None
    open_intro_slots: int
    circuits_opt_in: bool
    skills: list[SkillIn]
    is_demo: bool


class MemberSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: Role
    display_name: str
    sector: str | None
    city: str | None
    verification_level: int


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


# --- startups -----------------------------------------------------------------------------


class OpenRoleIO(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    type: Literal["full_time", "part_time", "internship", "contract"] = "full_time"
    capabilities: list[CapabilityId] = Field(default_factory=list, max_length=10)


class StartupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    website_domain: str = Field(min_length=3, max_length=253, pattern=r"^[a-zA-Z0-9.-]+\.[a-z]+$")
    description: str = Field(default="", max_length=2000)
    sector: str = Field(min_length=1, max_length=64)
    stage: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    location: LatLng
    hiring: bool = False
    open_roles: list[OpenRoleIO] = Field(default_factory=list, max_length=20)
    tech_stack: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("website_domain")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip().lower().removeprefix("www.")


class StartupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sector: str | None = Field(default=None, min_length=1, max_length=64)
    stage: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    location: LatLng | None = None
    hiring: bool | None = None
    open_roles: list[OpenRoleIO] | None = Field(default=None, max_length=20)
    tech_stack: list[str] | None = Field(default=None, max_length=20)


class StartupOut(BaseModel):
    id: uuid.UUID
    name: str
    website_domain: str
    description: str
    sector: str
    stage: str | None
    address: str | None
    location: LatLng | None
    hiring: bool
    open_roles: list[OpenRoleIO]
    tech_stack: list[str]
    claimed: bool
    claimed_by_member_id: uuid.UUID | None
    source: Literal["seed", "crawler", "user"]
    view_count: int
    trait_ids: list[str]
    needs: list[NeedOut]
    team: list[MemberSummary]


# --- auth ---------------------------------------------------------------------------------


class Persona(BaseModel):
    key: str
    member_id: uuid.UUID
    role: Role
    display_name: str
    verification_level: int
    story: str


class DemoLoginIn(BaseModel):
    persona: str = Field(min_length=1, max_length=64)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    member: MemberSummary


class AuthMe(BaseModel):
    subject: str
    is_demo: bool
    has_profile: bool
    member: MemberSummary | None


# --- verification -------------------------------------------------------------------------


class VerificationUpdate(BaseModel):
    level: int = Field(ge=0, le=3)


# --- onboarding (F1) ----------------------------------------------------------------------


class OnboardingSuggestIn(BaseModel):
    text: str = Field(min_length=10, max_length=4000)
    role: SelfAssignableRole | None = None


class SuggestedItem(BaseModel):
    capability_id: str
    text: str


class Suggestions(BaseModel):
    needs: list[SuggestedItem] = Field(default_factory=list)
    offers: list[SuggestedItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)


class OnboardingSuggestOut(BaseModel):
    source: Literal["llm", "manual"]
    # Why we fell back to manual pickers, if we did: "no_api_key" | "llm_unavailable".
    fallback_reason: str | None = None
    suggestions: Suggestions


class OnboardingConfirmIn(BaseModel):
    """The person's final choices after editing the chips. Replaces what they had."""

    bio: str | None = Field(default=None, max_length=2000)
    needs: list[NeedIn] = Field(default_factory=list, max_length=10)
    offers: list[OfferIn] = Field(default_factory=list, max_length=10)
    skills: list[SkillIn] = Field(default_factory=list, max_length=15)
    trait_ids: Annotated[list[TraitId], AfterValidator(_dedupe)] = Field(
        default_factory=list, max_length=10
    )


# --- map (F2) -----------------------------------------------------------------------------


class RoleFitOut(BaseModel):
    title: str
    score: int  # 0..100
    matched: list[str]
    missing: list[str]


class SkillMatchOut(BaseModel):
    """'Match to my skills' for students. Based on skills only, never on college."""

    score: int  # 0..100
    best_role: RoleFitOut | None
    matched: list[str]
    missing: list[str]


class MapStartup(BaseModel):
    id: uuid.UUID
    name: str
    sector: str
    stage: str | None
    hiring: bool
    location: LatLng
    distance_km: float | None
    open_roles: list[OpenRoleIO]
    claimed: bool
    interest_count: int
    interested: bool  # has the current user pressed "I'm interested"?
    match: SkillMatchOut | None  # only for students


class MapResult(BaseModel):
    center: LatLng | None
    radius_km: float | None
    total: int
    items: list[MapStartup]


# --- views, interest, claim (F2/F3) -------------------------------------------------------


class StartupStats(BaseModel):
    view_count: int
    student_viewers_30d: int
    interested_students: int
    interested_total: int


class InterestOut(BaseModel):
    interested: bool
    interest_count: int


class ClaimStartIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ClaimStartOut(BaseModel):
    claim_id: uuid.UUID
    sent_to_domain: str
    expires_at: datetime
    # Only in development or a public demo: the code we would have emailed.
    dev_code: str | None = None


class ClaimVerifyIn(BaseModel):
    claim_id: uuid.UUID
    code: str = Field(pattern=r"^\d{6}$")
