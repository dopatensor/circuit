"""Database tables (SQLAlchemy 2 ORM models).

Conventions
- Primary keys are UUIDs. Seeded rows get deterministic UUIDs (see app/seed/ids.py) so
  demo personas keep the same id across every reset.
- capabilities and traits use short slugs ("regulatory_affairs") as their id, which keeps
  the fixed lists readable in the database, in the API and in LLM prompts.
- Enumerations are plain text columns guarded by CHECK constraints (easier to evolve
  with migrations than native Postgres ENUM types).
- Locations are geography(Point, 4326): longitude/latitude on the WGS84 globe, so
  distances come out in metres.
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5

MEMBER_ROLES = ("student", "founder", "mentor", "investor", "partner_admin")
STARTUP_SOURCES = ("seed", "crawler", "user")
OWNER_TYPES = ("member", "startup")
INTRO_STATUSES = ("pending", "accepted", "declined", "expired", "completed")
CIRCUIT_STATUSES = ("proposed", "active", "declined", "expired", "completed")
CONSENT_STATES = ("pending", "accepted", "declined")
CLAIM_STATUSES = ("pending", "verified", "expired", "superseded")
JOB_TYPES = ("internship", "full_time", "part_time", "contract")
JOB_STATUSES = ("open", "closed")
APPLICATION_STATUSES = ("submitted", "shortlisted", "rejected", "hired", "withdrawn")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    # Predictable constraint names make migrations reproducible.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _point() -> Mapped[str | None]:
    # spatial_index=False: we declare the GIST index explicitly in __table_args__.
    return mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )


# --- Fixed lists ----------------------------------------------------------------------


class Capability(Base):
    """Something a person can need or offer, e.g. "regulatory_affairs"."""

    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Trait(Base):
    """A characteristic of how someone works or sells, e.g. "long_sales_cycle"."""

    __tablename__ = "traits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


# --- People and startups --------------------------------------------------------------


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint(_in("role", MEMBER_ROLES), name="role"),
        CheckConstraint("verification_level BETWEEN 0 AND 3", name="verification_level"),
        CheckConstraint("open_intro_slots >= 0", name="open_intro_slots"),
        Index("ix_members_location", "location", postgresql_using="gist"),
        Index("ix_members_role", "role"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # The login identity: the JWT "sub" claim from the auth provider (or "demo:<key>").
    auth_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Main sector of experience; a match across different sectors is a "bridge" match.
    sector: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = _point()
    city: Mapped[str | None] = mapped_column(String(120))
    college: Mapped[str | None] = mapped_column(String(200))  # students only
    linkedin_url: Mapped[str | None] = mapped_column(String(300))
    verification_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    open_intro_slots: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    circuits_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Startup(Base):
    __tablename__ = "startups"
    __table_args__ = (
        CheckConstraint(_in("source", STARTUP_SOURCES), name="source"),
        Index("ix_startups_location", "location", postgresql_using="gist"),
        Index("ix_startups_hiring", "hiring"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website_domain: Mapped[str] = mapped_column(String(253), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sector: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = _point()
    hiring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # [{"title": str, "type": "full_time"|"internship"|..., "capabilities": [capability ids]}]
    open_roles: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tech_stack: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    claimed_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _created_at()


class StartupMember(Base):
    __tablename__ = "startup_members"

    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False, default="")


class StartupClaim(Base):
    """A founder's attempt to claim a startup by proving they have an email on its domain.

    We never store the email address or the code itself: only the email's domain (to
    show which domain was verified) and a hash of the code.
    """

    __tablename__ = "startup_claims"
    __table_args__ = (
        CheckConstraint(_in("status", CLAIM_STATUSES), name="status"),
        Index("ix_startup_claims_startup_member", "startup_id", "member_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    email_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Jobs and applications (F11) -----------------------------------------------------


class Job(Base):
    """A job a startup is hiring for. Seeded and crawled jobs come from the startup's
    open_roles; claimed startups manage their jobs directly."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(_in("type", JOB_TYPES), name="type"),
        CheckConstraint(_in("status", JOB_STATUSES), name="status"),
        CheckConstraint(_in("source", STARTUP_SOURCES), name="source"),
        Index("ix_jobs_startup_id", "startup_id"),
        Index("ix_jobs_open_type_paid", "type", "paid", postgresql_where=text("status = 'open'")),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="full_time")
    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    compensation: Mapped[str | None] = mapped_column(String(120))  # e.g. "₹20,000/month"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JobCapability(Base):
    """A capability a job requires. min_level: 1 basic, 2 solid, 3 strong."""

    __tablename__ = "job_capabilities"
    __table_args__ = (CheckConstraint("min_level BETWEEN 1 AND 3", name="min_level"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id"), primary_key=True, index=True
    )
    min_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)


class Application(Base):
    """A student's application to a job. One per student per job."""

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(_in("status", APPLICATION_STATUSES), name="status"),
        UniqueConstraint("job_id", "member_id", name="uq_applications_job_member"),
        Index("ix_applications_member_id", "member_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    # Skill match when the student applied (the founder's list uses the live score).
    match_score_at_apply: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = _created_at()
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Needs, offers, traits, skills ----------------------------------------------------


class Need(Base):
    """A capability someone is looking for. Owned by a member or by a startup."""

    __tablename__ = "needs"
    __table_args__ = (
        CheckConstraint(_in("owner_type", OWNER_TYPES), name="owner_type"),
        Index("ix_needs_owner", "owner_type", "owner_id"),
        Index("ix_needs_capability_active", "capability_id", postgresql_where=text("active")),
        Index(
            "ix_needs_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Points at members.id or startups.id depending on owner_type (so no foreign key).
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capability_id: Mapped[str] = mapped_column(ForeignKey("capabilities.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _created_at()


class Offer(Base):
    """A capability a member can help others with."""

    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_capability_active", "capability_id", postgresql_where=text("active")),
        Index(
            "ix_offers_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_id: Mapped[str] = mapped_column(ForeignKey("capabilities.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _created_at()


class MemberTrait(Base):
    __tablename__ = "member_traits"

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    trait_id: Mapped[str] = mapped_column(ForeignKey("traits.id"), primary_key=True, index=True)


class StartupTrait(Base):
    __tablename__ = "startup_traits"

    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), primary_key=True
    )
    trait_id: Mapped[str] = mapped_column(ForeignKey("traits.id"), primary_key=True, index=True)


class MemberSkill(Base):
    """A student's skill, linked to a capability. level: 1 basic, 2 solid, 3 strong."""

    __tablename__ = "member_skills"
    __table_args__ = (CheckConstraint("level BETWEEN 1 AND 3", name="level"),)

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id"), primary_key=True, index=True
    )
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)


# --- Network --------------------------------------------------------------------------


class Connection(Base):
    """An undirected tie between two members, stored once with member_a < member_b."""

    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint("member_a < member_b", name="ordered_pair"),
        CheckConstraint("strength > 0 AND strength <= 1", name="strength"),
        UniqueConstraint("member_a", "member_b", name="uq_connections_pair"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    member_a: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    member_b: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    # e.g. "worked_together", "cohort", "mentored", "invested", "classmates", "intro"
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class IntroRequest(Base):
    __tablename__ = "intro_requests"
    __table_args__ = (
        CheckConstraint(_in("status", INTRO_STATUSES), name="status"),
        CheckConstraint("outcome_rating BETWEEN 1 AND 5", name="outcome_rating"),
        Index("ix_intro_requests_to_member_status", "to_member", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    from_member: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_member: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    via_member: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_bridge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome_rating: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = _created_at()
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchResult(Base):
    """Precomputed matches (also serves as the match cache)."""

    __tablename__ = "match_results"
    __table_args__ = (
        CheckConstraint(_in("candidate_type", OWNER_TYPES), name="candidate_type"),
        UniqueConstraint(
            "member_id", "candidate_type", "candidate_id", name="uq_match_results_candidate"
        ),
        Index("ix_match_results_member_score", "member_id", text("score DESC")),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_bridge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- Exchange circuits ----------------------------------------------------------------


class Circuit(Base):
    """A loop of members who each help the next one (A helps B, B helps C, C helps A)."""

    __tablename__ = "circuits"
    __table_args__ = (
        CheckConstraint(_in("status", CIRCUIT_STATUSES), name="status"),
        Index("ix_circuits_round_key", "round_key"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    round_key: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "2026-W41"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CircuitLeg(Base):
    """One "giver helps receiver with capability" step of a circuit."""

    __tablename__ = "circuit_legs"
    __table_args__ = (
        CheckConstraint(_in("consent", CONSENT_STATES), name="consent"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),
        UniqueConstraint("circuit_id", "position", name="uq_circuit_legs_position"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    circuit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    giver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_id: Mapped[str] = mapped_column(ForeignKey("capabilities.id"), nullable=False)
    # The giver's consent: each member accepts or declines the leg where they give help.
    consent: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rating: Mapped[int | None] = mapped_column(SmallInteger)


# --- Events ---------------------------------------------------------------------------


class Event(Base):
    """Append-only log of product actions. A database trigger blocks UPDATE and DELETE."""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_type_created_at", "type", "created_at"),
        Index("ix_events_target", "target_type", "target_id"),
        Index("ix_events_actor_id", "actor_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created_at()
