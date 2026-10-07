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

Infra
- docker compose for Postgres locally
- Deployable to Railway or Render (one backend service, one static frontend,
  managed Postgres with PostGIS + pgvector)

Note: Neo4j (graph) and Redis (cache) are part of our target architecture but are
deliberately left out of this MVP. Postgres handles graph queries (recursive SQL),
caching (a match_results table) and jobs at MVP scale. Keep the code behind clear
interfaces (graph/, cache/) so Neo4j and Redis can be added later without rewrites.

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
- JWT verification against a configurable JWKS URL (provider chosen later: Clerk or
  Supabase), claims: sub, role, verification_level, exp.
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
   interest tracking, claim flow (F2 backend, F3).
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
   claim flow (F2, F3 UI).
10. Network app: onboarding flow with chips (F1 UI), matches list with reasons and
    Bridge badges, warm intro flow, circuits loop card with accept/decline.
11. Dashboard UI: gap chart, map heat layer, stats, acceptance split (F8 UI).
12. Demo readiness: DEMO.md with a 5-minute demo script following the five seed
    stories, reset-demo verified, README with setup for Mac and WSL, deployment
    config for Railway or Render, all tests passing.

## Definition of done (every phase)
Tests pass, new endpoints log correctly, migrations apply from scratch, README
updated, committed, and explained to me. From Phase 8 on: every screen works at
phone width and on a laptop, because demos happen on both.
