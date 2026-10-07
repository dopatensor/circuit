"""The five scripted demo stories. These records are written by hand so the demo
always shows our differentiator, whatever the random generator produces around them.

1. Bridge match: a biotech startup needing marketing ↔ a deep-tech marketer
   (shared traits: long sales cycle, technical buyers).
2. Exchange circuit: Asha needs marketing, Priya needs fundraising, Arjun needs hiring.
   Asha helps Arjun with hiring, Arjun helps Priya with fundraising, Priya helps Asha
   with marketing.
3. A student from a lower-tier college with strong skills ↔ a nearby hiring startup.
4. Warm intro: founder Rohan reaches investor Vikram through respected mentor Lakshmi.
5. Capability gap: many needs for regulatory affairs, very few offers (the generator
   adds most of the needs; the only two offers in the whole dataset live here).
"""

from app.seed.geo import AREA_BY_NAME, Point, offset
from app.seed.schema import (
    OpenRole,
    SeedConnection,
    SeedJob,
    SeedMember,
    SeedNeed,
    SeedOffer,
    SeedStartup,
    StartupRecord,
)

# Which seeded member each persona in the demo switcher logs in as.
PERSONAS: dict[str, str] = {
    "student": "ravi",
    "founder": "meera",
    "mentor": "lakshmi",
    "investor": "vikram",
    "partner_admin": "nandini",
}

# The five demo stories, in demo order (DEMO.md follows the same order).
DEMO_STORIES: dict[int, str] = {
    1: "Bridge match",
    2: "Exchange circuit",
    3: "Student hired on skills",
    4: "Warm intro",
    5: "Ecosystem gaps",
}

# Everyone the demo switcher offers, in display order: (key, story number, their part).
DEMO_PERSONAS: list[tuple[str, int, str]] = [
    ("meera", 1, "Biotech founder who needs marketing"),
    ("kavya", 1, "Deep-tech marketer, matched across sectors"),
    ("asha", 2, "Needs marketing, offers hiring"),
    ("priya", 2, "Needs fundraising, offers marketing"),
    ("arjun", 2, "Needs hiring, offers fundraising"),
    ("ravi", 3, "Student from a lower-tier college with strong skills"),
    ("deepak", 3, "LedgerLoop founder who shortlists Ravi"),
    ("rohan", 4, "Climate founder who wants an intro to Vikram"),
    ("lakshmi", 4, "Respected mentor who knows them both"),
    ("vikram", 4, "Climate investor"),
    ("nandini", 5, "Incubator lead who sees the ecosystem's gaps"),
]

# Keys of all hand-written members; the generator never uses these.
STORY_MEMBER_KEYS = {
    "meera", "kavya", "asha", "priya", "arjun", "ravi", "rohan", "lakshmi", "vikram",
    "sunil", "farah", "nandini", "deepak",
}  # fmt: skip

# Pairs that must never be directly connected, or the warm-intro story disappears.
FORBIDDEN_CONNECTIONS = {frozenset({"rohan", "vikram"})}

HELIX = "helixroot.example"
LEDGERLOOP = "ledgerloop.example"
TERRAGRID = "terragrid.example"
KHADI = "khadikraft.example"
SUNCRATE = "suncrate.example"
SHIFTLY = "shiftly.example"


def _at(center: Point, area: str, east: float = 0.0, north: float = 0.0) -> Point:
    a = AREA_BY_NAME[area]
    return offset(center, a.east_km + east, a.north_km + north)


def story_startups(center: Point, city: str) -> list[SeedStartup]:
    helix = _at(center, "North Tech Park", 0.4, -0.3)
    ledger = _at(center, "West Industrial Estate", 0.9, 0.6)
    terra = _at(center, "East Innovation Hub", -0.5, 0.4)
    khadi = _at(center, "Old Market", 0.3, 0.2)
    sun = _at(center, "Lakeside", -0.6, 0.5)
    shiftly = _at(center, "Central Business District", 0.7, -0.4)
    return [
        # Story 1 — biotech that needs marketing.
        SeedStartup(
            record=StartupRecord(
                name="HelixRoot Biosciences",
                website_domain=HELIX,
                description=(
                    "Enzyme-based rapid diagnostics for hospital labs. Our test detects "
                    "sepsis markers in 40 minutes instead of two days."
                ),
                sector="biotech",
                stage="seed",
                address=f"North Tech Park, {city}",
                lat=helix.lat,
                lng=helix.lng,
                hiring=True,
                open_roles=[
                    OpenRole(
                        title="Research Associate",
                        capabilities=["lab_research", "data_analysis"],
                    ),
                    OpenRole(
                        title="Product Marketing Lead",
                        capabilities=["technical_marketing", "marketing"],
                    ),
                ],
                tech_stack=["Python", "R", "LIMS"],
            ),
            traits=[
                "long_sales_cycle",
                "technical_buyers",
                "deep_science",
                "regulated_market",
                "b2b",
                "high_touch_sales",
            ],  # fmt: skip
            needs=[
                SeedNeed(
                    "marketing",
                    "We need a marketer who can explain enzyme diagnostics to hospital lab "
                    "heads and pharma R&D teams. Our sales cycles run 12 to 18 months.",
                ),
                SeedNeed(
                    "regulatory_affairs",
                    "Need guidance on CDSCO approval for an in-vitro diagnostic device.",
                ),
                SeedNeed("clinical_trials", "Designing a multi-site validation study."),
            ],
            team=[("meera", "Founder & CEO")],
            claimed_by="meera",
            view_count=38,
        ),
        # Story 3 — nearby hiring startup for the student.
        SeedStartup(
            record=StartupRecord(
                name="LedgerLoop",
                website_domain=LEDGERLOOP,
                description=(
                    "Bookkeeping and GST filing on WhatsApp for small manufacturers in "
                    "industrial estates."
                ),
                sector="fintech",
                stage="seed",
                address=f"West Industrial Estate, {city}",
                lat=ledger.lat,
                lng=ledger.lng,
                hiring=True,
                open_roles=[
                    OpenRole(
                        title="Backend Engineering Intern",
                        type="internship",
                        capabilities=["backend_development", "data_engineering"],
                    ),
                    OpenRole(
                        title="Junior Backend Engineer",
                        capabilities=["backend_development", "devops_cloud"],
                    ),
                ],
                tech_stack=["Python", "FastAPI", "PostgreSQL", "Docker", "WhatsApp API"],
            ),
            traits=["b2b", "tier2_tier3_focus", "vernacular_users", "bootstrapped"],
            needs=[
                SeedNeed("backend_development", "Hiring backend engineers who ship fast."),
                SeedNeed("data_engineering", "Turning invoice photos into clean GST data."),
            ],
            team=[("deepak", "Co-founder & CTO")],
            claimed_by="deepak",
            view_count=21,
        ),
        # Story 4 — Rohan's startup. Unclaimed on purpose: the claim-flow demo.
        SeedStartup(
            record=StartupRecord(
                name="TerraGrid Energy",
                website_domain=TERRAGRID,
                description=(
                    "Software that lets housing societies pool rooftop solar and sell "
                    "surplus power back to the grid."
                ),
                sector="climatetech",
                stage="pre-seed",
                address=f"East Innovation Hub, {city}",
                lat=terra.lat,
                lng=terra.lng,
                hiring=True,
                open_roles=[
                    OpenRole(
                        title="Full-stack Developer",
                        capabilities=["frontend_development", "backend_development"],
                    ),
                    OpenRole(
                        title="Energy Data Analyst Intern",
                        type="internship",
                        capabilities=["data_analysis", "energy_domain"],
                    ),
                ],
                tech_stack=["TypeScript", "React", "Node.js", "TimescaleDB"],
            ),
            traits=["b2c", "impact_driven", "first_time_founder", "pre_revenue"],
            needs=[
                SeedNeed("fundraising", "Raising a pre-seed round to scale beyond 12 societies.")
            ],
            team=[("rohan", "Founder")],
            claimed_by=None,
            view_count=63,
        ),
        # Story 2 — the three circuit founders' startups.
        SeedStartup(
            record=StartupRecord(
                name="KhadiKraft",
                website_domain=KHADI,
                description="Direct-to-consumer handloom clothing sourced from weaver clusters.",
                sector="d2c",
                stage="seed",
                address=f"Old Market, {city}",
                lat=khadi.lat,
                lng=khadi.lng,
                hiring=False,
                tech_stack=["Shopify", "Instagram"],
            ),
            traits=["b2c", "impact_driven", "rural_focus"],
            team=[("asha", "Founder")],
            claimed_by="asha",
            view_count=12,
        ),
        SeedStartup(
            record=StartupRecord(
                name="SunCrate",
                website_domain=SUNCRATE,
                description="Solar-powered cold storage boxes rented to vegetable vendors.",
                sector="climatetech",
                stage="pre-seed",
                address=f"Lakeside, {city}",
                lat=sun.lat,
                lng=sun.lng,
                hiring=False,
                tech_stack=["IoT", "Python"],
            ),
            traits=["hardware_heavy", "impact_driven", "tier2_tier3_focus"],
            team=[("priya", "Co-founder & CEO")],
            claimed_by="priya",
            view_count=9,
        ),
        SeedStartup(
            record=StartupRecord(
                name="Shiftly",
                website_domain=SHIFTLY,
                description="Same-day staffing for warehouses and dark stores.",
                sector="logistics",
                stage="series-a",
                address=f"Central Business District, {city}",
                lat=shiftly.lat,
                lng=shiftly.lng,
                hiring=True,
                open_roles=[
                    OpenRole(title="Talent Acquisition Lead", capabilities=["hiring"]),
                    OpenRole(title="Operations Manager", capabilities=["operations"]),
                ],
                tech_stack=["Kotlin", "Go", "PostgreSQL"],
            ),
            traits=["b2b", "marketplace", "venture_backed", "repeat_founder"],
            team=[("arjun", "Founder & CEO")],
            claimed_by="arjun",
            view_count=17,
        ),
    ]


# Story 3: the internship Ravi should match best. Jobs for the other story startups are
# derived from their open roles like everyone else's.
STORY3_JOB_TITLE = "Backend Engineering Intern"
STORY_JOBS: dict[tuple[str, str], SeedJob] = {
    (LEDGERLOOP, STORY3_JOB_TITLE): SeedJob(
        title=STORY3_JOB_TITLE,
        type="internship",
        paid=True,
        compensation="₹20,000/month",
        description=(
            "Six-month internship on the team that turns photos of handwritten invoices "
            "into GST-ready data. You'll build FastAPI endpoints and data pipelines on "
            "Postgres, and ship to real shop owners in the first month. We hire for "
            "skills, not college names."
        ),
        capabilities={"backend_development": 2, "data_engineering": 2},
    ),
}


def story_members(center: Point, city: str) -> list[SeedMember]:
    def m(key: str, area: str, east: float = 0.0, north: float = 0.0, **kw) -> SeedMember:
        p = _at(center, area, east, north)
        return SeedMember(key=key, lat=p.lat, lng=p.lng, city=city, **kw)

    return [
        # --- Story 1 ---
        m(
            "meera",
            "North Tech Park",
            0.2,
            -0.6,
            role="founder",
            display_name="Dr. Meera Iyer",
            sector="biotech",
            bio=(
                "Biochemist turned founder. Built HelixRoot's sepsis test from my PhD lab "
                "work; now trying to get it into hospital labs."
            ),
            verification_level=3,
            open_intro_slots=3,
            circuits_opt_in=False,
            traits=["long_sales_cycle", "technical_buyers", "deep_science", "first_time_founder"],
            needs=[
                SeedNeed(
                    "marketing",
                    "Looking for a marketer who understands technical buyers and long sales "
                    "cycles to help us reach hospital lab heads.",
                )
            ],
            offers=[SeedOffer("lab_research", "Happy to review assay design and lab workflows.")],
        ),  # fmt: skip
        m(
            "kavya",
            "Central Business District",
            -0.8,
            1.1,
            role="mentor",
            display_name="Kavya Menon",
            sector="deeptech",
            bio=(
                "Ran marketing for a chip-design software company selling to engineering "
                "teams at semiconductor firms. Enterprise deals took 18 months."
            ),
            verification_level=3,
            open_intro_slots=4,
            circuits_opt_in=True,
            traits=["long_sales_cycle", "technical_buyers", "b2b", "high_touch_sales"],
            offers=[
                SeedOffer(
                    "technical_marketing",
                    "I help deep-tech teams position complex products for expert buyers.",
                ),
                SeedOffer(
                    "marketing",
                    "Positioning and demand generation for long, technical B2B sales cycles.",
                ),
            ],
        ),  # fmt: skip
        # --- Story 2 (the circuit) ---
        m(
            "asha",
            "Old Market",
            0.5,
            0.6,
            role="founder",
            display_name="Asha Reddy",
            sector="d2c",
            bio=(
                "Founder of KhadiKraft. Before that I ran campus hiring for a 2,000-person "
                "IT services firm."
            ),
            verification_level=2,
            open_intro_slots=3,
            circuits_opt_in=True,
            traits=["b2c", "impact_driven", "first_time_founder"],
            needs=[
                SeedNeed(
                    "marketing",
                    "Need help with brand storytelling and Instagram growth for handloom.",
                )
            ],
            offers=[
                SeedOffer(
                    "hiring",
                    "I can set up your hiring pipeline: sourcing, interviews and offers.",
                )
            ],
        ),  # fmt: skip
        m(
            "priya",
            "Lakeside",
            -0.2,
            0.9,
            role="founder",
            display_name="Priya Sharma",
            sector="climatetech",
            bio=(
                "Co-founder of SunCrate. Spent six years as a brand manager at a consumer "
                "goods company before going full-time on climate."
            ),
            verification_level=2,
            open_intro_slots=3,
            circuits_opt_in=True,
            traits=["impact_driven", "hardware_heavy", "first_time_founder"],
            needs=[SeedNeed("fundraising", "First-time fundraiser preparing a pre-seed round.")],
            offers=[
                SeedOffer(
                    "marketing",
                    "Consumer brand building: positioning, campaigns and social content.",
                )
            ],
        ),  # fmt: skip
        m(
            "arjun",
            "Central Business District",
            0.9,
            -0.1,
            role="founder",
            display_name="Arjun Nair",
            sector="logistics",
            bio=(
                "Second-time founder (Shiftly). Raised seed and Series A, happy to share "
                "what worked. Now scaling the team fast."
            ),
            verification_level=3,
            open_intro_slots=3,
            circuits_opt_in=True,
            traits=["b2b", "marketplace", "repeat_founder", "venture_backed"],
            needs=[
                SeedNeed("hiring", "Need to hire 15 operations staff and 2 engineers this quarter.")
            ],
            offers=[
                SeedOffer(
                    "fundraising",
                    "I can review your deck and help you run a tight fundraising process.",
                )
            ],
        ),  # fmt: skip
        # --- Story 3 (student) ---
        m(
            "ravi",
            "West Industrial Estate",
            0.1,
            -0.2,
            role="student",
            display_name="Ravi Kumar",
            sector=None,
            college="Shantinagar Institute of Technology",
            bio=(
                "Final-year CSE student. Built a GST invoice parser used by 40 shops in my "
                "neighbourhood, plus a Dockerised FastAPI backend for it."
            ),
            verification_level=2,  # LinkedIn linked, so the demo can show his matches
            open_intro_slots=2,
            circuits_opt_in=False,
            skills={
                "backend_development": 3,
                "data_engineering": 3,
                "devops_cloud": 2,
                "data_analysis": 2,
            },
        ),  # fmt: skip
        m(
            "deepak",
            "West Industrial Estate",
            1.2,
            0.3,
            role="founder",
            display_name="Deepak Joshi",
            sector="fintech",
            bio="CTO at LedgerLoop. We hire for skills, not college names.",
            verification_level=2,
            open_intro_slots=3,
            circuits_opt_in=False,
            traits=["b2b", "tier2_tier3_focus", "bootstrapped"],
            offers=[
                SeedOffer("backend_development", "Can mentor on Python backends and Postgres.")
            ],
        ),  # fmt: skip
        # --- Story 4 (warm intro) ---
        m(
            "rohan",
            "East Innovation Hub",
            -0.3,
            0.8,
            role="founder",
            display_name="Rohan Mehta",
            sector="climatetech",
            bio="Founder of TerraGrid. Ex-grid engineer. First time raising money.",
            verification_level=3,
            open_intro_slots=3,
            circuits_opt_in=False,
            traits=["impact_driven", "first_time_founder", "pre_revenue"],
            needs=[
                SeedNeed(
                    "fundraising",
                    "Looking for a climate-focused investor for our pre-seed round.",
                )
            ],
            offers=[SeedOffer("energy_domain", "Can explain grid regulation and net metering.")],
        ),  # fmt: skip
        m(
            "lakshmi",
            "University Quarter",
            0.4,
            -0.2,
            role="mentor",
            display_name="Dr. Lakshmi Narayan",
            sector="climatetech",
            bio=(
                "Former director of a national energy research lab. Has mentored 60+ "
                "climate founders over the last decade."
            ),
            verification_level=3,
            open_intro_slots=6,
            circuits_opt_in=False,
            traits=["deep_science", "impact_driven", "b2g"],
            offers=[
                SeedOffer("scientific_advisory", "Technical diligence for energy hardware."),
                SeedOffer("leadership_coaching", "Coaching first-time founders."),
                SeedOffer("government_relations", "Navigating state energy departments."),
            ],
        ),  # fmt: skip
        m(
            "vikram",
            "Central Business District",
            -0.4,
            0.5,
            role="investor",
            display_name="Vikram Shah",
            sector="climatetech",
            bio="Partner at a climate fund writing pre-seed and seed cheques.",
            verification_level=3,
            open_intro_slots=2,
            circuits_opt_in=False,
            traits=["impact_driven", "venture_backed"],
            needs=[SeedNeed("scientific_advisory", "Help assessing hardware claims in pitches.")],
            offers=[
                SeedOffer("fundraising", "Pre-seed and seed funding for climate startups."),
                SeedOffer("financial_modeling", "Building a credible energy-project model."),
            ],
        ),  # fmt: skip
        # --- Story 5: the only two regulatory_affairs offers in the dataset ---
        m(
            "sunil",
            "Lakeside",
            0.8,
            -0.7,
            role="mentor",
            display_name="Dr. Sunil Bhat",
            sector="medtech",
            bio="Spent 12 years reviewing medical device dossiers for the national regulator.",
            verification_level=3,
            open_intro_slots=2,
            circuits_opt_in=False,
            traits=["regulated_market", "long_sales_cycle"],
            offers=[
                SeedOffer(
                    "regulatory_affairs",
                    "CDSCO medical device and diagnostics approvals, end to end.",
                )
            ],
        ),  # fmt: skip
        m(
            "farah",
            "Central Business District",
            1.3,
            0.8,
            role="mentor",
            display_name="Farah Siddiqui",
            sector="fintech",
            bio="Compliance head at a payments company; RBI licensing and audits.",
            verification_level=2,
            open_intro_slots=2,
            circuits_opt_in=False,
            traits=["regulated_market", "b2b"],
            offers=[
                SeedOffer("regulatory_affairs", "RBI licensing, PA/PG and NBFC compliance."),
                SeedOffer("data_privacy_compliance", "DPDP readiness and SOC 2 audits."),
            ],
        ),  # fmt: skip
        # --- Partner admin persona ---
        m(
            "nandini",
            "University Quarter",
            -0.3,
            0.3,
            role="partner_admin",
            display_name="Nandini Rao",
            sector=None,
            bio="Programme lead at Ankur Incubation Centre, which supports 40 startups a year.",
            verification_level=3,
            open_intro_slots=5,
            circuits_opt_in=False,
        ),  # fmt: skip
    ]


def story_connections() -> list[SeedConnection]:
    return [
        # Story 4: Rohan and Vikram are both close to Lakshmi, but not to each other.
        SeedConnection("rohan", "lakshmi", 0.9, "mentored"),
        SeedConnection("lakshmi", "vikram", 0.9, "worked_together"),
        # Story 1: a mutual for the bridge match, a little weaker.
        SeedConnection("meera", "nandini", 0.7, "incubator"),
        SeedConnection("kavya", "nandini", 0.6, "event"),
        # Story 3
        SeedConnection("deepak", "nandini", 0.5, "incubator"),
        # Story 2: the three know of each other only loosely.
        SeedConnection("asha", "nandini", 0.5, "incubator"),
        SeedConnection("priya", "nandini", 0.5, "incubator"),
    ]
