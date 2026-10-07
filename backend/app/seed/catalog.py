"""The fixed lists of capabilities and traits.

These are the ONLY values the LLM onboarding (F1) may suggest, and the vocabulary that
needs, offers and student skills are expressed in. Changing an id here is a data
migration, so add new entries rather than renaming existing ones.
"""

from typing import NamedTuple


class CapabilityDef(NamedTuple):
    id: str
    name: str
    category: str
    description: str


class TraitDef(NamedTuple):
    id: str
    name: str
    description: str


def _caps(category: str, *rows: tuple[str, str, str]) -> list[CapabilityDef]:
    return [CapabilityDef(id_, name, category, desc) for id_, name, desc in rows]


CAPABILITIES: list[CapabilityDef] = [
    *_caps(
        "engineering",
        ("frontend_development", "Frontend development", "Web UIs with React, Vue or similar."),
        ("backend_development", "Backend development", "APIs, databases and server code."),
        ("mobile_development", "Mobile development", "Android and iOS apps."),
        ("data_engineering", "Data engineering", "Pipelines, warehouses and ETL."),
        ("machine_learning", "Machine learning", "Training and shipping ML models."),
        ("devops_cloud", "DevOps & cloud", "CI/CD, infrastructure and cloud operations."),
        ("cybersecurity", "Cybersecurity", "Security reviews, hardening and incident response."),
        ("embedded_hardware", "Embedded & hardware", "Firmware, electronics and prototyping."),
        ("qa_testing", "QA & testing", "Test plans, automation and release quality."),
        ("data_analysis", "Data analysis", "SQL, dashboards and turning data into decisions."),
        ("technical_architecture", "Technical architecture", "System design and tech choices."),
    ),
    *_caps(
        "product_design",
        ("product_management", "Product management", "Roadmaps, prioritisation and specs."),
        ("ui_ux_design", "UI/UX design", "User research, flows and interface design."),
        ("customer_discovery", "Customer discovery", "Interviews and validating the problem."),
        ("technical_writing", "Technical writing", "Docs, API references and whitepapers."),
    ),
    *_caps(
        "go_to_market",
        ("marketing", "Marketing", "Positioning, campaigns and demand generation."),
        ("technical_marketing", "Technical marketing", "Marketing to engineers and scientists."),
        ("content_marketing", "Content marketing", "Blogs, newsletters and thought leadership."),
        ("performance_marketing", "Performance marketing", "Paid acquisition and funnels."),
        ("social_media_marketing", "Social media marketing", "Organic social and creators."),
        ("brand_design", "Brand & visual design", "Identity, decks and visual storytelling."),
        ("video_content", "Video content", "Shooting and editing product and social video."),
        ("b2b_sales", "B2B sales", "Pipelines, demos and closing business customers."),
        ("enterprise_sales", "Enterprise sales", "Long, multi-stakeholder enterprise deals."),
        ("partnerships", "Partnerships", "Channel, distribution and strategic partners."),
        ("community_building", "Community building", "Growing and engaging a user community."),
        ("pr_media", "PR & media", "Press relations and media coverage."),
        ("customer_success", "Customer success", "Onboarding, retention and expansion."),
        ("pricing_strategy", "Pricing strategy", "Packaging, pricing and monetisation."),
        ("go_to_market_strategy", "Go-to-market strategy", "Choosing segments and channels."),
        ("international_expansion", "International expansion", "Entering new countries."),
    ),
    *_caps(
        "funding_finance",
        ("fundraising", "Fundraising", "Preparing and running a funding round."),
        ("investor_relations", "Investor relations", "Board updates and investor reporting."),
        ("financial_modeling", "Financial modelling", "Projections, unit economics, runway."),
        ("accounting_tax", "Accounting & tax", "Bookkeeping, GST and statutory filings."),
        ("grant_writing", "Grant writing", "Government and foundation grant applications."),
        ("pitch_coaching", "Pitch coaching", "Sharpening the story and the pitch deck."),
    ),
    *_caps(
        "people",
        ("hiring", "Hiring", "Sourcing, interviewing and closing candidates."),
        ("hr_operations", "HR operations", "Payroll, policies and people operations."),
        ("leadership_coaching", "Leadership coaching", "Coaching founders and first managers."),
        ("culture_building", "Culture building", "Values, rituals and team health."),
    ),
    *_caps(
        "legal_regulatory",
        ("regulatory_affairs", "Regulatory affairs", "Approvals from CDSCO, FDA, RBI and others."),
        ("clinical_trials", "Clinical trials", "Designing and running clinical studies."),
        ("legal_contracts", "Legal & contracts", "Company law, contracts and term sheets."),
        ("ip_patents", "IP & patents", "Patent strategy, filings and freedom to operate."),
        ("data_privacy_compliance", "Data privacy & compliance", "DPDP, GDPR, SOC 2, audits."),
        ("government_relations", "Government relations", "Public sector sales and policy."),
    ),
    *_caps(
        "operations",
        ("operations", "Operations", "Processes, vendors and day-to-day execution."),
        ("supply_chain", "Supply chain", "Sourcing, inventory and logistics."),
        ("manufacturing", "Manufacturing", "Contract manufacturing and scaling production."),
        ("quality_assurance_mfg", "Manufacturing quality", "QA systems, ISO and GMP."),
    ),
    *_caps(
        "domain_expertise",
        ("lab_research", "Lab research", "Wet-lab experiments and R&D."),
        ("scientific_advisory", "Scientific advisory", "Review of science and technical claims."),
        ("healthcare_domain", "Healthcare know-how", "Hospitals, clinicians and payers."),
        ("agriculture_domain", "Agriculture know-how", "Farmers, FPOs and agri value chains."),
        ("energy_domain", "Energy & climate know-how", "Grids, renewables and carbon markets."),
        ("financial_services_domain", "Financial services know-how", "Banks, NBFCs, payments."),
        ("education_domain", "Education know-how", "Schools, colleges and learners."),
        ("retail_domain", "Retail & consumer know-how", "Kirana, D2C and consumer brands."),
    ),
    *_caps(
        "strategy",
        ("business_strategy", "Business strategy", "Business models and big decisions."),
        ("market_research", "Market research", "Sizing markets and mapping competitors."),
        ("public_speaking", "Public speaking", "Talks, panels and demo days."),
    ),
]

TRAITS: list[TraitDef] = [
    TraitDef("long_sales_cycle", "Long sales cycle", "Deals take 6+ months to close."),
    TraitDef("technical_buyers", "Technical buyers", "Buyers are engineers or scientists."),
    TraitDef("regulated_market", "Regulated market", "Needs approvals or licences to sell."),
    TraitDef("hardware_heavy", "Hardware heavy", "Physical product, inventory or devices."),
    TraitDef("deep_science", "Deep science", "Built on research years ahead of market."),
    TraitDef("b2b", "Sells to businesses", "Customers are companies."),
    TraitDef("b2c", "Sells to consumers", "Customers are individuals."),
    TraitDef("b2g", "Sells to government", "Customers are public bodies."),
    TraitDef("marketplace", "Marketplace", "Connects two sides, e.g. buyers and sellers."),
    TraitDef("subscription_revenue", "Subscription revenue", "Recurring SaaS-style revenue."),
    TraitDef("bootstrapped", "Bootstrapped", "Growing on revenue, not venture funding."),
    TraitDef("venture_backed", "Venture backed", "Raised from institutional investors."),
    TraitDef("tier2_tier3_focus", "Tier 2/3 focus", "Serves smaller cities and towns."),
    TraitDef("rural_focus", "Rural focus", "Serves villages and rural communities."),
    TraitDef("vernacular_users", "Vernacular users", "Users prefer Indian languages."),
    TraitDef("export_oriented", "Export oriented", "Sells mainly outside India."),
    TraitDef("impact_driven", "Impact driven", "Social or climate impact is core."),
    TraitDef("first_time_founder", "First-time founder", "Building a company for the first time."),
    TraitDef("repeat_founder", "Repeat founder", "Has founded a company before."),
    TraitDef("remote_first", "Remote first", "Team works mostly remotely."),
    TraitDef("open_source", "Open source", "Builds in the open or on open source."),
    TraitDef("data_intensive", "Data intensive", "Value comes from large datasets."),
    TraitDef("high_touch_sales", "High-touch sales", "Sales need demos, pilots and trust."),
    TraitDef("network_effects", "Network effects", "Gets better as more people join."),
    TraitDef("pre_revenue", "Pre-revenue", "No paying customers yet."),
]

CAPABILITY_IDS = frozenset(c.id for c in CAPABILITIES)
TRAIT_IDS = frozenset(t.id for t in TRAITS)
