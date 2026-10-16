# Circuit — engineering guide

Read this every session. It says WHAT Circuit is and HOW we build it.
- PRODUCTION.md: how it runs in production (infra, security, ops). Wins on infra questions.
- LAUNCH.md: the staged checklist to reach production. Do one stage per session.
- BACKLOG.md: everything else, prioritised. Never build from it without it being pulled into a stage.
- PROGRESS.md: current status. Update it at the end of every session.
- DESIGN.md: visual and writing rules (create it before redesign work).

## Product
Circuit is a startup ecosystem platform for India, starting with one pilot city and
one partner college.

Differentiator: we match people on what they NEED and what they can OFFER, not on
sector or job titles. That enables cross-sector "bridge" matches, warm intros and
3-person exchange circuits, plus a map of who is hiring nearby.

Users:
- Students (often tier 2/3 colleges): find nearby hiring startups and jobs, matched on
  skills and proof of work, not college name.
- Founders, mentors, investors: matches with reasons, warm intros, exchange circuits.
- Partner admins (colleges, incubators): dashboard of their own ecosystem's gaps.
- Super admins (Circuit team): verification, moderation, crawled-data review.

## Features (current scope)
F1  Smart onboarding: paste a bio → LLM suggests needs, offers, capabilities, traits
    from OUR FIXED LISTS ONLY → user confirms with chips. Manual pickers if the LLM fails.
F2  Startup map: filters (hiring, capability, distance), pins by hiring status, popup
    with match %, open roles, "I'm interested".
F3  Unclaimed startup profiles + claim flow (verify via company email domain). Shows
    student views/interest to motivate claiming. Claimed data is never overwritten.
F4  Matches with one-line reasons; "Bridge match" badge for cross-sector matches.
F5  Warm intros via the best mutual connection (1–2 hops); weekly capacity limits.
F6  Exchange circuits: weekly round + super-admin "Run round now". 3-person loops,
    weakest-link score, CP-SAT selection, 72h consent, live status, mark done, rating.
F7  Verification levels 1–3 as badges (1 email, 2 work email/LinkedIn, 3 admin-verified).
F8  Partner dashboard: gap chart + heatmap, network stats, local vs bridge acceptance.
    Scoped to the partner's organisation; counts under 5 hidden.
F9  Demo mode (dev/demo environments only): persona switcher + `make reset-demo`.
F10 Logging + events: one JSON log line per request; append-only events table.
F11 Jobs and applications: list, filters, job page with skill match, one-click apply,
    statuses, founder applicant view ranked by skill match.
F12 Account basics: landing page, sign-up/onboarding, settings, export, delete,
    notifications (in-app + email), report/block, help/FAQ, legal pages.
F13 Admin: super-admin panel (verify, moderate, review crawled startups, takedowns,
    metrics, audit log).

Planned next (see BACKLOG.md): networking redesign (feed, profiles with proof of work,
connections, search, inbox), GitHub proof of work, production crawler, PWA polish.

## Stack
Backend (/backend)
- Python 3.12, uv, FastAPI, Pydantic v2
- SQLAlchemy 2 (async) + Alembic, psycopg 3
- Postgres 16 + PostGIS + pgvector (Supabase in staging/production; local container in dev)
- GeoAlchemy2, pgvector-python
- fastembed (BAAI/bge-small-en-v1.5, 384 dims) behind an EmbeddingProvider interface,
  with a deterministic fake provider for tests
- anthropic SDK, claude-haiku-4-5-20251001 (onboarding extraction, crawler)
- networkx (cycle finding), OR-Tools CP-SAT (circuit selection)
- Redis (cache + rate limits) behind a cache/ interface
- structlog JSON logs; pytest + httpx

Frontend (/frontend)
- React + TypeScript + Vite + Tailwind; PWA
- MapLibre GL JS with OpenStreetMap-based tiles
- TanStack Query + a client generated from the OpenAPI spec (no hand-written fetch calls)
- Recharts; Supabase JS client only for auth, storage uploads and realtime

Infra: see PRODUCTION.md (Cloud Run, Cloud Run Jobs + Scheduler, Supabase, Redis,
Vercel, GitHub Actions). Local dev: docker compose with Postgres (PostGIS + pgvector)
and Redis. Every image must work on ARM64 and x86_64.

Graph queries (warm paths, circuits, 2nd-degree network) use recursive SQL and
networkx behind a graph/ interface. Neo4j is NOT in scope; it can be added behind the
same interface if a measured trigger in BACKLOG.md is hit.

## Architecture rules
- Postgres is the only source of truth. Redis is disposable: if it's down, read from
  Postgres and log a warning.
- Routers are thin; business logic lives in services/. React components stay thin;
  data logic lives in hooks.
- Heavy work (matching, circuit rounds, crawling, LLM calls in bulk) never runs inside
  a user request; it runs as jobs and users read precomputed results.
- Every external call has a timeout, retries with backoff and a graceful fallback.
- Jobs and important endpoints are idempotent.
- One way to do each thing: one error format, one pagination style, one logging setup.

## Auth and access
- Supabase Auth: Google sign-in first, email OTP backup. We never store passwords.
- FastAPI verifies Supabase JWTs via JWKS (signature, expiry, audience, pinned algorithm).
- members table (linked by auth user id) is the source of truth for role,
  verification_level, organisation_id.
- Roles: student, founder, mentor, investor, partner_admin, super_admin.
- require_role / require_level / partner scoping on every endpoint; IDOR tests.
- RLS on every table; all writes go through FastAPI; service role key only in backend.
- DEMO_AUTH issues persona tokens in dev/demo only. The app refuses to start with
  DEMO_AUTH=true when ENV=production.

## Data model (Postgres)
- members: id, auth_user_id, role, display_name, bio, location (geography), city,
  college, organisation_id, verification_level, open_intro_slots, circuits_opt_in,
  is_minor, profile_visibility, created_at, updated_at
- organisations: id, name, kind (college | incubator | program), city
- startups: id, name, website_domain (unique), description, sector, stage, address,
  location, hiring, tech_stack (jsonb), claimed_by_member_id,
  source (seed | crawler | user), confidence, view_count, created_at
- startup_members; jobs; job_capabilities; applications (one per student per job)
- capabilities (40–80), traits (20–30); needs; offers (with embedding vector(384))
- member_traits, startup_traits, member_skills
- connections; intro_requests; match_results (score, components jsonb, reason, is_bridge)
- circuits; circuit_legs (giver, receiver, capability, consent, fulfilled, rating)
- notifications; reports; blocks; audit_log; consents (policy_version, accepted_at)
- events (append-only: actor_id, type, target_type, target_id, payload, created_at)
GIST indexes on locations, HNSW on embeddings, indexes on every foreign key.

## Matching (v1, rule-based)
- Candidates: local (same city, shared traits, 1–2 hop connections) + bridge (whole
  pool, need-to-offer on capability + embedding similarity, ignoring sector).
- score = w1*complementarity + w2*affinity + w3*trust_path + w4*timing - w5*load_penalty
  Complementarity both directions. Weights in config. Pure, unit-tested functions.
- Ranking: diversity, capacity caps, ~25% bridge share. Students: distance is a hard filter.
- Precomputed by a job into match_results, cached in Redis.
- Eval set (tests/eval/pairs.json) + script; every scoring change must not lower agreement.

## Privacy and safety
- Company data only from crawling; robots.txt respected; takedown form.
- Never log or send to analytics: names, emails, phones, tokens.
- Under-18 students: hidden profile by default, no messages from strangers.
- Aggregates hide counts under 5; heatmaps use coarse cells.
- Super-admin actions audit-logged.

## Testing
- Unit (scoring, reasons, circuits on known graphs, auth, logging), API (every endpoint:
  one success + at least one failure, IDOR, rate limits, events), Playwright end-to-end
  at 375px and 1280px, axe accessibility checks.
- Tests use a fresh seeded test database, the fake embedding provider and a mocked LLM.
- Demo story tests (tests/demo/): bridge match, Asha–Priya–Arjun circuit, tier-3
  student matched and applying, warm intro via mentor, regulatory-help gap.
- `make check` runs everything and prints PASS/FAIL per story. Never deploy on red.

## How to work with me
- I'm learning. Explain what you built and why in plain language, including new concepts.
- Work on one LAUNCH.md stage (or one approved backlog item) per session, on its own branch.
- Write tests as you build. Never finish with failing tests.
- At the end: tick LAUNCH.md boxes, update PROGRESS.md, commit, summarise, stop for my OK.
- Ask before adding any dependency, changing the schema in a breaking way, or deleting data.
- Never commit secrets. .env is gitignored; .env.example documents every variable.
- Keep it simple. Prefer deleting code to adding abstraction.
