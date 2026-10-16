# Circuit — MVP build spec (start from scratch)

## Purpose of this MVP
Circuit is a startup ecosystem platform. This MVP exists to support OUTREACH: we will
demo it live to colleges, incubators, founders and investors. Every feature must make
our differentiator visible within a 5-minute demo. Polish the demo path over breadth.

Our differentiator, in one line: we match people on what they NEED and what they can
OFFER (not on sector or job titles), across sectors, with exchange circuits and a map
of who is hiring nearby.

Two sides of the product:
1. Students (often from lower-tier colleges) find nearby startups that are hiring, on
   a map, and get matched on skills rather than college name.
2. Founders, mentors and investors get matched on needs and offers, including
   cross-sector "bridge" matches, warm intros and 3-person exchange circuits.
Plus: partners (colleges, incubators) see a dashboard of what their ecosystem lacks.

Web crawling is OUT of scope. Use seed data shaped like future crawler output.

## How to work with me
- I'm learning backend and frontend development. After each phase, explain what you
  built and why in plain language, including concepts I might not know.
- Work in the phases below, in order. At the end of each phase: run tests, commit
  with a clear message, summarise, and STOP for my OK.
- Keep it simple: one repo, one backend app, one frontend app. No microservices.
- Ask before adding any dependency not listed below.
- Never commit secrets. Use .env (gitignored) and provide .env.example.
- I develop on Windows (WSL2, x86_64) and macOS (Apple Silicon, ARM64). Everything
  must run on both; verify every Docker image supports both architectures.

## Stack
Backend (/backend)
- Python 3.12 with uv; FastAPI; Pydantic v2
- SQLAlchemy 2 (async) + Alembic; psycopg 3
- Postgres 16 with PostGIS and pgvector. Build our own Dockerfile FROM postgres:16
  installing both from the PGDG apt repo (works on ARM64 and x86_64).
- GeoAlchemy2, pgvector-python
- fastembed with BAAI/bge-small-en-v1.5 (384 dims) behind an EmbeddingProvider
  interface, plus a deterministic fake provider for tests
- anthropic SDK, model claude-haiku-4-5-20251001, for onboarding extraction only
  (API key in .env; the app must still work without it, falling back to manual pickers)
- networkx for finding exchange cycles; OR-Tools CP-SAT for choosing circuits
- APScheduler for scheduled jobs; structlog for JSON logs; pytest + httpx

Frontend (/frontend)
- React + TypeScript + Vite; Tailwind CSS
- MapLibre GL JS with free OpenStreetMap-based tiles (no paid map key required)
- TanStack Query for data fetching; a TypeScript client generated from the backend's
  OpenAPI spec (openapi-typescript) so no API calls are hand-written
- Recharts for dashboard charts

Infra (production details in PRODUCTION.md, which overrides anything here)
- docker compose locally: Postgres (PostGIS + pgvector), Redis, Neo4j
- Production: FastAPI on Google Cloud Run (asia-south1); Cloud Run Jobs +
  Cloud Scheduler for background work; Supabase (Postgres, Auth, Storage,
  Realtime); Redis (Upstash or Memorystore); Neo4j AuraDB; frontend on Vercel

Redis and Neo4j are IN scope for the pilot, each behind an interface (cache/,
graph/). Neither is ever the source of truth: Postgres is. If either is down, the
app falls back (Postgres reads; recursive SQL / networkx) and logs a warning.

## Features (all must be demoable)
F1. Smart onboarding: user pastes a bio or describes their startup; the LLM suggests
    needs, offers, capabilities and traits FROM OUR FIXED LISTS ONLY; user confirms
    or edits with tap-to-select chips. Manual pickers if no API key.
F2. Startup map for students: map of startups, filters for hiring, capability and
    distance; pins coloured by hiring status; popup with sector, open roles and a
    "match to my skills" score; "I'm interested" button (logged as an event).
F3. Unclaimed profiles + claim: seeded startups start unclaimed. A founder can claim
    one (MVP: confirm via an email on the startup's domain, simulated in dev). The
    startup shows how many students viewed or showed interest, to motivate claiming.
F4. Matches with reasons: each member sees ranked matches, each with a one-line
    reason built from the score components. Cross-sector matches carry a visible
    "Bridge match" badge.
F5. Warm intros: for any match, show the best mutual connection (1-2 hops, recursive
    SQL). Intro requests go via the mutual when one exists. Capacity limits per
    person per week; requests beyond capacity are refused politely.
F6. Exchange circuits: weekly round (plus an admin "Run round now" button for demos).
    Build CAN_HELP edges, find 3-person cycles with networkx, score by weakest link,
    choose non-overlapping circuits with CP-SAT. Members see a loop card ("You help
    X with A, X helps Y with B, Y helps you with C") and accept or decline within 72h.
F7. Verification badges: levels 1-3 shown as badges on profiles. Level rules:
    1 email verified (browse), 2 work email or LinkedIn link (matches),
    3 role verified by admin (intros). Admin can set levels in the MVP.
F8. Partner dashboard: gap map (per capability: active needs vs active offers, as a
    ranked chart and as a map heat layer by area), network stats, and intro
    acceptance rate split by local vs bridge matches.
F9. Demo mode: a persona switcher in the header (dev/demo only) to instantly log in
    as a prepared student, founder, mentor or partner admin. A one-command
    "reset demo" that restores the seed data to a known state before every demo.
F11. Jobs and applications: a jobs list (filter by role, skill, distance, paid or
    unpaid, internship or full-time) and a job page showing the startup, role,
    required capabilities and the student's skill match. Students apply with one
    click (profile + short note); they see their applications and status
    (applied | viewed | shortlisted | rejected). Founders of claimed startups see
    applicants ranked by skill match and update status. Applications to UNCLAIMED
    startups are saved as "interest" and shown to the founder when they claim.
F10. Logging and events: one JSON log line per request (request_id, method, path,
    status, duration_ms, user_id); an append-only events table for every product
    action. Never log names, emails, phone numbers or tokens.

## Data model (Postgres)
- members: id, role (student | founder | mentor | investor | partner_admin),
  display_name, bio, location (geography point), city, college (students),
  verification_level, open_intro_slots, circuits_opt_in, created_at, updated_at
- startups: id, name, website_domain (unique), description, sector, stage, address,
  location (geography point), hiring, open_roles (jsonb), tech_stack (jsonb),
  claimed_by_member_id, source (seed | crawler | user), view_count, created_at
- startup_members: startup_id, member_id, title
- jobs: id, startup_id, title, description, type (internship | full_time | part_time),
  paid (bool), stipend_range, location (geography point), remote (bool), active,
  created_at  (replaces startups.open_roles as the source of truth for roles)
- job_capabilities: job_id, capability_id, required (bool)
- applications: id, job_id, student_id, note, status (applied | viewed |
  shortlisted | rejected), created_at, updated_at; one application per student per job
- capabilities (40-80, seeded), traits (20-30, seeded)
- needs: owner_type (member | startup), owner_id, capability_id, text,
  embedding vector(384), active
- offers: member_id, capability_id, text, embedding vector(384), active
- member_traits, startup_traits, member_skills (students: capability links)
- connections: member_a, member_b, strength, source
- intro_requests: from_member, to_member, via_member, status, reason, timestamps
- match_results: member_id, candidate_id, candidate_type (member | startup), score,
  components (jsonb), reason, is_bridge, computed_at
- circuits, circuit_legs (giver, receiver, capability, consent, fulfilled, rating)
- events: actor_id, type, target_type, target_id, payload (jsonb), created_at
GIST indexes on locations, HNSW indexes on embeddings.

## Matching (v1, rule-based)
- Candidates from two sources, merged: local (same city, shared traits, 1-2 hop
  connections) and bridge (whole pool, need-to-offer on capability + embedding
  similarity, ignoring sector).
- score = w1*complementarity + w2*affinity + w3*trust_path + w4*timing
          - w5*load_penalty
  Complementarity is computed in both directions. Weights in config. Pure functions,
  fully unit-tested.
- Ranking: diversity, capacity caps, ~25% of results reserved for bridge matches.
- Students: distance is a HARD filter; match student skills to startup open roles
  and needs.
- A background job precomputes results into match_results every few hours; also
  callable on demand.
- tests/eval/pairs.json: ~50 hand-labelled good/bad pairs from the seed data and a
  script reporting how often the scorer agrees.

## Auth
- Supabase Auth (Google sign-in first, email OTP backup; no passwords stored by us).
  FastAPI verifies Supabase JWTs via JWKS. Our members table (linked by auth user
  id) is the source of truth for role, verification_level and partner scope.
- Row-level security on every table; all writes go through FastAPI; the service
  role key exists only in the backend.
- DEMO_AUTH mode issues tokens for seeded personas (powers the persona switcher).
  The app must refuse to start with DEMO_AUTH=true when ENV=production unless
  DEMO_PUBLIC=true is explicitly set for a demo deployment with only fake data.
- require_level(n) dependency for protected endpoints.

## Seed data (this is the demo, treat it carefully)
- Configurable city centre (lat/lng in .env). ~150 startups, ~300 members (students
  the largest group), realistic fake companies, sectors, roles and needs.
- Must contain these scripted demo stories so the differentiator always shows:
  1. A biotech startup needing marketing, matched to a deep-tech marketer as a
     Bridge match with a clear reason (shared traits: long sales cycle, technical
     buyers).
  2. A 3-person exchange circuit (Asha needs marketing, Priya needs fundraising,
     Arjun needs hiring) that the circuit round reliably finds.
  3. A student from a lower-tier college with strong skills, matched to a nearby
     hiring startup on skills.
  4. A warm intro path through a respected mentor.
  5. A visible capability gap in the dashboard (e.g. many needs for regulatory help,
     few offers).
- Startup records use the future crawler schema: name, website_domain, description,
  sector, address, lat, lng, hiring, open_roles, tech_stack, source.
- Seed loader is idempotent (upsert by website_domain).

## Phases (stop after each)
0. Scaffold: /backend and /frontend, docker compose for Postgres, config, logging
   middleware, /health and /health/deps. Verify both apps start.
1. Data model + seed: models, migrations, indexes, capability/trait lists, seed
   generator with all five demo stories, reset-demo command.
2. Auth + profiles: JWKS + DEMO_AUTH, personas, members/startups CRUD, needs/offers,
   smart onboarding endpoint (F1), verification levels (F7).
3. Geo + claim: nearby and bbox endpoints, student skill-to-startup scoring, view and
   interest tracking, claim flow, jobs and applications endpoints (F2 backend, F3,
   F11 backend).
4. Matching: embeddings, scoring, candidates, ranking, reasons, bridge badges, job,
   eval script (F4).
5. Intros + events: warm paths, intro requests with capacity, outcome rating, events
   for every action (F5, F10).
6. Circuits: edges, cycles, solver, rounds, consent endpoints, admin trigger, tests
   with a hand-built graph where the right circuits are known (F6).
7. Dashboard API: gap map by capability and area, network stats, local vs bridge
   acceptance (F8 backend).
8. Frontend shell: Vite app, Tailwind, generated API client, layout, persona
   switcher (F9), login state, verification badges.
9. Map view: MapLibre map, filters, pins, popups, interest button, startup page with
   claim flow, jobs list, job page, apply button, "My applications", founder
   applicants view (F2, F3, F11 UI).
10. Network app: onboarding flow with chips (F1 UI), matches list with reasons and
    Bridge badges, warm intro flow, circuits loop card with accept/decline.
11. Dashboard UI: gap chart, map heat layer, stats, acceptance split (F8 UI).
12. Demo readiness: DEMO.md with a 5-minute demo script following the five seed
    stories, reset-demo verified, README with setup for Mac and WSL, deployment
    config for Railway or Render, all tests passing.

## Testing (required; the demo depends on it)
Write tests as you build each phase, not at the end. Tests run against a real
Postgres (with PostGIS + pgvector) started by docker compose, using a separate test
database that is created fresh and seeded for each test run. Use the fake embedding
provider and never call the LLM in tests (mock it).

Unit tests (fast, no database)
- Scoring: complementarity in both directions, bridge flag, load penalty, weights
  read from config, score always between 0 and 1.
- Reasons: every reason string is non-empty and mentions a real shared capability
  or trait.
- Circuits: on a hand-built graph with known answers, the cycle finder returns
  exactly the expected 3-person loops (no duplicates), and the solver never puts a
  person in more circuits than their capacity.
- Auth: expired token rejected, wrong signature rejected, level checks enforced,
  app refuses to start with DEMO_AUTH=true and ENV=production (unless DEMO_PUBLIC).
- Logging: log lines contain request_id and never contain names, emails or tokens.

API tests (httpx against the running app)
- Every endpoint: one success case and at least one failure case (wrong level,
  missing auth, bad input) with the correct status code.
- Geo: nearby results sorted by distance; nothing outside the radius returned.
- Intros: capacity limit refuses the request after the limit is reached.
- Events: every product action writes exactly one event row.

Demo story tests (tests/demo/) — THE MOST IMPORTANT TESTS
One test per seed story. Each runs the real flow end to end on freshly reset seed
data and asserts what the audience will see:
1. Bridge: the deep-tech marketer appears in the biotech startup's top 5 matches,
   is_bridge is true, and the reason mentions a shared trait.
2. Circuit: after "Run round now", a circuit containing Asha, Priya and Arjun is
   proposed, with the correct giver -> receiver -> capability for each leg.
3. Student: the lower-tier-college student's top startup is the planned nearby
   hiring startup, within the radius, matched on skills; the student applies to
   its internship, and the founder sees them as the top-ranked applicant.
4. Warm intro: the warm path between the two planned members goes through the
   planned mentor.
5. Gap: regulatory help is in the top 3 gaps on the dashboard for the seed city.
Also: reset-demo run twice in a row produces identical results (idempotent).

Frontend tests (from Phase 8)
- Playwright end-to-end tests that click through the five stories in a real browser
  at laptop and phone widths, using the persona switcher.

One command to check everything before a demo
- `make demo-check` (or a script if make is unavailable) that: starts services,
  resets the demo data, runs all tests, hits /health/deps, and prints a clear
  PASS/FAIL summary per demo story. If anything fails, it prints which story broke.
- Run this before every demo. Never demo on a red result.

## Definition of done (every phase)
Tests pass (including any demo story tests the phase makes possible), new
endpoints log correctly, migrations apply from scratch, README
updated, committed, and explained to me. From Phase 8 on: every screen works at
phone width and on a laptop, because demos happen on both.
