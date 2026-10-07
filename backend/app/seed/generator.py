"""Deterministic seed generator: ~150 startups and ~300 members around a city centre.

Everything comes from one random.Random(seed), so the same inputs always produce the
same dataset. The hand-written demo stories (stories.py) are included unchanged, and
the generator is careful not to break them (see the "guard" comments).
"""

import random
from dataclasses import dataclass

from app.seed.catalog import CAPABILITIES
from app.seed.geo import AREAS, Point, offset
from app.seed.schema import (
    Dataset,
    OpenRole,
    SeedConnection,
    SeedEvent,
    SeedIntro,
    SeedJob,
    SeedMember,
    SeedNeed,
    SeedOffer,
    SeedStartup,
    StartupRecord,
)
from app.seed.stories import (
    FORBIDDEN_CONNECTIONS,
    STORY_JOBS,
    STORY_MEMBER_KEYS,
    story_connections,
    story_members,
    story_startups,
)

N_STARTUPS = 150
N_STUDENTS = 150
N_MENTORS = 38
N_INVESTORS = 22
N_PARTNER_ADMINS = 3

CAP_NAME = {c.id: c.name for c in CAPABILITIES}

# Guard for story 5: only the two story mentors offer regulatory affairs.
NEVER_GENERATED_OFFERS = {"regulatory_affairs", "clinical_trials"}


@dataclass(frozen=True)
class SectorProfile:
    label: str
    roots: tuple[str, ...]
    suffixes: tuple[str, ...]
    products: tuple[str, ...]  # "{name} builds/runs ..." phrases
    traits: tuple[str, ...]
    needs: tuple[str, ...]  # capability ids startups in this sector commonly need
    regulatory_rate: float  # chance a startup here needs regulatory_affairs
    stack: tuple[str, ...]
    roles: tuple[tuple[str, tuple[str, ...]], ...]  # (title, capabilities)
    weight: int


_ENG_ROLES = (
    ("Backend Engineer", ("backend_development",)),
    ("Frontend Engineer", ("frontend_development", "ui_ux_design")),
    ("Full-stack Developer", ("frontend_development", "backend_development")),
    ("Mobile Developer", ("mobile_development",)),
    ("Data Analyst", ("data_analysis",)),
    ("DevOps Engineer", ("devops_cloud",)),
    ("QA Engineer", ("qa_testing",)),
)
_GTM_ROLES = (
    ("Growth Marketer", ("performance_marketing", "marketing")),
    ("Content Writer", ("content_marketing", "technical_writing")),
    ("Social Media Associate", ("social_media_marketing", "video_content")),
    ("Business Development Associate", ("b2b_sales", "partnerships")),
    ("Product Designer", ("ui_ux_design", "brand_design")),
    ("Customer Success Associate", ("customer_success",)),
)

SECTORS: dict[str, SectorProfile] = {
    "fintech": SectorProfile(
        "fintech", ("Ledger", "Rupee", "Paisa", "Credo", "Kosh", "Tally", "Mint", "Vault"),
        ("Pay", "Fin", "Credit", "Money", "Books"),
        ("UPI collections for small merchants", "credit lines for gig workers",
         "expense cards for SMEs", "a savings app for first-time earners"),
        ("b2b", "regulated_market", "venture_backed", "data_intensive", "b2c"),
        ("data_privacy_compliance", "b2b_sales", "fundraising", "backend_development",
         "cybersecurity", "partnerships"),
        0.3, ("Python", "Go", "PostgreSQL", "Kafka", "React", "AWS"), _ENG_ROLES, 14,
    ),
    "healthtech": SectorProfile(
        "healthtech", ("Arogya", "Vaidya", "Pulse", "Care", "Swasth", "Medi", "Nabh"),
        ("Health", "Care", "Clinic", "Labs"),
        ("teleconsults for tier-3 towns", "clinic management software",
         "home sample collection", "chronic care coaching on WhatsApp"),
        ("regulated_market", "b2c", "tier2_tier3_focus", "high_touch_sales"),
        ("healthcare_domain", "data_privacy_compliance", "b2b_sales", "hiring",
         "mobile_development", "partnerships"),
        0.4, ("Kotlin", "Flutter", "Node.js", "PostgreSQL", "FHIR"), _ENG_ROLES, 12,
    ),
    "biotech": SectorProfile(
        "biotech", ("Helix", "Geno", "Cyto", "Enzy", "Proto", "Myco", "Vira"),
        ("Bio", "Genomics", "Therapeutics", "Biosciences"),
        ("microbial fertiliser strains", "low-cost antibody production",
         "point-of-care molecular tests", "enzymes for textile processing"),
        ("deep_science", "long_sales_cycle", "technical_buyers", "regulated_market", "b2b"),
        ("clinical_trials", "fundraising", "ip_patents", "lab_research", "grant_writing",
         "marketing"),
        0.5, ("Python", "R", "LIMS"),
        (("Research Associate", ("lab_research",)), ("Bioinformatics Analyst",
         ("data_analysis", "machine_learning"))), 8,
    ),
    "medtech": SectorProfile(
        "medtech", ("Ortho", "Cardio", "Neuro", "Sense", "Vita", "Opti"),
        ("Devices", "Medical", "Diagnostics", "Labs"),
        ("a portable ECG patch", "AI screening for diabetic retinopathy",
         "low-cost neonatal warmers", "smart insulin pens"),
        ("hardware_heavy", "regulated_market", "long_sales_cycle", "deep_science"),
        ("clinical_trials", "manufacturing", "quality_assurance_mfg", "healthcare_domain",
         "embedded_hardware", "fundraising"),
        0.45, ("C++", "Embedded C", "Python", "PyTorch"),
        (("Embedded Engineer", ("embedded_hardware",)), ("ML Engineer",
         ("machine_learning", "data_analysis"))), 7,
    ),
    "agritech": SectorProfile(
        "agritech", ("Krishi", "Khet", "Anaj", "Fasal", "Mitti", "Beej", "Harit"),
        ("Agro", "Farms", "Grow", "Agri"),
        ("crop advisory over IVR", "farm-gate procurement for FPOs",
         "drone spraying services", "soil testing kits"),
        ("rural_focus", "vernacular_users", "impact_driven", "b2b"),
        ("agriculture_domain", "supply_chain", "partnerships", "government_relations",
         "fundraising", "mobile_development"),
        0.2, ("Flutter", "Python", "PostgreSQL", "IVR"), _ENG_ROLES + _GTM_ROLES[:2], 10,
    ),
    "edtech": SectorProfile(
        "edtech", ("Vidya", "Gyan", "Shiksha", "Pathshala", "Kaksha", "Akshar"),
        ("Learn", "Academy", "School", "Edu"),
        ("vernacular coding courses", "exam prep for state boards",
         "career coaching for college students", "teacher training on mobile"),
        ("b2c", "vernacular_users", "tier2_tier3_focus", "subscription_revenue"),
        ("content_marketing", "performance_marketing", "education_domain", "video_content",
         "community_building", "hiring"),
        0.05, ("React", "Node.js", "MongoDB", "AWS"), _ENG_ROLES + _GTM_ROLES, 10,
    ),
    "climatetech": SectorProfile(
        "climatetech", ("Surya", "Vayu", "Jal", "Prithvi", "Neer", "Hara", "Carbon"),
        ("Energy", "Climate", "Power", "Labs"),
        ("battery swapping for e-rickshaws", "rooftop solar financing",
         "carbon accounting for exporters", "water-saving drip controllers"),
        ("impact_driven", "hardware_heavy", "b2b", "long_sales_cycle"),
        ("fundraising", "energy_domain", "government_relations", "manufacturing",
         "partnerships", "grant_writing"),
        0.15, ("Python", "IoT", "React", "TimescaleDB"), _ENG_ROLES, 10,
    ),
    "deeptech": SectorProfile(
        "deeptech", ("Quanta", "Photon", "Silico", "Ion", "Tensor", "Orbit", "Lumen"),
        ("Labs", "Systems", "Semi", "Space", "Robotics"),
        ("chip-design verification tools", "small-satellite components",
         "warehouse robots", "edge AI accelerators"),
        ("deep_science", "technical_buyers", "long_sales_cycle", "b2b", "hardware_heavy"),
        ("fundraising", "technical_marketing", "enterprise_sales", "ip_patents",
         "embedded_hardware", "hiring"),
        0.15, ("C++", "Rust", "Verilog", "Python", "ROS"),
        (("Firmware Engineer", ("embedded_hardware",)), ("ML Engineer",
         ("machine_learning",)), ("Robotics Intern", ("embedded_hardware",
         "machine_learning"))), 8,
    ),
    "saas": SectorProfile(
        "saas", ("Stack", "Flow", "Desk", "Sync", "Pilot", "Grid", "Loop"),
        ("HQ", "ly", "io", "Works", "Cloud"),
        ("invoicing for agencies", "HR software for factories", "a CRM for real-estate brokers",
         "vendor onboarding for enterprises"),
        ("b2b", "subscription_revenue", "remote_first", "venture_backed"),
        ("b2b_sales", "customer_success", "content_marketing", "pricing_strategy",
         "international_expansion", "frontend_development"),
        0.1, ("TypeScript", "React", "Node.js", "PostgreSQL", "AWS"), _ENG_ROLES + _GTM_ROLES,
        14,
    ),
    "d2c": SectorProfile(
        "d2c", ("Desi", "Chai", "Masala", "Kesar", "Tulsi", "Rangoli", "Mitti"),
        ("Co", "Kitchen", "Wear", "Store", "Brands"),
        ("millet snacks", "handloom sarees online", "Ayurvedic skincare",
         "regional-language children's books"),
        ("b2c", "bootstrapped", "impact_driven"),
        ("performance_marketing", "brand_design", "social_media_marketing", "supply_chain",
         "fundraising"),
        0.15, ("Shopify", "Instagram", "Google Ads"), _GTM_ROLES, 9,
    ),
    "logistics": SectorProfile(
        "logistics", ("Cargo", "Ship", "Route", "Haul", "Dak", "Gati"),
        ("Logistics", "Freight", "Express", "Move"),
        ("last-mile delivery for kirana stores", "truck aggregation", "cold-chain monitoring"),
        ("b2b", "marketplace", "venture_backed", "tier2_tier3_focus"),
        ("operations", "hiring", "b2b_sales", "data_analysis", "partnerships"),
        0.1, ("Kotlin", "Go", "PostgreSQL", "Kafka"), _ENG_ROLES, 7,
    ),
    "foodtech": SectorProfile(
        "foodtech", ("Thali", "Dabba", "Tiffin", "Annam", "Rasoi"),
        ("Foods", "Kitchen", "Eats"),
        ("cloud kitchens for offices", "plant-based paneer", "school meal delivery"),
        ("b2c", "regulated_market", "subscription_revenue"),
        ("supply_chain", "performance_marketing", "operations", "quality_assurance_mfg"),
        0.35, ("React Native", "Node.js", "PostgreSQL"), _GTM_ROLES + _ENG_ROLES[:2], 6,
    ),
    "hrtech": SectorProfile(
        "hrtech", ("Kaam", "Talent", "Hire", "Naukri", "Skill"),
        ("Works", "Jobs", "Hire", "Up"),
        ("hiring for blue-collar jobs", "skills assessments for freshers",
         "payroll for small businesses"),
        ("b2b", "marketplace", "vernacular_users"),
        ("b2b_sales", "hiring", "product_management", "data_analysis"),
        0.05, ("Python", "Django", "React", "PostgreSQL"), _ENG_ROLES + _GTM_ROLES, 6,
    ),
    "legaltech": SectorProfile(
        "legaltech", ("Nyaya", "Vakil", "Kanoon", "Lex", "Adalat"),
        ("Legal", "Law", "Docs"),
        ("contract review for SMEs", "court case tracking", "legal aid chatbots"),
        ("b2b", "data_intensive", "regulated_market"),
        ("machine_learning", "b2b_sales", "legal_contracts", "data_privacy_compliance"),
        0.2, ("Python", "LangChain", "PostgreSQL", "React"), _ENG_ROLES, 4,
    ),
    "mobility": SectorProfile(
        "mobility", ("Chalo", "Yatra", "Ride", "Volt", "Wheel"),
        ("Mobility", "Motors", "EV", "Rides"),
        ("EV fleets for delivery riders", "bus ticketing for small towns",
         "drone deliveries for pharmacies"),
        ("hardware_heavy", "venture_backed", "regulated_market", "tier2_tier3_focus"),
        ("manufacturing", "government_relations", "operations", "fundraising",
         "embedded_hardware"),
        0.3, ("Kotlin", "Python", "IoT"), _ENG_ROLES, 5,
    ),
}  # fmt: skip

FIRST_NAMES = (
    "Aarav", "Aditi", "Akash", "Ananya", "Anil", "Anjali", "Bhavana", "Chetan", "Deepa",
    "Dev", "Divya", "Gaurav", "Harini", "Ishaan", "Jaya", "Karan", "Kiran", "Lavanya",
    "Madhav", "Manasi", "Neha", "Nikhil", "Pooja", "Pranav", "Rahul", "Rekha", "Rishi",
    "Sahana", "Sameer", "Sanjana", "Shreya", "Siddharth", "Sneha", "Suresh", "Tanvi",
    "Tarun", "Uma", "Varun", "Vidya", "Yash", "Zoya", "Imran", "Fatima", "Joseph",
    "Mary", "Gurpreet", "Harpreet", "Tenzin", "Lalit", "Meenakshi", "Naveen", "Pallavi",
    "Raghav", "Sowmya", "Tejas", "Vandana", "Abdul", "Nisha", "Omkar", "Ritu",
)  # fmt: skip
LAST_NAMES = (
    "Agarwal", "Bhat", "Chatterjee", "Das", "D'Souza", "Gowda", "Gupta", "Hegde",
    "Iyengar", "Jain", "Kamath", "Khan", "Kulkarni", "Malhotra", "Menon", "Mishra",
    "Naidu", "Pandey", "Patel", "Pillai", "Prasad", "Rao", "Reddy", "Saxena", "Sen",
    "Shetty", "Singh", "Srinivasan", "Thomas", "Verma", "Yadav", "Banerjee", "Fernandes",
    "Ghosh", "Kapoor", "Mukherjee", "Nair", "Qureshi", "Sinha", "Varghese",
)  # fmt: skip

# (name, tier, area). Tier is only used here to make sure lower-tier colleges have
# plenty of strong students; it is never stored, because we match on skills.
COLLEGES = (
    ("National Institute of Science & Technology", 1, "University Quarter"),
    ("City Engineering College", 2, "University Quarter"),
    ("St. Aloysius College of Arts & Science", 2, "Central Business District"),
    ("Lakeside Institute of Management", 2, "Lakeside"),
    ("Shantinagar Institute of Technology", 3, "West Industrial Estate"),
    ("Government Polytechnic, South Campus", 3, "South Residential"),
    ("Sri Venkateshwara College of Engineering", 3, "North Tech Park"),
    ("Airport Road Women's College", 3, "Airport Road"),
    ("East Point College of Commerce", 3, "East Innovation Hub"),
)

STUDENT_SKILL_POOL = (
    "frontend_development", "backend_development", "mobile_development", "data_analysis",
    "machine_learning", "devops_cloud", "qa_testing", "ui_ux_design", "data_engineering",
    "content_marketing", "social_media_marketing", "video_content", "brand_design",
    "technical_writing", "market_research", "embedded_hardware", "customer_discovery",
)  # fmt: skip

MENTOR_SPECIALTIES = (
    ("marketing", "go_to_market_strategy", "content_marketing"),
    ("b2b_sales", "enterprise_sales", "pricing_strategy"),
    ("hiring", "hr_operations", "culture_building"),
    ("product_management", "ui_ux_design", "customer_discovery"),
    ("technical_architecture", "backend_development", "devops_cloud"),
    ("machine_learning", "data_engineering", "data_analysis"),
    ("legal_contracts", "ip_patents"),
    ("financial_modeling", "accounting_tax", "fundraising"),
    ("operations", "supply_chain", "manufacturing"),
    ("pr_media", "public_speaking", "brand_design"),
    ("leadership_coaching", "culture_building", "business_strategy"),
    ("partnerships", "international_expansion", "go_to_market_strategy"),
    ("community_building", "social_media_marketing", "performance_marketing"),
    ("cybersecurity", "data_privacy_compliance"),
)  # fmt: skip

INVESTOR_OFFERS = (
    "fundraising", "investor_relations", "financial_modeling", "pitch_coaching",
    "business_strategy",
)  # fmt: skip
INVESTOR_NEEDS = ("market_research", "scientific_advisory", "data_analysis")
STAGES = ("idea", "pre-seed", "seed", "seed", "series-a", "series-b")


class _Gen:
    def __init__(self, center: Point, city: str, seed: int):
        self.center = center
        self.city = city
        self.rng = random.Random(seed)
        self.used_names: set[str] = set()
        self.used_domains: set[str] = set()

    # --- helpers -----------------------------------------------------------------------

    def person_name(self) -> str:
        while True:
            name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
            if name not in self.used_names:
                self.used_names.add(name)
                return name

    def near(self, area_name: str, spread_km: float = 1.2) -> Point:
        area = next(a for a in AREAS if a.name == area_name)
        return offset(
            self.center,
            area.east_km + self.rng.gauss(0, spread_km),
            area.north_km + self.rng.gauss(0, spread_km),
        )

    def weighted_area(self) -> str:
        return self.rng.choices([a.name for a in AREAS], [a.startup_weight for a in AREAS])[0]

    def need_text(self, cap: str, context: str) -> str:
        templates = (
            "Looking for help with {cap} as we {ctx}.",
            "Need someone experienced in {cap}; we {ctx}.",
            "We {ctx} and are stuck on {cap}.",
        )
        return self.rng.choice(templates).format(cap=CAP_NAME[cap].lower(), ctx=context)

    def offer_text(self, cap: str, background: str) -> str:
        years = self.rng.randint(3, 15)
        return f"{years} years of {CAP_NAME[cap].lower()} experience, {background}."

    # --- startups ----------------------------------------------------------------------

    def startup(self, sector_id: str) -> SeedStartup:
        prof = SECTORS[sector_id]
        rng = self.rng
        while True:
            name = f"{rng.choice(prof.roots)}{rng.choice(prof.suffixes)}"
            domain = f"{name.lower()}.example"
            if domain not in self.used_domains:
                self.used_domains.add(domain)
                break
        area = self.weighted_area()
        p = self.near(area)
        product = rng.choice(prof.products)
        hiring = rng.random() < 0.55
        roles = []
        if hiring:
            for title, caps in rng.sample(prof.roles, k=min(len(prof.roles), rng.randint(1, 3))):
                kind = "internship" if rng.random() < 0.3 else "full_time"
                roles.append(
                    OpenRole(
                        title=f"{title} Intern" if kind == "internship" else title,
                        type=kind,
                        capabilities=list(caps),
                    )
                )
        context = f"build {product}"
        needs = [
            SeedNeed(cap, self.need_text(cap, context))
            for cap in rng.sample(prof.needs, k=rng.randint(1, 3))
        ]
        if rng.random() < prof.regulatory_rate:
            needs.append(
                SeedNeed("regulatory_affairs", self.need_text("regulatory_affairs", context))
            )
        return SeedStartup(
            record=StartupRecord(
                name=name,
                website_domain=domain,
                description=f"{name} builds {product}.",
                sector=sector_id,
                stage=rng.choice(STAGES),
                address=f"{area}, {self.city}",
                lat=p.lat,
                lng=p.lng,
                hiring=hiring,
                open_roles=roles,
                tech_stack=rng.sample(prof.stack, k=min(len(prof.stack), rng.randint(2, 4))),
            ),
            traits=rng.sample(prof.traits, k=min(len(prof.traits), rng.randint(2, 3))),
            needs=needs,
            view_count=int(rng.expovariate(1 / 12)),
        )

    def founders_for(self, s: SeedStartup, index: int) -> list[SeedMember]:
        rng = self.rng
        sector = s.record.sector
        prof = SECTORS[sector]
        members = []
        titles = [
            (
                "Founder & CEO",
                (
                    "b2b_sales",
                    "business_strategy",
                    "go_to_market_strategy",
                    "partnerships",
                    "product_management",
                ),
            ),
            (
                "Co-founder & CTO",
                (
                    "backend_development",
                    "technical_architecture",
                    "machine_learning",
                    "devops_cloud",
                    "frontend_development",
                ),
            ),
        ]
        for j, (title, offer_pool) in enumerate(titles[: rng.choice((1, 1, 2))]):
            key = f"founder-{index:03d}-{j}"
            name = self.person_name()
            first_time = rng.random() < 0.65
            traits = rng.sample(s.traits, k=min(2, len(s.traits)))
            traits.append("first_time_founder" if first_time else "repeat_founder")
            needs = []
            if j == 0 and s.needs and rng.random() < 0.7:
                need = rng.choice(s.needs)
                needs.append(SeedNeed(need.capability_id, need.text))
            offers = [
                SeedOffer(cap, self.offer_text(cap, f"now building in {prof.label}"))
                for cap in rng.sample(offer_pool, k=rng.randint(1, 2))
            ]
            p = offset(Point(s.record.lat, s.record.lng), rng.gauss(0, 2), rng.gauss(0, 2))
            members.append(
                SeedMember(
                    key=key,
                    role="founder",
                    display_name=name,
                    bio=f"{title} at {s.record.name}. {s.record.description}",
                    lat=p.lat,
                    lng=p.lng,
                    city=self.city,
                    sector=sector,
                    verification_level=rng.choice((1, 2, 2, 3)),
                    open_intro_slots=rng.randint(2, 4),
                    circuits_opt_in=rng.random() < 0.35,
                    traits=traits,
                    needs=needs,
                    offers=offers,
                )
            )
            s.team.append((key, title))
        # Most startups whose team we know have been claimed; the rest are waiting.
        if members and rng.random() < 0.7:
            s.claimed_by = members[0].key
        return members

    # --- people ------------------------------------------------------------------------

    def student(self, i: int) -> SeedMember:
        rng = self.rng
        college, tier, area = rng.choice(COLLEGES)
        p = self.near(area, 1.5)
        k = rng.randint(2, 5)
        # Guard for story 3: lower-tier colleges are not short of strong skills.
        skills = {cap: rng.choice((1, 2, 2, 3)) for cap in rng.sample(STUDENT_SKILL_POOL, k=k)}
        top = max(skills, key=skills.get)
        year = rng.choice(("Second", "Third", "Final"))
        offers = []
        if rng.random() < 0.3:
            offers.append(
                SeedOffer(top, f"Student who can help with {CAP_NAME[top].lower()} projects.")
            )
        return SeedMember(
            key=f"student-{i:03d}",
            role="student",
            display_name=self.person_name(),
            bio=f"{year}-year student at {college}. Into {CAP_NAME[top].lower()}.",
            lat=p.lat,
            lng=p.lng,
            city=self.city,
            college=college,
            verification_level=rng.choice((0, 1, 1, 1, 2)),
            open_intro_slots=2,
            circuits_opt_in=False,
            skills=skills,
            offers=offers,
        )

    def mentor(self, i: int) -> SeedMember:
        rng = self.rng
        sector = rng.choice(list(SECTORS))
        specialty = rng.choice(MENTOR_SPECIALTIES)
        offers = [
            SeedOffer(cap, self.offer_text(cap, f"mostly with {SECTORS[sector].label} teams"))
            for cap in rng.sample(specialty, k=min(len(specialty), rng.randint(2, 3)))
            if cap not in NEVER_GENERATED_OFFERS
        ]
        p = self.near(self.weighted_area(), 2.0)
        needs = []
        if rng.random() < 0.25:
            cap = rng.choice(("community_building", "public_speaking", "market_research"))
            needs.append(SeedNeed(cap, self.need_text(cap, "grow our mentoring practice")))
        return SeedMember(
            key=f"mentor-{i:03d}",
            role="mentor",
            display_name=self.person_name(),
            bio=(
                f"Operator turned mentor with a background in {SECTORS[sector].label}. "
                f"Helps founders with {CAP_NAME[specialty[0]].lower()}."
            ),
            lat=p.lat,
            lng=p.lng,
            city=self.city,
            sector=sector,
            verification_level=rng.choice((2, 2, 3)),
            open_intro_slots=rng.randint(2, 5),
            circuits_opt_in=rng.random() < 0.4,
            traits=rng.sample(SECTORS[sector].traits, k=2),
            needs=needs,
            offers=offers,
        )

    def investor(self, i: int) -> SeedMember:
        rng = self.rng
        sector = rng.choice(list(SECTORS))
        p = self.near("Central Business District", 2.5)
        need = rng.choice(INVESTOR_NEEDS)
        return SeedMember(
            key=f"investor-{i:03d}",
            role="investor",
            display_name=self.person_name(),
            bio=(
                f"{rng.choice(('Angel investor', 'Principal at an early-stage fund', 'Partner at a seed fund'))} "  # noqa: E501
                f"focused on {SECTORS[sector].label}."
            ),
            lat=p.lat,
            lng=p.lng,
            city=self.city,
            sector=sector,
            verification_level=rng.choice((2, 3)),
            open_intro_slots=rng.randint(1, 3),
            circuits_opt_in=rng.random() < 0.2,
            traits=list(
                dict.fromkeys(["venture_backed", *rng.sample(SECTORS[sector].traits, k=1)])
            ),
            needs=[SeedNeed(need, self.need_text(need, "evaluate early-stage deals"))],
            offers=[
                SeedOffer(cap, self.offer_text(cap, f"investing in {SECTORS[sector].label}"))
                for cap in rng.sample(INVESTOR_OFFERS, k=rng.randint(2, 3))
            ],
        )

    def partner_admin(self, i: int) -> SeedMember:
        org = ("City Engineering College placement cell", "Lakeside Startup Foundry",
               "North Tech Park Innovation Council")[i]  # fmt: skip
        p = self.near("University Quarter", 2.0)
        return SeedMember(
            key=f"partner-{i:03d}",
            role="partner_admin",
            display_name=self.person_name(),
            bio=f"Ecosystem lead at {org}.",
            lat=p.lat,
            lng=p.lng,
            city=self.city,
            verification_level=3,
            open_intro_slots=5,
        )

    # --- network -----------------------------------------------------------------------

    def connections(self, members: list[SeedMember], startups: list[SeedStartup]):
        rng = self.rng
        edges: dict[frozenset, SeedConnection] = {}

        def add(a: str, b: str, strength: float, source: str) -> None:
            pair = frozenset((a, b))
            if a == b or pair in FORBIDDEN_CONNECTIONS or pair in edges:
                return
            edges[pair] = SeedConnection(a, b, round(min(max(strength, 0.05), 1.0), 2), source)

        for c in story_connections():
            add(c.a, c.b, c.strength, c.source)

        by_role: dict[str, list[SeedMember]] = {}
        for m in members:
            by_role.setdefault(m.role, []).append(m)
        founders = [m.key for m in by_role["founder"]]
        students = by_role["student"]
        # Story members only get the random ties that keep their stories intact.
        generic_founders = [k for k in founders if k not in STORY_MEMBER_KEYS]

        for s in startups:  # co-founders know each other well
            team = [k for k, _ in s.team]
            for i, a in enumerate(team):
                for b in team[i + 1 :]:
                    add(a, b, 0.9, "cofounders")
        for m in by_role["mentor"]:
            pool = generic_founders + [s.key for s in students]
            degree = 14 if m.key == "lakshmi" else rng.randint(4, 9)
            for other in rng.sample(pool, k=degree):
                add(m.key, other, rng.uniform(0.4, 0.85), "mentored")
        for m in by_role["investor"]:
            for other in rng.sample(generic_founders, k=rng.randint(3, 7)):
                add(m.key, other, rng.uniform(0.3, 0.75), "invested")
            for other in rng.sample(by_role["mentor"], k=2):
                add(m.key, other.key, rng.uniform(0.3, 0.7), "co_invested")
        for a in generic_founders:
            for b in rng.sample(generic_founders, k=rng.randint(1, 3)):
                add(a, b, rng.uniform(0.3, 0.6), "cohort")
        by_college: dict[str, list[str]] = {}
        for s in students:
            by_college.setdefault(s.college or "", []).append(s.key)
        for keys in by_college.values():
            for a in keys:
                for b in rng.sample(keys, k=min(len(keys), rng.randint(1, 3))):
                    add(a, b, rng.uniform(0.3, 0.6), "classmates")
        for m in by_role["partner_admin"]:
            for other in rng.sample(generic_founders, k=10):
                add(m.key, other, rng.uniform(0.3, 0.6), "incubator")
        return list(edges.values())

    def intros(self, members: list[SeedMember]) -> list[SeedIntro]:
        """Past intro requests, so the partner dashboard has history to show."""
        rng = self.rng
        seekers = [
            m
            for m in members
            if m.role in ("founder", "student") and m.key not in STORY_MEMBER_KEYS
        ]
        helpers = [
            m
            for m in members
            if m.role in ("mentor", "investor") and m.key not in STORY_MEMBER_KEYS
        ]
        intros = []
        for i in range(48):
            a, b = rng.choice(seekers), rng.choice(helpers)
            bridge = a.sector is not None and b.sector is not None and a.sector != b.sector
            # Bridge intros are accepted a bit more often in the seed history.
            accepted = rng.random() < (0.68 if bridge else 0.52)
            status = rng.choice(("accepted", "completed")) if accepted else "declined"
            intros.append(
                SeedIntro(
                    key=f"intro-{i:03d}",
                    from_member=a.key,
                    to_member=b.key,
                    via_member=None,
                    status=status,
                    is_bridge=bridge,
                    reason="Seeded history",
                    days_ago=rng.randint(3, 80),
                    outcome_rating=rng.randint(3, 5) if status == "completed" else None,
                )
            )
        return intros

    def interest_events(self, startups: list[SeedStartup], students: list[SeedMember]):
        rng = self.rng
        events = []
        for s in startups:
            if s.record.website_domain == "terragrid.example":
                n = 14  # story 4/F3: an unclaimed startup with visible student interest
            elif s.claimed_by is None:
                n = rng.randint(0, 6)
            else:
                n = rng.randint(0, 3)
            for st in rng.sample(students, k=n):
                events.append(
                    SeedEvent(
                        actor=st.key,
                        type="startup.interest",
                        target_type="startup",
                        target_key=s.record.website_domain,
                        days_ago=round(rng.uniform(0.5, 30), 2),
                    )
                )
        return events


STIPENDS = ("₹8,000/month", "₹10,000/month", "₹12,000/month", "₹15,000/month", "₹25,000/month")
SALARIES = ("₹4–6 LPA", "₹6–9 LPA", "₹8–12 LPA", "₹12–18 LPA")


def jobs_for(s: SeedStartup) -> list[SeedJob]:
    """One job per open role. Uses its own random stream (seeded by the domain) so
    adding jobs never changes the rest of the generated data."""
    rng = random.Random(f"jobs:{s.record.website_domain}")
    jobs = []
    for role in s.record.open_roles:
        story_job = STORY_JOBS.get((s.record.website_domain, role.title))
        if story_job is not None:
            jobs.append(story_job)
            continue
        internship = role.type == "internship"
        paid = not internship or rng.random() < 0.7
        if internship:
            compensation = rng.choice(STIPENDS) if paid else "Unpaid (certificate and letter)"
        else:
            compensation = rng.choice(SALARIES)
        skills = ", ".join(CAP_NAME[c].lower() for c in role.capabilities)
        length = rng.choice(("three", "six")) if internship else None
        description = (
            f"{length.capitalize()}-month internship at {s.record.name}. "
            if length
            else f"Full-time role at {s.record.name}. "
        ) + f"{s.record.description} You'll work on {skills}."
        jobs.append(
            SeedJob(
                title=role.title,
                type=role.type,
                paid=paid,
                compensation=compensation,
                description=description,
                capabilities={
                    c: (rng.choice((1, 2)) if internship else rng.choice((2, 2, 3)))
                    for c in role.capabilities
                },
            )
        )
    return jobs


def build_dataset(center: Point, city: str, seed: int = 42) -> Dataset:
    g = _Gen(center, city, seed)
    g.used_names.update(m.display_name for m in story_members(center, city))
    startups = story_startups(center, city)
    g.used_domains.update(s.record.website_domain for s in startups)
    members = story_members(center, city)

    sector_ids = list(SECTORS)
    weights = [SECTORS[s].weight for s in sector_ids]
    while len(startups) < N_STARTUPS:
        startups.append(g.startup(g.rng.choices(sector_ids, weights)[0]))

    # About 45% of generated startups have a known founding team.
    for i, s in enumerate(startups):
        if not s.team and g.rng.random() < 0.45:
            members.extend(g.founders_for(s, i))

    members.extend(g.student(i) for i in range(N_STUDENTS - 1))  # + Ravi
    members.extend(g.mentor(i) for i in range(N_MENTORS))
    members.extend(g.investor(i) for i in range(N_INVESTORS))
    members.extend(g.partner_admin(i) for i in range(N_PARTNER_ADMINS))

    for s in startups:
        s.jobs = jobs_for(s)

    students = [m for m in members if m.role == "student"]
    return Dataset(
        members=members,
        startups=startups,
        connections=g.connections(members, startups),
        intros=g.intros(members),
        events=g.interest_events(startups, students),
    )
