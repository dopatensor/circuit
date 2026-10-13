# Circuit

A startup ecosystem platform that matches people on what they **need** and what they
can **offer**, across sectors, with exchange circuits and a map of who is hiring nearby.
See [CLAUDE.md](CLAUDE.md) for the full MVP spec and build phases.

**Status:** Phases 0–7 done, i.e. the whole backend: auth, profiles, smart onboarding,
the startup map, claiming, jobs (F11), matching with reasons and Bridge badges (F4),
warm intros with weekly capacity (F5), events for every action (F10), exchange
circuits (F6) and the partner dashboard API (F8). Phase 8 added the frontend shell:
an installable app (PWA) with role-based tabs, the demo persona switcher and
verification badges. Phase 9 added the map, startup pages with claiming, and jobs
with applications. Phase 10 added the network app: onboarding with tap-to-select chips
(F1), an action on every match, the warm intro flow and Intros tab (F5), and the
Circuits loop card with accept, decline and rating (F6). Phase 11 added the partner
dashboard (F8 UI): three numbers, the ranked capability-gap chart, the gap heat map and
local vs bridge intro acceptance. **The frontend redesign (R1–R7, see
[DESIGN.md](DESIGN.md)) is under way:** R1 added the new design system, the `/design`
component gallery, the theme (now pitch black only), the new navigation, Home and "Post a job".
Phase 12 (demo readiness) follows the redesign.
`make demo-check` prints PASS/FAIL per demo story. Browse the API at
http://localhost:8000/docs.

## Layout

```
backend/    FastAPI app (Python 3.12, uv)
  app/        config, logging middleware, db, models, API routers, CLI
  app/seed/   capability/trait lists, demo stories, generator, loader
  app/matching/ pure scoring, ranking and reasons; the compute service; the eval
  app/circuits/ exchange circuits: pure engine (networkx + CP-SAT) and the round service
  app/graph/  people-graph interface (Postgres today, Neo4j later)
  app/cache/  match-cache interface (match_results today, Redis later)
  migrations/ Alembic database migrations
  tests/      pytest suite
frontend/   React + TypeScript + Vite app
db/         Postgres 16 + PostGIS + pgvector Dockerfile and init script
compose.yaml  local Postgres
.env.example  every setting the apps read (copy to .env)
```

## Prerequisites

Works on macOS (Apple Silicon) and Windows via WSL2 (x86_64).

| Tool | Version | macOS | WSL2 (Ubuntu) |
| --- | --- | --- | --- |
| Docker | Desktop 4.x | [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/) | Docker Desktop for Windows with *WSL integration* turned on for your distro |
| uv | latest | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 22.12+ | `brew install node@22` | via [nvm](https://github.com/nvm-sh/nvm): `nvm install 22` |

uv downloads Python 3.12 by itself; you don't need to install Python.

**WSL tip:** clone the repo inside the Linux filesystem (e.g. `~/code/circuit`), not
under `/mnt/c/...`. File watching and installs are far faster there.

## First-time setup

```bash
cp .env.example .env            # then edit if needed; never commit .env
docker compose up -d --wait     # builds and starts Postgres (first build takes a minute)
cd backend && uv sync && cd ..  # creates backend/.venv with all Python packages
cd frontend && npm install && npx playwright install chromium && cd ..   # browser for e2e tests
cd backend && uv run python -m app.cli reset-demo && cd ..   # tables + demo data
```

## Run

In two terminals:

```bash
# Terminal 1 — API on http://localhost:8000 (docs at /docs)
cd backend && uv run python -m app --reload

# Terminal 2 — web app on http://localhost:5173
cd frontend && npm run dev
```

Check it works:

- http://localhost:8000/health → `{"status":"ok"}` (the process is up)
- http://localhost:8000/health/deps → Postgres, PostGIS and pgvector status
  (returns 503 if any is missing)
- http://localhost:5173 → the web app; it reaches the API through Vite's proxy

To test on a phone, open the "Network" URL that `npm run dev` prints (same Wi-Fi).

## Tests and checks

```bash
cd backend
uv run pytest               # uses the circuit_test database (TEST_DATABASE_URL)
uv run ruff check .         # lint
uv run ruff format .        # auto-format

cd ../frontend
npm run build               # type-checks and builds (also writes the service worker)
npm run size                # first-load JavaScript must stay under 250 KB gzipped
npx playwright test         # browser tests at 375px and 1280px (starts its own API on
                            # :8011 against circuit_test and a preview build on :4183)
```

Lighthouse (mobile profile: mid-range Android, slow 4G), with the API running:

```bash
cd frontend && npm run build && npx vite preview --port 4183 &
npm run lighthouse -- http://localhost:4183/welcome
npm run lighthouse -- http://localhost:4183/map --as ravi --details   # signed in
```

Last run (Phase 11): the dashboard 95–96/100/100/100. On this session's machine the map
measures 73–86 for Performance, and so does the unchanged Phase 10 build, so that's the
machine, not a regression. Phase 10: onboarding, matches, intros, circuits and the dashboard's
"Run round now" all 100/100/100/100. Phase 9: welcome 98/100/100/100; jobs and matches 99–100 across the board;
the map 89–92 Performance (MapLibre's start-up work on a simulated budget phone), 95
Accessibility (pins in dense clusters sit closer than 24px) and 96 Best Practices
(only because this sandbox can't reach the tile server). Lighthouse
12+ no longer has a PWA category; `e2e/pwa.spec.ts` checks the manifest, icons,
service worker and offline behaviour instead.

## Auth

- **Real logins**: set `JWKS_URL` (and `JWT_ISSUER` / `JWT_AUDIENCE` if your provider
  sets them) to your Clerk or Supabase project. The API accepts RS256/ES256 tokens
  signed by that provider. The token's `sub` identifies the person; a new user calls
  `POST /api/members/me` once to create their profile.
- **Demo logins** (`DEMO_AUTH=true`): `GET /api/auth/demo/personas` lists the seeded
  personas, `POST /api/auth/demo/login {"persona": "ravi"}` returns a token. The app
  refuses to start with demo auth in production unless `DEMO_PUBLIC=true` and a random
  `DEMO_JWT_SECRET` (32+ chars) are set.
- **Verification levels** (F7) are stored on the member and checked on every request,
  so a change applies immediately: 1 = email verified (browse), 2 = work email or
  LinkedIn link (matches), 3 = role verified by an admin (intros). Adding a LinkedIn URL
  to your profile raises level 1 to 2. Partner admins (level 3) set levels with
  `PUT /api/admin/members/{id}/verification`.
- Try it in the browser: open http://localhost:8000/docs, call the demo login, copy the
  `access_token`, click **Authorize** and paste it.

## Everyday commands

From the repo root (macOS and WSL both have `make`):

```bash
make db           # start Postgres
make reset-demo   # wipe and reload the demo seed
make demo-check   # PASS/FAIL for each of the five demo stories
make eval         # how often the match scorer agrees with tests/eval/pairs.json
make test         # backend tests, frontend build + size budget, browser tests
make e2e          # browser tests only
make api-client   # regenerate the frontend's typed API client after API changes
make lint         # ruff lint + format check
make dev-api      # API on :8000
make dev-web      # web app on :5173
```

Run `make reset-demo && make demo-check` before every demo.

## Frontend (Phase 8 onward)

`frontend/` is a React + TypeScript app built with Vite and Tailwind CSS.

- **Design** (see [DESIGN.md](DESIGN.md)): simple, calm and guided. Pitch black, with
  the logo's three accents: lime for the main action on each screen, blue only for Bridge
  matches and circuits, orange for demand (hiring, needs, gaps), neutrals for the rest.
  The logo is drawn inline (`<Logo>` in `src/components/ds/Icon.tsx`). IBM Plex Sans (self-hosted in
  `public/fonts/`), with IBM Plex Mono only for standalone numbers. Bordered cards, no
  shadows. Tokens live in `src/index.css`.
- **Design system** (`src/components/ds/`): Avatar, Badge (verification, Bridge, Hiring),
  Button, Card/List/ListRow/Section, Chip, BottomSheet and Modal (built on `<dialog>`;
  spring open, drag down to close on phones), Tabs, Toast (with Undo), Skeleton,
  EmptyState, Stepper, Checklist and inline SVG icons. **`/design`** shows them all, in
  dev and in builds made with `VITE_DESIGN_PAGE=1` (the test build); never in a normal
  production build. Animation uses `motion` (only its small DOM feature set) and
  `@use-gesture/react` for dragging; everything respects "reduce motion".
- **Layout**: everyone gets the same places: **Home · Discover · Circuits · Inbox**, and
  **Me** (your avatar on phones). Phones: a top bar and a bottom bar with a centre button
  for the role's main action (student: Jobs; founder: Post, which offers "Post a job" or
  "Update what you need"; mentor and investor: Offer; partner admin: Gaps, the
  dashboard). Laptops: a left sidebar with the same places and the action as a button;
  content in a 640px column; from 1280px a right rail with profile strength and people
  worth meeting (students: jobs near you). The map and dashboard use the full width.
  **Discover** has tabs over the browse screens (Matches, Jobs, Startups, Map; students
  start on the map) and **Inbox** holds intro requests for now. Old links (`/map`,
  `/jobs`, `/intros`…) still work. Tap targets are 44px+.
- **Home**: a greeting, then one "next step" card with the path you're on (students:
  Profile → Apply → Shortlist; founders: Profile → Matches → Intros), worked out from
  your profile, applications, intros and circuits; then your top matches (partner
  admins: intros to pass on) and, below 1280px, profile strength.
- **Post a job** (`/jobs/new`, founders who claimed a startup): role, type, pay, what
  they'll do and the skills it needs; students are matched on those skills.
- **Data**: every call goes through the typed client generated from the API's OpenAPI
  spec (`src/api/schema.d.ts`; regenerate with `make api-client`), with TanStack Query.
  A backend test fails if `frontend/openapi.json` is out of date.
- **Demo mode (F9)**: signed out, the welcome screen shows the pitch and the demo people
  grouped by the five stories. Signed in, **Me** shows your profile, verification, three
  stats for your role and a "Switch person" button that opens the same story list.
- **Matches (F4)**: one card per match (score, one-line reason, Bridge badge) with one
  action: "Ask for intro" for people and for startups a founder has claimed, otherwise
  "View startup" or (students) "View job".
- **Onboarding (F1)**: Me → "Edit" (or the link on Matches) opens "What you need and
  offer". Paste a bio and tap "Suggest chips": with an API key the suggested needs,
  offers (students: skills) and traits come pre-selected; without one, the same chips
  are picked by hand from the full lists. "Save and see matches" saves and recomputes
  your matches straight away.
- **Warm intros (F5)**: "Ask for intro" opens a sheet with the path (You → mutual →
  them), the API's one-line explanation, a short reason (10–500 characters) and "Send
  request". If you can't ask yet (verification level, a full week), it says why. The
  **Inbox** lists "To pass on", "For you" and "You asked", each card with the
  buttons the API allows (pass it on, accept, decline, withdraw, rate 1–5), and your
  capacity this week.
- **Circuits (F6)**: each loop card shows the three people in a circle with clockwise
  arrows, the three "who helps whom" lines with everyone's answer, Accept and Decline
  with the hours left, and once active "Rate the help you got".
- **Dashboard (F8)**, for partner admins, top to bottom:
  - three numbers: members, startups hiring, intros made;
  - "What your ecosystem lacks": a ranked bar chart (Recharts) of the 10 biggest gaps,
    needs in blue next to offers in green, values at the bar ends, a tooltip on hover
    and "Show as a table";
  - "Where it's missing": a heat map (MapLibre heatmap layer, one blue hue, brighter =
    bigger gap) with a capability picker that starts on the biggest gap. The map only
    loads when it's about to scroll into view;
  - "Do bridge intros work?": acceptance rate for local vs bridge matches;
  - **Run round now** for exchange circuits.
  Each section loads, fails and retries on its own, and its loading block has the
  section's real size, so nothing jumps. The chart colours were checked for colour
  blindness and contrast on the dark cards.
- **MapLibre's worker**: MapLibre draws street tiles and the heat layer in a web worker.
  `src/map/setup.ts` tells it where the build put the worker file; without that,
  production builds silently drew no streets and no heat.
- **Installable (PWA)**: a manifest (name, standalone, the Circuit mark at 192/512/maskable plus
  an apple-touch-icon; regenerate with `npm run icons`) and a service worker
  (vite-plugin-pwa):
  - The app shell is precached, so it opens instantly and works offline.
  - Your matches, jobs and applications are fetched network-first, and the last copy
    is used offline (screens show "Last updated <time>").
  - The API cache is keyed by URL only, so tokens are never stored in it, and it is
    cleared on sign-out and persona switch.
  - When a new version is deployed, a bar says "Update available, tap to refresh".
  - After the second visit, a one-time "Add Circuit to your home screen" prompt
    appears, with the Share → "Add to Home Screen" steps on iPhone.
- **Map (F2)**: MapLibre with a quiet pitch-black style, built from
  free OpenStreetMap vector tiles (OpenFreeMap, no key; `VITE_MAP_TILES` to change). If
  tiles can't load, the map still works with a plain background and the pins. Pins are
  real buttons, orange for hiring and grey otherwise. The map fits all pins; one "Filters" sheet (hiring, skill, distance);
  tap a pin for a sheet with match %, open roles, "I'm interested" and "View startup".
  MapLibre loads only with the Map tab and is cached the first time it's opened.
- **Startup page and claim (F3)**: views, interested students and applications; for an
  unclaimed startup, founders see "Claim this startup": a work email on the startup's
  domain, then a 6-digit code (shown on screen in demo mode). Founders find it via Me →
  "Find and claim your startup"; Me lists "Your startups".
- **Jobs (F11)**: "Open jobs" (search, one filter sheet: type, pay, distance, skill;
  students sorted by skill match) and "My applications" with status badges. The job page
  highlights the skills you have and keeps "Apply" at the bottom (short note in a sheet).
  Founders open their startup → "See applicants", ranked by skill match (never college),
  and shortlist, hire or pass.
- **Screenshots** for design reviews: `npm run screenshots -- http://localhost:4183`.

## Smart onboarding (F1)

`POST /api/onboarding/suggest {"text": "...pasted bio..."}` asks Claude
(`ANTHROPIC_MODEL`, default `claude-haiku-4-5-20251001`) to suggest needs, offers,
skills and traits. The answer is forced into a JSON schema whose ids can only come
from our fixed lists, and is filtered again on our side. Without `ANTHROPIC_API_KEY`
(or if the call fails) the response is `"source": "manual"` and the UI shows manual
pickers. `POST /api/onboarding/confirm` saves the chosen chips. The pasted text is
never logged or stored by the suggest step.

## Startup map and claiming (F2, F3)

- `GET /api/map/startups/nearby?radius_km=10&hiring=true&capability=...&sort=match`:
  startups within the radius (a hard filter) of your profile location (or `lat`/`lng`,
  or the city centre). `GET /api/map/startups/bbox?min_lat=...` returns what's inside
  the visible map. Each pin has hiring status, sector, open roles, interest count and,
  for students, a **skill match score** (0–100) computed from skills and levels only,
  never from college (`app/skill_match.py`).
- Opening a startup page counts a view (once per person per day; the team doesn't
  count). `POST /api/startups/{id}/interest` is the "I'm interested" button.
  `GET /api/startups/{id}/stats` shows views and interested students to everyone.
- **Claiming**: a founder sends an email on the startup's domain to
  `POST /api/startups/{id}/claim`, then the 6-digit code to `.../claim/verify`. Email
  is simulated: outside production (or with `DEMO_PUBLIC=true`) the code is returned
  as `dev_code`. Only the email's domain and a hash of the code are stored. After
  claiming, the founder can edit the page and see who is interested
  (`GET /api/startups/{id}/interested`).

## Jobs and applications (F11)

- `GET /api/jobs` lists open jobs with filters: `q` (title), `capability`, `type`
  (internship, full_time, …), `paid`, and `radius_km` (a hard distance filter from
  your location). Students get a skill match per job and default to best match first.
  `GET /api/jobs/{id}` adds the full description.
- Students apply once per job with a short note (`POST /api/jobs/{id}/apply`, level 1+)
  and follow their status in `GET /api/applications/me` (submitted, shortlisted,
  rejected, hired, withdrawn).
- The founder who claimed the startup posts and edits jobs, sees applicants ranked by
  skill match (`GET /api/startups/{id}/applicants`; skills are shown, colleges are
  not) and changes status (`PATCH /api/applications/{id}`).
- Applying to a job at an unclaimed startup works: the application waits, the
  startup's stats show `applications_waiting`, and the founder sees it after claiming.
- The map, job list and job page all use the same scoring (`app/skill_match.py`).

## Matching (F4)

- `GET /api/matches` (verification level 2) returns your ranked matches, each with a
  one-line reason and a `is_bridge` flag for cross-sector matches, e.g. *"Kavya Menon
  offers marketing, which you need · both: long sales cycle, technical buyers · across
  sectors (deeptech → biotech) · you both know Nandini Rao"*.
- **Candidates**: local (same city plus a shared trait, a 1–2 hop connection or the same
  sector) merged with bridge (anyone whose offers meet your needs or the reverse, by
  capability or by embedding similarity from pgvector, ignoring sector).
- **Score** = w1·complementarity (both directions) + w2·affinity (shared traits) +
  w3·trust path + w4·timing − w5·load penalty. Weights live in `.env`. All scoring is
  pure functions in `app/matching/scoring.py`.
- **Ranking**: people with no free intro slots are skipped, a startup and its team count
  once, ~25% of results are reserved for bridge matches, and no sector dominates.
- **Students** are matched to jobs within `STUDENT_RADIUS_KM` (a hard filter) using the
  same skill match as the map and job pages; Ravi's top match is the story 3 internship.
- **Embeddings** come from `fastembed` (BAAI/bge-small-en-v1.5, 384 numbers per text) behind
  an `EmbeddingProvider` interface; tests use a deterministic fake.
- Results are precomputed into `match_results` by a background job every
  `MATCH_REFRESH_HOURS` (and by `reset-demo`); `POST /api/matches/refresh` recomputes yours,
  `POST /api/admin/matches/recompute` everyone's, `uv run python -m app.cli compute-matches`
  from the shell.
- **Eval**: `tests/eval/pairs.json` holds 53 hand-labelled good/bad pairs from the seed;
  `make eval` reports agreement and how often good pairs outrank bad ones.

## Warm intros (F5)

- `GET /api/intros/path/{member_id}` (level 2) shows how a request would travel: through
  the best mutual connection within 2 hops (found with a recursive SQL query over
  `connections`), directly if you already know each other, or straight to them if no
  one links you. It also says whether you can ask right now and, if not, why. Example:
  *"Dr. Lakshmi Narayan knows you both (mentorship with you; worked together with Vikram
  Shah). Your request goes to them first."*
- `POST /api/intros` (level 3) sends a request with a short reason. It goes **via the
  mutual** when one exists (or another mutual you pick from `alternatives`).
- Flow: `pending` → the mutual **forwards** (or declines) → the target **accepts** (or
  declines) → the sender **rates** the intro 1–5 (`completed`). Direct requests skip
  the forwarding step. The sender can **withdraw** an open request. Accepting connects the
  two people, so their next path is direct. The target only sees a request once the
  mutual has passed it on.
- **Capacity**: `members.open_intro_slots` is how many requests a person takes on per
  week, counting requests they receive and ones they're asked to pass on. A busy
  mutual is skipped for one with room. Beyond capacity the API answers `429` with a
  polite message and a date (*"Vikram Shah has had a busy week of intro requests.
  They'll have room again from Tue 13 Oct, so please try then."*) and a `Retry-After`
  header. Each member can also send at most `INTRO_REQUESTS_PER_WEEK` requests a week.
- `GET /api/intros/me`: requests you sent, ones waiting for you to pass on, ones you
  received, and your capacity this week. Each request lists the `actions` you can take.
- Requests nobody answers within `INTRO_EXPIRY_DAYS` (14) expire (hourly job).
- Each request records whether the match was a **Bridge match**, for the partner
  dashboard's local vs bridge acceptance rate.

## Exchange circuits (F6)

A circuit is a loop of three people who each help the next: *"You help Arjun Nair with
hiring, Arjun Nair helps Priya Sharma with fundraising, Priya Sharma helps you with
marketing."* Nobody owes anybody, because everybody gives once and gets once.

How a round works (`app/circuits/engine.py` is pure and unit-tested; `service.py` reads
and writes the database):
1. **CAN_HELP edges**: giver → receiver when one of the giver's active offers is the same
   capability as one of the receiver's active needs (a founder's needs include their
   startup's). Only members who opted in (`circuits_opt_in`) with verification level 2+,
   and not already in an open circuit. Edge weight = 0.4 + 0.4 × how closely the offer
   and need texts match (embeddings) + 0.2 × how well they already know each other.
2. **Cycles**: every 3-person loop, found with networkx.
3. **Score**: a loop is only as strong as its weakest link (its lowest edge weight).
4. **Choice**: OR-Tools CP-SAT picks the set of loops with the highest total score
   where nobody appears twice. Simply taking the best loop first can do worse; there's
   a test showing that case.
5. Each chosen loop is saved as a `proposed` circuit. Each person accepts or declines the
   leg where they give help within **72 hours** (`CIRCUIT_CONSENT_HOURS`). All three
   accept → `active`; anyone declines → `declined` (and the same three aren't proposed
   again for 4 weeks); time runs out → `expired`. Once active, each person marks the
   help they received as done and rates it 1–5; all three → `completed`.

Endpoints: `GET /api/circuits/me` (loop cards, each listing your `actions`),
`POST /api/circuits/{id}/accept|decline|rate`, and for admins
`POST /api/admin/circuits/run` ("Run round now"; `?dry_run=true` previews without
saving). The round also runs weekly (`CIRCUIT_ROUND_DAY`, `CIRCUIT_ROUND_HOUR`, UTC), and
an hourly job expires circuits nobody fully accepted in time.

## Partner dashboard API (F8)

Partner admins only (role `partner_admin`, level 3); everyone else gets 403.

- `GET /api/dashboard/gaps`: per capability, active needs (from members and startups)
  vs active offers, biggest gap first. On the seed, regulatory affairs leads with 35
  needs vs 2 offers (story 5).
- `GET /api/dashboard/gaps/areas?capability=regulatory_affairs&cell_km=2`: the same on a
  grid of square cells (about `cell_km` across), each with its centre `lat`/`lng`, for
  the map's heat layer. A need sits where its startup (or member) is; an offer where
  the member is.
- `GET /api/dashboard/stats`: members by role, startups (claimed, hiring), open jobs,
  applications, needs and offers, connections, intros, students who showed interest,
  and circuits by status.
- `GET /api/dashboard/intros`: intro acceptance rate for local vs bridge matches.
  Accepted and completed intros count as accepted; declined and expired as not; open
  and withdrawn ones are left out. On the seed: local 52%, bridge 80%.

## Logs

The API writes one JSON line per request with `request_id`, `method`, `path`,
`status`, `duration_ms` and `user_id`. Query strings, headers and bodies are never
logged, so personal data and tokens stay out of logs. Every response carries an
`X-Request-ID` header matching its log line.

Product actions are also written to the append-only `events` table (ids, counts and
categories only; never names, emails, phone numbers, free text or tokens). A test
(`tests/test_events_coverage.py`) fails if any write endpoint forgets to record one.

## Demo data

```bash
cd backend
uv run python -m app.cli reset-demo   # wipe everything, restore the demo (~2 s). Run before every demo.
uv run python -m app.cli seed         # add/refresh seed data but keep live activity (claims, views)
uv run python -m app.cli migrate      # only apply migrations
uv run python -m app.cli dump-seed    # print the generated startups as crawler-shaped JSON
```

The seed is generated around `CITY_CENTER_LAT`/`CITY_CENTER_LNG` (`CITY_NAME` for
addresses) and is identical on every run: ~150 startups, ~160 jobs (full-time and
internships, paid and unpaid) and ~300 members, students the largest group. Startup domains end in `.example` (a reserved domain) so no seed record
points at a real company. It always contains the five demo stories:

| # | Story | Who |
| --- | --- | --- |
| 1 | Bridge match: biotech needing marketing ↔ deep-tech marketer | HelixRoot Biosciences (Dr. Meera Iyer) ↔ Kavya Menon |
| 2 | 3-person exchange circuit | Asha → Arjun (hiring), Arjun → Priya (fundraising), Priya → Asha (marketing) |
| 3 | Lower-tier college student matched on skills to a nearby hiring startup | Ravi Kumar → LedgerLoop's paid Backend Engineering Intern role (about 1 km away, 100% match) |
| 4 | Warm intro through a respected mentor | Rohan Mehta → Dr. Lakshmi Narayan → Vikram Shah |
| 5 | Capability gap | regulatory affairs: 35 needs, 2 offers |

Demo personas (used by the persona switcher later): student Ravi, founder Meera,
mentor Lakshmi, investor Vikram, partner admin Nandini. TerraGrid Energy (Rohan's
startup) is deliberately unclaimed, with 63 views and 14 interested students, for the
claim-flow demo.

## Database

- Schema changes go through Alembic: edit `app/models.py`, then
  `uv run alembic revision --autogenerate -m "what changed"`, review the file in
  `migrations/versions/`, and `uv run alembic upgrade head`.
- The `events` table is append-only: a database trigger rejects UPDATE and DELETE.
- `docker compose up -d --wait` starts Postgres on port 5432 (change `POSTGRES_PORT`
  in `.env` if something else uses it — and update the URLs to match).
- Two databases are created on first start: `circuit` (app) and `circuit_test` (tests),
  both with PostGIS and pgvector enabled.
- `docker compose down -v` deletes the data volume for a completely fresh start.
