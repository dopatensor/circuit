# Circuit — progress

Snapshot for picking the work up in a new session. The spec is [CLAUDE.md](CLAUDE.md)
(including the "Spec additions" and "Testing" sections at the end). **The frontend
must also follow [DESIGN.md](DESIGN.md)**, the user's design and PWA brief for Phases
8–11. Setup details are in [README.md](README.md).

Branch: `claude/kind-noether-bp70jm`. Phases 0–4 are merged into `main` (pull requests
#1–#3 in `dopatensor/circuit`). Phases 5–9 are committed and pushed on this branch
but not merged yet; no pull request has been opened for them.

## Status at a glance

| Phase | State |
| --- | --- |
| 0 Scaffold | ✅ done |
| 1 Data model + seed (+ F11 jobs tables and seed jobs) | ✅ done |
| 2 Auth + profiles, onboarding (F1), verification (F7) | ✅ done |
| 3 Geo + claim (F2, F3) + jobs/applications API (F11) | ✅ done |
| 4 Matching (F4) | ✅ done |
| 5 Intros + events (F5, F10) | ✅ done |
| 6 Circuits (F6) | ✅ done |
| 7 Dashboard API (F8 backend) | ✅ done |
| 8 Frontend shell (F9) + PWA + redesign | ✅ done |
| 9 Map view + jobs UI (F2, F3, F11) | ✅ done (waiting for the user's OK) |
| **10 Network app (F1 UI, matches, intros, circuits)** | ⏭️ **next: not started** |
| 11–12 | not started |

Last verified (2026-10-07, Phase 9 commit):

- Backend tests: **224 passed, 1 skipped**. `ruff` and `alembic check` are clean.
- Browser tests: **35 passed, 1 skipped** (twice in a row).
- `npm run size`: 96.6 KB first-load JavaScript, gzipped. MapLibre (283 KB gzipped) is
  its own lazy chunk and isn't pre-cached on install (404 KB precache).
- Lighthouse (mobile, slow 4G): welcome 98/100/100/100; `/jobs` and `/matches` signed in
  99–100; `/map` as Ravi 89–92 Performance, 95 Accessibility, 96 Best Practices (see
  known issues).
- `make demo-check`: **5/5 PASS**.

## What Phase 5 built (warm intros, F5)

- `app/intros.py` (pure helpers + DB helpers) and `app/api/intros.py`:
  `GET /api/intros/path/{member_id}` (level 2), `POST /api/intros` (level 3),
  `GET /api/intros/me`, `POST /api/intros/{id}/forward|accept|decline|withdraw|rate`.
- Statuses: `pending` → `forwarded` → `accepted` / `declined` → `completed`; also
  `withdrawn` and `expired` (migration `a5cb711b8b42`).
- Capacity: `members.open_intro_slots` per rolling 7 days (received + passed on); senders
  max `INTRO_REQUESTS_PER_WEEK` (5); refusals are 429 with a dated polite message.
- Accepting an intro adds a `connections` row (`source="intro"`, strength 0.5).
- `tests/test_events_coverage.py` fails if any write endpoint doesn't record an event.

## What Phase 6 built (exchange circuits, F6)

- `app/circuits/engine.py` (pure): `edge_weight` (0.4 + 0.4·text fit + 0.2·trust),
  `best_edges` (one per giver→receiver), `find_cycles` (networkx `simple_cycles` with
  `length_bound=3`, weakest-link score), `choose_circuits` (CP-SAT, at most one circuit
  per person, maximise total score in thousandths, one worker + fixed seed so it's
  deterministic, 10 s limit, at most 20,000 cycles).
- `app/graph.PostgresGraph.can_help(min_level)`: the CAN_HELP edges in SQL (offers ×
  needs on capability, founders inherit their startup's needs, both sides opted in and
  level ≥ 2, best text similarity via pgvector).
- `app/circuits/service.py`: `run_round(dry_run=…)` leaves out people in an open circuit
  and trios that declined or expired in the last 28 days, saves `proposed` circuits with
  `expires_at = now + 72 h`, and records events. `expire_stale` handles expiry.
- `app/api/circuits.py`: `GET /api/circuits/me` (loop cards, your leg first, a sentence
  and your `actions`), `POST /api/circuits/{id}/accept|decline|rate`, and
  `POST /api/admin/circuits/run?dry_run=` (admins).
- Lifecycle: `proposed` → all three accept → `active` → each receiver rates the help they
  got → `completed`. One decline → `declined`. 72 h unanswered → `expired`. Leg `consent`
  is the giver's answer; leg `fulfilled` and `rating` are the receiver's.
- Scheduler: weekly `circuit_round` (`CIRCUIT_ROUND_DAY`/`HOUR`, UTC) and an hourly
  `expire_stale` job that expires intros and circuits.
- Events: `circuits.round_run`, `circuit.proposed`, `.accepted`, `.declined`,
  `.activated`, `.expired`, `.leg_rated`, `.completed`.
- Seed: among opted-in members with level ≥ 2, the only 3-cycle is the story 2 loop (21
  people, 25 edges, 1 cycle). That makes story 2 reliable with both embedding
  providers, but a live round only shows one circuit. The solver logic is proven on
  hand-built graphs in `tests/test_circuits_engine.py`.

## What Phase 7 built (partner dashboard API, F8)

- `app/dashboard.py`: SQL for gaps by capability, gaps on a grid (cells are squares of
  `cell_km`, default 2 km, with longitude scaled by latitude), network stats, and intro
  acceptance by `is_bridge`. The pure helpers (`grid_degrees`, `Acceptance.rate`) are
  unit-tested.
- `app/api/dashboard.py`: `GET /api/dashboard/gaps`, `/gaps/areas`, `/stats`, `/intros`,
  partner admins only (`require_admin`). Each records a `dashboard.viewed` event.
- Needs whose owner no longer exists are left out (needs have no foreign key to their
  owner, so a deleted member's needs could otherwise linger in counts).
- Seed numbers: regulatory affairs 35 needs vs 2 offers; 17 cells with a regulatory gap
  at 2 km; intro acceptance local 52% (12/23) vs bridge 80% (20/25).

## What Phase 8 built (frontend shell, F9, PWA)

- **Dependencies** (approved): tailwindcss + `@tailwindcss/vite`, `@tanstack/react-query`,
  `openapi-fetch` + `openapi-typescript` (dev), `react-router`, `@playwright/test`
  (pinned to **1.56.1** to match the container's Chromium), `vite-plugin-pwa`,
  `lighthouse` (dev). **TypeScript pinned to ~5.9**: TypeScript 7's native compiler has
  no JS API, which openapi-typescript needs.
- `src/api/client.ts`: the typed client (`api.GET("/api/...")`), the token middleware,
  `unwrap()` (data or an `ApiError` with one plain sentence; the API's `detail` strings
  are shown as-is), and `withMeta()` (also returns `servedAt` from the `Date` header, for
  `<LastUpdated>`). CORS exposes `Date`.
- `src/auth.tsx`: token plus your own `MemberSummary` (and the demo flag) in
  localStorage. This makes the app open instantly and work offline; `/api/auth/me`
  re-checks it, and a 401 signs you out. `login(persona)` and `logout()` clear the query
  cache and the service worker's `circuit-api` cache.
- `src/nav.ts`: tabs per role; the first tab is home. `/` and unknown paths redirect
  there, as do tabs your role doesn't have.
- `src/components/`: `Shell` (bottom tabs on phones, sidebar from `md`; content column
  720px, full width for `/map` and `/dashboard`), `ui.tsx` (Title, PrimaryButton (accent),
  SecondaryButton, Skeleton, Empty, ErrorState, VerificationBadge, BridgeBadge,
  LastUpdated), `PersonaList`.
- `src/screens/`: Welcome (signed out, persona list), Me (name, role, badge, persona
  switcher, sign out), and placeholders for Map, Jobs, Matches, Circuits, Intros and
  Dashboard (`placeholders.tsx`). Every screen is lazy-loaded.
- `src/pwa/`: `UpdateBar` (registers the service worker with `registerType: "prompt"`)
  and `InstallPrompt` (counts visits per browser session; iPhone gets manual steps).
- `vite.config.ts`: manifest, Workbox precache, navigation fallback (not for `/api`),
  runtime cache `circuit-api` (NetworkFirst for GET `/api/matches`, `/api/jobs`,
  `/api/applications/me`, keyed by URL only so no Authorization header is stored), and a
  proxy target from `API_PROXY_TARGET`.
- `scripts/`: `make-icons.mjs` (renders the "C" icons with Playwright),
  `check-size.mjs`, `lighthouse.mjs`, `screenshots.mjs`.
- `playwright.config.ts`: phone (375×812) and laptop (1280×800) projects; starts the API
  on :8011 against `TEST_DATABASE_URL` after `reset-demo` (fake embeddings), and a preview
  build on :4183. Tests: `e2e/shell.spec.ts`, `e2e/pwa.spec.ts`.
- Backend: `python -m app.cli openapi`, `PORT` env for the API, and a test that
  `frontend/openapi.json` is current.

## Phase 8 redesign (after the user's review)

- The user found the first shell too plain, loosened the brief and asked for pure black
  with neon blue and green. DESIGN.md's "Update" section records the new rules.
- `src/index.css`: dark-only tokens (`bg`, `surface`, `raised`, `line`, `fg`, `muted`,
  `blue`, `green`), `text-display`, `shadow-glow-blue` / `shadow-glow-green`.
- `src/components/ui.tsx`: Card, Avatar (initials), Pill (green/blue/neutral), Stat,
  Eyebrow, PrimaryButton (neon blue + glow), BridgeBadge (neon green + glow);
  `Sheet.tsx` (bottom sheet / centred panel on `<dialog>`); `DemoStories.tsx` (personas
  grouped by story, replaces PersonaList); `MatchCard.tsx`.
- Backend: `DEMO_STORIES` and `DEMO_PERSONAS` now carry a story number; the persona API
  returns `story_number` and `story_title`. Deepak (LedgerLoop's founder, story 3) was
  added to the switcher.
- Screens: a new Welcome (pitch, three steps, stories), Me (profile card, three stats by
  role, demo card with "Switch person", sign out), and **Matches is real now**
  (`/api/matches` as cards: score, reason, Bridge badge; no action yet, Phase 10 adds
  "Ask for intro"). Icons are a neon-blue "C" on black.
- The Me stats call `/api/matches`, `/api/jobs`, `/api/dashboard/stats` etc., so they
  also write those endpoints' "viewed" events. Acceptable for now; a dedicated
  `/api/members/me/summary` endpoint would be cleaner.

## What Phase 9 built (map, claim, jobs: F2, F3, F11 UI)

- **Map** (`src/screens/MapScreen.tsx`, `src/map/`): MapLibre GL (lazy chunk) with
  `darkStyle()`, a pure-black style from OpenFreeMap vector tiles (`VITE_MAP_TILES`,
  `VITE_MAP_GLYPHS`). Pins are DOM buttons inside a MapLibre-owned wrapper (never
  overwrite the wrapper's classes: MapLibre positions it), created 25 per frame, with a
  24px tap area. The map fits all pins when results or filters change (instant the
  first time) and sets `data-map-settled` when it stops moving. Data comes from
  `/api/map/startups/nearby` (students 5/10/20 km, others 50 km). Filters sheet: hiring,
  skill, distance (students). The pin sheet shows sector, distance, hiring, match %,
  open roles (links to jobs), "I'm interested" (students) and "View startup". Without
  WebGL, a plain list is shown.
- **Startup page** (`StartupPage.tsx`): header with pills, stats (students interested,
  views, applications), the claim card + `ClaimFlow` sheet (email → code; "Use it" fills
  the demo code), "See applicants" for the claimer, "I'm interested" for students,
  description, roles, team. **Find your startup** (`FindStartup.tsx`, `/startups`).
- **Jobs** (`Jobs.tsx`): "Open jobs" / "My applications" segmented tabs (`?tab=`),
  search, filter sheet (type, pay, distance, skill), and `LastUpdated` for offline
  copies. **Job page** (`JobPage.tsx`): match %, skills with ✓ for ones you have,
  description, a note about unclaimed startups, "Apply" fixed at the bottom and an
  `ApplyForm` sheet, "You applied" + status afterwards, "See applicants" for the
  startup's own founder.
- **Applicants** (`Applicants.tsx`): ranked by match; skills (matched in green), the
  note, status, and Shortlist / Hire / Not a fit buttons.
- **Me** for founders: "Your startups" and "Find and claim your startup".
- Backend: `StartupStats.you_are_interested`.
- Shared: `src/api/hooks.ts` (`useCapabilities`, `useMyProfile`),
  `src/components/jobs.tsx` (status pills, job types, pay).
- **Tests**: `e2e/fixtures.ts` (`resetDemo()` resets the e2e database in about 6 s; an
  automatic fixture blocks the tile host so tests don't depend on it),
  `map.spec.ts` (pins, pin sheet, interest, filters, partner view), `story3.spec.ts`
  (apply → Deepak shortlists → Ravi sees "Shortlisted"; another founder is refused;
  no double apply), `claim.spec.ts` (wrong domain refused, right domain + code claims).
- `scripts/lighthouse.mjs` takes `--as <persona>` (signs in through Playwright first)
  and `--details`.

## Phase 10: exactly what's left (all of it)

Spec: F1 onboarding UI, matches with reasons and Bridge badges (the list exists),
warm intro flow, circuits loop card. Follow DESIGN.md.

1. **Onboarding (F1)**: `POST /api/onboarding/suggest` (paste a bio → suggested needs,
   offers, capabilities, traits from the fixed lists) and `POST /api/onboarding/confirm`.
   Tap-to-select chips; without an API key the endpoint falls back to manual pickers
   (check the response shape). Entry point: Me ("Edit what you need and offer"), and for
   new profiles.
2. **Matches**: add one action per card. Members → "Ask for intro" (opens the intro
   sheet); startups → "View startup"; jobs (students) → "View job". For a startup
   match, the intro target would be its claiming founder (not in the API yet).
3. **Warm intro flow (F5)**: the sheet shows `GET /api/intros/path/{id}`'s sentence and
   via person, a reason field (10–500 characters) and "Send request". Show 429/403
   messages as-is (`blocked_reason` when `can_request` is false). The **Intros tab**
   lists sent, to-forward and received requests, each with the `actions` the API lists
   (forward, accept, decline, withdraw, rate 1–5).
4. **Circuits tab (F6)**: `GET /api/circuits/me` loop cards: three names in a simple
   circle, the three "who helps whom" lines, Accept / Decline (72 h countdown), then
   "Rate the help you got" once active. Partner admins: "Run round now" (Dashboard, Phase
   11, or a small admin card).
5. Playwright: story 1 (Meera → Kavya Bridge card → intro path), story 4 (Rohan →
   Vikram via Lakshmi: request → Lakshmi forwards → Vikram accepts → Rohan rates), story 2
   (admin runs the round → Asha, Priya and Arjun accept → active). Use `resetDemo()`.
6. Screenshots, Lighthouse, size, README, PROGRESS, commit, stop for OK.

## Remaining phases after 10 (from CLAUDE.md)

- **11 Dashboard UI**: gap chart (Recharts) from `/api/dashboard/gaps`, MapLibre heatmap
  layer from `/api/dashboard/gaps/areas` (weight by `gap`, clipped at 0, with a
  capability picker), stat tiles from `/stats`, local vs bridge bars from `/intros`.
- **12 Demo readiness**: DEMO.md 5-minute script (story 3 includes applying and
  shortlisting), Railway or Render config, final README.

## Decisions and deviations from CLAUDE.md

All of these were explained at the end of their phase; the user confirmed by continuing.

**Dependencies** (approved by the user, or on the spec's list):
- **Added with approval:** uvicorn, pydantic-settings, ruff (dev), @vitejs/plugin-react,
  @types/react and @types/react-dom (Phase 0); PyJWT[crypto] (Phase 2).
- **From the spec's list:** networkx and ortools (Phase 6; OR-Tools also brings pandas
  and pins protobuf 6, which onnxruntime/fastembed accept), alembic, geoalchemy2,
  pgvector, anthropic, fastembed,
  apscheduler.
- **Not added:** `@types/node` was avoided, so the Vite proxy target is hard-coded to
  `http://localhost:8000`.

**Data model additions beyond the spec's list:**
- `members.sector` (needed to tell bridge from local matches), `members.auth_subject`
  (JWT `sub`), `members.linkedin_url` (level 2).
- `member_skills.level` (1–3).
- `intro_requests.is_bridge`, `outcome_rating`, `forwarded_at`, and the extra statuses
  `forwarded` and `withdrawn` (Phase 5).
- `startup_claims` table (claim codes; stores only the email domain and a code hash).
- F11 tables `jobs`, `job_capabilities`, `applications`.
- `match_results.candidate_type` also allows `job`, because students are matched to jobs.

**Seed:**
- Startup domains use the reserved `.example` TLD, so nothing points at a real company.
- The default city is Bengaluru (`CITY_NAME`, `CITY_CENTER_LAT`/`LNG`), with generic area
  names so any city works.
- The regulatory-need rate was halved so the gap looks believable (35 needs vs 2 offers).
- LedgerLoop's second need was changed from regulatory affairs to data engineering so the
  story 3 internship is a clean 100% match.
- Ravi is verification level 2 (LinkedIn), because matches need level 2.
- Seed events are marked `payload.seed = true` and written once; a plain `seed` keeps live
  claims and never lowers view counts; `reset-demo` truncates everything.

**Auth:**
- Role and verification level come from the member row, not the token, so admin changes
  apply immediately. Token claims only seed a new profile, and the level is capped at 1.
- Partner admins (level 3) act as "admin".
- Demo tokens are HS256 with `DEMO_JWT_SECRET`, which must be 32+ random characters when
  demo auth runs in production.
- `env_ignore_empty=True`, so `KEY=` in `.env` means "use the default".

**Map:** pins and pages show **jobs**, not the raw `open_roles` JSON. `open_roles` stays as
crawler input and seeded jobs are derived from it. `StartupCreate`/`Update` no longer
accept `open_roles`; founders manage jobs through the jobs endpoints.

**Privacy:**
- Public member profiles show the city only, never the exact location.
- Founders' applicant lists show skills, not college.
- Only the claiming founder sees *who* is interested; everyone sees the counts.

**Claim flow:**
- Email is simulated: `dev_code` is returned outside production or with `DEMO_PUBLIC=true`.
- Real production returns 503 until an email provider is added (that would be a new
  dependency, so ask first).

**Matching:** the bridge rule is "different sectors and complementarity ≥ 0.5". Students
are matched only to jobs within `STUDENT_RADIUS_KM` (10 km), with one job per startup.

**Intros (Phase 5):**
- Viewing a path needs level 2 (like matches); sending a request needs level 3;
  answering (forward, accept, decline) needs no particular level.
- One weekly capacity per person covers both receiving and passing on requests.
- Senders have their own weekly limit (5), which isn't in the spec, to stop spamming.
- Accepted intros create a connection, which grows the graph used for trust paths.
- Only the sender rates the outcome.

**Dashboard (Phase 7):**
- "Area" is a grid of square cells (2 km by default), not named neighbourhoods, because
  addresses aren't geocoded into areas. This works for any city.
- The dashboard covers the whole platform (one city in the MVP), not one partner's own
  members.

**Circuits (Phase 6):**
- Circuits need verification level 2 (like matches), plus `circuits_opt_in`.
- Founders' circuit needs include their startup's needs (as in matching).
- Trios that declined or expired aren't proposed again for 28 days.
- "Fulfilled" is the receiver's word, given when they rate the help they received.
- The admin run endpoint has a `dry_run` option (used by demo-check).

**API layout:** product endpoints live under `/api/...`; health stays at `/health` and
`/health/deps`.

## Known issues and limitations

- **Startup list is query-heavy.** `GET /api/startups` loads details per startup (about 5
  queries each, so up to ~500 for 100 results). Fine at seed size; the map, job and match
  endpoints are already batched.
- **Real Claude call never run.** No `ANTHROPIC_API_KEY` was available, so onboarding was
  only verified against a fake Messages API server that exercises the real SDK. Try it
  once with a real key.
- **No rate limit** on `POST /api/onboarding/suggest`, which costs money per call. Add
  one before any public deployment.
- **Matches can be up to 6 hours stale** after someone edits their needs or offers, until
  the job runs, `POST /api/matches/refresh` is called, or an admin recomputes.
- **Stale match rows aren't cleaned up.** Rows pointing at deleted candidates are skipped
  when read, but not deleted until the next recompute.
- **The eval is optimistic.** It scores 100%, but the labels came from reading needs
  against offers, which is also the scorer's main signal. Some good pairs sit close to
  the 0.40 threshold (Meera→Sunil 0.49, founder-008-0→Lakshmi 0.43). Labels from real
  users would be a harder test.
- **Intro paths are only for members.** A startup match has no intro target in the API
  yet (Phase 10 should use the claiming founder).
- **`GET /api/intros/me` returns at most 200 requests**, newest first, with no paging.
- **The seed has only one possible circuit** (story 2). A live "Run round now" shows
  one loop. More background loops in the seed would make the round look richer, but
  they must not compete with the story loop.
- **Running a real round before a demo uses up story 2**: Asha, Priya and Arjun are
  then in an open circuit, so demo-check fails until `make reset-demo`.
- **No way to withdraw interest.** "I'm interested" can't be undone, because events are
  append-only and there's no "withdrawn" event yet.
- **`startups.hiring` isn't derived from open jobs.** It's set when a job is created but
  not cleared when every job closes.
- **`jobs.searched` events are noisy:** one is written on every jobs list call, including
  pagination.
- **The map scores 89–92 for Lighthouse Performance** (MapLibre's start-up on a simulated
  budget phone) and 95 for Accessibility: in dense clusters pins sit closer than 24px.
  **Pin clustering** (count bubbles that zoom in when tapped) would fix both and help on
  small screens; with DOM pins it means grouping pins in screen space on `moveend`.
- **This sandbox can't reach `tiles.openfreemap.org`** (network policy), so the map here
  shows pins on black without streets. Real browsers load the tiles. Tests block the tile
  host on purpose.
- **Offline e2e tests need `PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS=1`**, which
  `playwright.config.ts` sets. Without it, Playwright's offline switch and routes
  sometimes miss the service worker's own requests, and the cache test flakes.
- **The update bar can't easily be tested automatically** (it needs two deployed
  versions). Check it by hand: build, preview, change a file, rebuild, reload.
- **On a Mac, run `npx playwright install chromium` once** (the cloud container has
  Chromium preinstalled).
- **Uvicorn's own startup lines are plain text.** Request logs are JSON as specified.
- **First `reset-demo` needs internet:** it downloads the ~130 MB embedding model to
  `~/.cache/circuit/fastembed`. With `EMBEDDING_PROVIDER=fake` it works offline, with
  weaker semantic matching.
- **The test database is shared** (`circuit_test`). Some tests reset it and tests that
  mutate seed rows restore them. Run the suite serially; don't parallelise it.

## Commands

### First time (macOS or WSL2)

```bash
git clone <repo> && cd circuit
git checkout claude/kind-noether-bp70jm   # or main once Phase 5 is merged
cp .env.example .env               # set DEMO_AUTH=true for the persona logins
make db                            # docker compose up -d --wait  (Postgres+PostGIS+pgvector)
cd backend && uv sync && cd ..     # Python 3.12 deps (uv downloads Python itself)
cd frontend && npm install && cd ..  # needs Node 22.12+
make reset-demo                    # migrate + seed + embed + compute matches (~15 s; model download first time)
```

### Every day

```bash
make dev-api        # API on http://localhost:8000  (docs: /docs)
make dev-web        # web app on http://localhost:5173  (still the Phase 0 placeholder)
make reset-demo     # restore the demo data
make demo-check     # PASS/FAIL per demo story (expects a fresh reset-demo)
make eval           # match scorer vs tests/eval/pairs.json
make test           # backend pytest + frontend build
make lint           # ruff check + format check
```

Before every demo: `make reset-demo && make demo-check`.

Equivalent raw commands, from `backend/`:

```bash
uv run python -m app.cli reset-demo
uv run python -m app.demo_check            # add --reset to reset first
uv run pytest                              # RUN_MODEL_TESTS=1 also runs the real-model test
uv run python -m app --reload              # API
```

### In a Claude Code cloud session

The SessionStart hook (`.claude/hooks/session-start.sh`) does the setup:
- installs PostGIS and pgvector into the container's local Postgres 16 and starts it;
- creates the `circuit` and `circuit_test` databases;
- runs `uv sync` and `npm install`;
- exports `DATABASE_URL` and `TEST_DATABASE_URL`.

No Docker is needed. Then use the same `make` commands. If uv warns that
`UV_NATIVE_TLS` is deprecated, export `UV_SYSTEM_CERTS=1` and unset `UV_NATIVE_TLS`; the
warning is harmless.
