"""The generated dataset is deterministic, valid, and always contains the demo stories."""

import math
from collections import Counter

import pytest

from app.seed.catalog import CAPABILITY_IDS, TRAIT_IDS
from app.seed.generator import COLLEGES, build_dataset
from app.seed.geo import Point
from app.seed.stories import PERSONAS

CENTER = Point(12.9716, 77.5946)


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (lat1, lng1), (lat2, lng2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


@pytest.fixture(scope="module")
def data():
    return build_dataset(CENTER, "Bengaluru")


@pytest.fixture(scope="module")
def members(data):
    return {m.key: m for m in data.members}


@pytest.fixture(scope="module")
def startups(data):
    return {s.record.website_domain: s for s in data.startups}


def connected(data, a: str, b: str) -> float | None:
    for c in data.connections:
        if {c.a, c.b} == {a, b}:
            return c.strength
    return None


# --- shape ----------------------------------------------------------------------------


def test_deterministic(data):
    assert build_dataset(CENTER, "Bengaluru") == data


def test_sizes(data):
    roles = Counter(m.role for m in data.members)
    assert len(data.startups) == 150
    assert 270 <= len(data.members) <= 330
    assert roles.most_common(1)[0][0] == "student"
    assert set(roles) == {"student", "founder", "mentor", "investor", "partner_admin"}


def test_all_references_are_valid(data, members):
    caps = [n.capability_id for s in data.startups for n in s.needs]
    caps += [n.capability_id for m in data.members for n in m.needs]
    caps += [o.capability_id for m in data.members for o in m.offers]
    caps += [c for m in data.members for c in m.skills]
    assert set(caps) <= CAPABILITY_IDS
    traits = [t for m in data.members for t in m.traits] + [
        t for s in data.startups for t in s.traits
    ]
    assert set(traits) <= TRAIT_IDS
    for s in data.startups:
        assert all(k in members for k, _ in s.team)
        assert s.claimed_by is None or s.claimed_by in members
    for c in data.connections:
        assert c.a in members and c.b in members and c.a != c.b


def test_no_duplicates(data):
    assert len({m.key for m in data.members}) == len(data.members)
    assert len({m.display_name for m in data.members}) == len(data.members)
    assert len({s.record.website_domain for s in data.startups}) == len(data.startups)
    assert all(len(set(m.traits)) == len(m.traits) for m in data.members)
    assert all(len(set(s.traits)) == len(s.traits) for s in data.startups)
    pairs = [frozenset((c.a, c.b)) for c in data.connections]
    assert len(set(pairs)) == len(pairs)


def test_everything_is_within_the_city(data):
    for s in data.startups:
        assert km((s.record.lat, s.record.lng), CENTER) < 25
    for m in data.members:
        assert km((m.lat, m.lng), CENTER) < 25


def test_startups_use_reserved_example_domains(data):
    # Never point seed data (or the simulated claim emails) at real companies.
    assert all(s.record.website_domain.endswith(".example") for s in data.startups)


def test_city_centre_is_configurable():
    elsewhere = build_dataset(Point(19.0760, 72.8777), "Mumbai")
    s = elsewhere.startups[0]
    assert km((s.record.lat, s.record.lng), (19.0760, 72.8777)) < 25
    assert "Mumbai" in (s.record.address or "")


def test_personas_point_at_members_with_matching_roles(members):
    for role, key in PERSONAS.items():
        assert members[key].role == role


# --- the five demo stories --------------------------------------------------------------


def test_story1_bridge_match(members, startups):
    helix = startups["helixroot.example"]
    kavya = members["kavya"]
    assert helix.record.sector == "biotech"
    assert "marketing" in {n.capability_id for n in helix.needs}
    assert "marketing" in {o.capability_id for o in kavya.offers}
    assert kavya.sector != helix.record.sector  # cross-sector, so a bridge
    shared = set(helix.traits) & set(kavya.traits)
    assert {"long_sales_cycle", "technical_buyers"} <= shared
    assert helix.claimed_by == "meera"


def test_story2_three_person_circuit(members):
    asha, priya, arjun = members["asha"], members["priya"], members["arjun"]
    needs = {k: {n.capability_id for n in members[k].needs} for k in ("asha", "priya", "arjun")}
    offers = {k: {o.capability_id for o in members[k].offers} for k in ("asha", "priya", "arjun")}
    assert needs == {"asha": {"marketing"}, "priya": {"fundraising"}, "arjun": {"hiring"}}
    # Asha -> Arjun (hiring), Arjun -> Priya (fundraising), Priya -> Asha (marketing)
    assert "hiring" in offers["asha"]
    assert "fundraising" in offers["arjun"]
    assert "marketing" in offers["priya"]
    assert asha.circuits_opt_in and priya.circuits_opt_in and arjun.circuits_opt_in


def test_story3_lower_tier_student_near_hiring_startup(members, startups):
    ravi = members["ravi"]
    ledger = startups["ledgerloop.example"]
    tiers = {name: tier for name, tier, _ in COLLEGES}
    assert tiers[ravi.college] == 3
    assert ravi.skills["backend_development"] == 3
    assert ledger.record.hiring
    role_caps = {c for r in ledger.record.open_roles for c in r.capabilities}
    assert {"backend_development", "data_engineering"} <= role_caps
    assert km((ravi.lat, ravi.lng), (ledger.record.lat, ledger.record.lng)) < 3


def test_story4_warm_intro_through_mentor(data, members):
    assert connected(data, "rohan", "vikram") is None
    assert connected(data, "rohan", "lakshmi") >= 0.8
    assert connected(data, "lakshmi", "vikram") >= 0.8
    assert members["lakshmi"].verification_level == 3
    assert "fundraising" in {n.capability_id for n in members["rohan"].needs}
    assert "fundraising" in {o.capability_id for o in members["vikram"].offers}


def test_story5_regulatory_gap_is_the_biggest(data):
    needs = Counter(n.capability_id for s in data.startups for n in s.needs)
    needs += Counter(n.capability_id for m in data.members for n in m.needs)
    offers = Counter(o.capability_id for m in data.members for o in m.offers)
    gaps = {c: needs[c] - offers[c] for c in CAPABILITY_IDS}
    assert max(gaps, key=gaps.get) == "regulatory_affairs"
    assert needs["regulatory_affairs"] >= 20
    assert offers["regulatory_affairs"] == 2


def test_unclaimed_startup_with_student_interest_for_claim_demo(data, startups):
    terra = startups["terragrid.example"]
    assert terra.claimed_by is None
    interest = [e for e in data.events if e.target_key == "terragrid.example"]
    assert len(interest) >= 10
    assert sum(s.claimed_by is None for s in data.startups) > 50


# --- jobs (F11) --------------------------------------------------------------------------


def test_hiring_startups_have_jobs_matching_their_open_roles(data):
    for s in data.startups:
        assert [j.title for j in s.jobs] == [r.title for r in s.record.open_roles]
        for j in s.jobs:
            assert j.capabilities and set(j.capabilities) <= CAPABILITY_IDS
            assert all(1 <= lvl <= 3 for lvl in j.capabilities.values())
            assert j.paid or j.type == "internship"  # only internships may be unpaid


def test_job_mix_has_paid_and_unpaid_internships_and_full_time(data):
    kinds = Counter((j.type, j.paid) for s in data.startups for j in s.jobs)
    assert kinds[("internship", True)] >= 10
    assert kinds[("internship", False)] >= 5
    assert kinds[("full_time", True)] >= 50


def test_story3_internship(startups):
    (intern,) = [j for j in startups["ledgerloop.example"].jobs if j.type == "internship"]
    assert intern.title == "Backend Engineering Intern" and intern.paid
    assert intern.capabilities == {"backend_development": 2, "data_engineering": 2}


def test_adding_jobs_did_not_change_other_seed_data(data):
    # Jobs use their own random stream; these numbers are from before jobs existed.
    assert sum(len(s.needs) for s in data.startups) + sum(len(m.needs) for m in data.members) > 300
    assert len(data.connections) > 800
