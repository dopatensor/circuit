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
    # True when this member claimed the startup's page (and so can post jobs for it).
    is_claimer: bool = False


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
    jobs: list["JobBrief"]
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
    story: str  # their part in the story, one line
    story_number: int  # 1-5, the demo story they belong to
    story_title: str  # e.g. "Bridge match"


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
    jobs: list["JobBrief"]
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
    # Applications waiting for this startup. On an unclaimed startup they are saved
    # and shown to the founder once they claim the page.
    applications_waiting: int
    you_are_interested: bool  # has the current user pressed "I'm interested"?


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


# --- jobs and applications (F11) ----------------------------------------------------------

JobType = Literal["internship", "full_time", "part_time", "contract"]
ApplicationStatus = Literal["submitted", "shortlisted", "rejected", "hired", "withdrawn"]


class JobCapabilityIO(BaseModel):
    capability_id: CapabilityId
    min_level: int = Field(default=2, ge=1, le=3)


class JobBrief(BaseModel):
    id: uuid.UUID
    title: str
    type: JobType
    paid: bool
    compensation: str | None


class JobStartup(BaseModel):
    id: uuid.UUID
    name: str
    sector: str
    claimed: bool
    location: LatLng | None
    address: str | None


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    type: JobType
    paid: bool
    compensation: str | None
    status: Literal["open", "closed"]
    capabilities: list[JobCapabilityIO]
    startup: JobStartup
    distance_km: float | None
    match: SkillMatchOut | None  # students only
    has_applied: bool
    created_at: datetime


class JobIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    type: JobType = "full_time"
    paid: bool = True
    compensation: str | None = Field(default=None, max_length=120)
    capabilities: list[JobCapabilityIO] = Field(min_length=1, max_length=10)


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    type: JobType | None = None
    paid: bool | None = None
    compensation: str | None = Field(default=None, max_length=120)
    status: Literal["open", "closed"] | None = None
    capabilities: list[JobCapabilityIO] | None = Field(default=None, min_length=1, max_length=10)


class ApplyIn(BaseModel):
    note: str = Field(default="", max_length=500)


class ApplicationJob(BaseModel):
    id: uuid.UUID
    title: str
    type: JobType
    paid: bool
    startup_id: uuid.UUID
    startup_name: str
    startup_claimed: bool


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job: ApplicationJob
    status: ApplicationStatus
    note: str
    match_score_at_apply: int
    created_at: datetime
    status_changed_at: datetime | None


class ApplicantMember(BaseModel):
    """What a founder sees about an applicant: skills, not college."""

    id: uuid.UUID
    display_name: str
    city: str | None
    verification_level: int


class ApplicantOut(BaseModel):
    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    member: ApplicantMember
    skills: list[SkillIn]
    match: SkillMatchOut  # live score against the job
    note: str
    status: ApplicationStatus
    created_at: datetime


class ApplicationStatusIn(BaseModel):
    status: Literal["submitted", "shortlisted", "rejected", "hired"]


StartupOut.model_rebuild()
MapStartup.model_rebuild()


# --- matches (F4) -------------------------------------------------------------------------


class MatchOut(BaseModel):
    candidate_type: Literal["member", "startup", "job"]
    candidate_id: uuid.UUID
    title: str  # person's name, startup name, or job title
    subtitle: str  # role and sector, or the job's startup
    sector: str | None
    score: int  # 0-100
    reason: str  # one line, built from the components
    is_bridge: bool  # cross-sector: shown as a "Bridge match" badge
    # Who a warm intro would go to: the person, or the founder who claimed the startup.
    # None for jobs and unclaimed startups.
    intro_member_id: uuid.UUID | None
    components: dict
    computed_at: datetime | None


class MatchList(BaseModel):
    items: list[MatchOut]
    computed_at: datetime | None


class RecomputeOut(BaseModel):
    members: int
    results: int
    embedded: int


# --- warm intros (F5) ---------------------------------------------------------------------

IntroStatus = Literal[
    "pending", "forwarded", "accepted", "declined", "expired", "completed", "withdrawn"
]
IntroAction = Literal["forward", "accept", "decline", "withdraw", "rate"]


class Capacity(BaseModel):
    """Intro requests a member takes on per week (received plus passed on)."""

    slots: int
    used: int
    next_free_at: datetime | None  # when a slot frees up, if they are full


class IntroPath(BaseModel):
    """How a request to this person would travel."""

    target: MemberSummary
    # mutual: through someone who knows you both; direct: you already know each other;
    # none: no connection within two hops, so the request goes to them directly.
    kind: Literal["mutual", "direct", "none"]
    via: MemberSummary | None
    strengths: list[float]  # tie strengths along the path (0-1), you first
    sentence: str  # one line for the UI
    alternatives: list[MemberSummary]  # other mutuals, best first
    can_request: bool
    blocked_reason: str | None  # why not, politely
    open_request_id: uuid.UUID | None  # your request to them that is still open


class IntroRequestIn(BaseModel):
    to_member_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=500)
    # Optional: pick one of the alternatives from the path. By default the best mutual.
    via_member_id: uuid.UUID | None = None


class IntroOut(BaseModel):
    id: uuid.UUID
    status: IntroStatus
    sender: MemberSummary
    target: MemberSummary
    via: MemberSummary | None
    reason: str
    is_bridge: bool
    outcome_rating: int | None
    created_at: datetime
    forwarded_at: datetime | None
    responded_at: datetime | None
    completed_at: datetime | None
    my_role: Literal["sender", "mutual", "target"]
    actions: list[IntroAction]  # what you can do with it now


class IntroInbox(BaseModel):
    sent: list[IntroOut]
    to_forward: list[IntroOut]  # you are the mutual and haven't decided yet
    received: list[IntroOut]  # requests that reached you
    capacity: Capacity
    sent_this_week: int
    sent_limit: int


class IntroRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


# --- exchange circuits (F6) ---------------------------------------------------------------

CircuitStatus = Literal["proposed", "active", "declined", "expired", "completed"]


class CapabilityRef(BaseModel):
    id: str
    name: str


class CircuitLegOut(BaseModel):
    position: int
    giver: MemberSummary
    receiver: MemberSummary
    capability: CapabilityRef
    consent: Literal["pending", "accepted", "declined"]  # the giver's answer
    fulfilled: bool  # the receiver says they got the help
    rating: int | None  # the receiver's rating, 1-5


class CircuitCard(BaseModel):
    """A loop card: "You help X with A, X helps Y with B, Y helps you with C"."""

    id: uuid.UUID
    round_key: str
    status: CircuitStatus
    score: int  # 0-100, the weakest link
    created_at: datetime
    expires_at: datetime  # answer by then (while proposed)
    sentence: str
    legs: list[CircuitLegOut]  # starting with the leg where you give
    my_consent: Literal["pending", "accepted", "declined"]
    actions: list[Literal["accept", "decline", "rate"]]


class CircuitRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


class RoundCircuit(BaseModel):
    id: uuid.UUID | None  # None in a dry run
    score: int
    members: list[MemberSummary]
    sentence: str  # "Asha helps Arjun with hiring, Arjun helps Priya with ..."


class RoundOut(BaseModel):
    round_key: str
    dry_run: bool
    pool: int  # members with at least one possible exchange
    edges: int
    cycles_found: int
    circuits: list[RoundCircuit]


# --- partner dashboard (F8) ---------------------------------------------------------------


class CapabilityGap(BaseModel):
    capability_id: str
    name: str
    category: str
    needs: int  # active needs (members and startups)
    offers: int  # active offers
    gap: int  # needs - offers; the biggest gaps are what the ecosystem lacks


class GapList(BaseModel):
    items: list[CapabilityGap]


class AreaCell(BaseModel):
    lat: float  # centre of the grid cell
    lng: float
    needs: int
    offers: int
    gap: int


class AreaGaps(BaseModel):
    """Grid cells for a map heat layer (weight by gap, or by needs)."""

    capability_id: str | None  # None = all capabilities
    cell_km: float
    max_gap: int
    cells: list[AreaCell]


class NetworkStats(BaseModel):
    members: int
    members_by_role: dict[str, int]
    startups: int
    startups_claimed: int
    startups_hiring: int
    open_jobs: int
    applications: int
    active_needs: int
    active_offers: int
    connections: int
    intros: int
    intros_accepted: int
    students_interested: int  # distinct students who pressed "I'm interested"
    circuits_opted_in: int
    circuits_by_status: dict[str, int]


class AcceptanceGroup(BaseModel):
    decided: int  # accepted + completed + declined + expired
    accepted: int  # accepted + completed
    rate: float | None  # accepted / decided (0-1); None when nothing is decided yet


class IntroAcceptance(BaseModel):
    """Do cross-sector (bridge) intros work as well as local ones?"""

    local: AcceptanceGroup
    bridge: AcceptanceGroup
