"""Shapes of seed data.

StartupRecord is the contract a future web crawler will produce; the seed generator
emits exactly the same shape so the loader doesn't care where a record came from.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.seed.catalog import CAPABILITY_IDS

RoleType = Literal["full_time", "part_time", "internship", "contract"]


class OpenRole(BaseModel):
    title: str
    type: RoleType = "full_time"
    capabilities: list[str] = Field(default_factory=list)

    @field_validator("capabilities")
    @classmethod
    def _known_capabilities(cls, value: list[str]) -> list[str]:
        unknown = set(value) - CAPABILITY_IDS
        if unknown:
            raise ValueError(f"unknown capabilities: {sorted(unknown)}")
        return value


class StartupRecord(BaseModel):
    """One startup as a crawler would report it."""

    name: str
    website_domain: str
    description: str
    sector: str
    stage: str | None = None
    address: str | None = None
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    hiring: bool = False
    open_roles: list[OpenRole] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    source: Literal["seed", "crawler", "user"] = "seed"

    @field_validator("website_domain")
    @classmethod
    def _normalise_domain(cls, value: str) -> str:
        return value.strip().lower().removeprefix("www.")


@dataclass
class SeedNeed:
    capability_id: str
    text: str


@dataclass
class SeedOffer:
    capability_id: str
    text: str


@dataclass
class SeedStartup:
    """A crawler-shaped record plus what our platform knows on top of it."""

    record: StartupRecord
    traits: list[str] = field(default_factory=list)
    needs: list[SeedNeed] = field(default_factory=list)
    team: list[tuple[str, str]] = field(default_factory=list)  # (member key, title)
    claimed_by: str | None = None  # member key
    view_count: int = 0


@dataclass
class SeedMember:
    key: str  # stable handle, e.g. "asha"; the UUID is derived from it
    role: str
    display_name: str
    bio: str
    lat: float
    lng: float
    city: str
    sector: str | None = None
    college: str | None = None
    verification_level: int = 1
    open_intro_slots: int = 3
    circuits_opt_in: bool = False
    traits: list[str] = field(default_factory=list)
    skills: dict[str, int] = field(default_factory=dict)  # capability id -> level 1..3
    needs: list[SeedNeed] = field(default_factory=list)
    offers: list[SeedOffer] = field(default_factory=list)


@dataclass
class SeedConnection:
    a: str  # member key
    b: str
    strength: float
    source: str


@dataclass
class SeedIntro:
    key: str
    from_member: str
    to_member: str
    via_member: str | None
    status: str
    is_bridge: bool
    reason: str
    days_ago: int
    outcome_rating: int | None = None


@dataclass
class SeedEvent:
    actor: str | None  # member key
    type: str
    target_type: str | None
    target_key: str | None  # member key or startup domain
    days_ago: float
    payload: dict = field(default_factory=dict)


@dataclass
class Dataset:
    members: list[SeedMember]
    startups: list[SeedStartup]
    connections: list[SeedConnection]
    intros: list[SeedIntro]
    events: list[SeedEvent]
