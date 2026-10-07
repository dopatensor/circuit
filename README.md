# Circuit

A startup ecosystem platform that matches people on what they **need** and what they
can **offer**, across sectors, with exchange circuits and a map of who is hiring nearby.
See [CLAUDE.md](CLAUDE.md) for the full MVP spec and build phases.

**Status:** Phase 3 (map + claim) — map endpoints with a student skill-match score,
view and interest tracking, and claiming a startup via an email on its domain, on top
of auth, profiles and smart onboarding. Browse the API at http://localhost:8000/docs.

## Layout

```
backend/    FastAPI app (Python 3.12, uv)
  app/        config, logging middleware, db, models, API routers, CLI
  app/seed/   capability/trait lists, demo stories, generator, loader
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
cd frontend && npm install && cd ..
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
npm run build               # type-checks and builds
```

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

## Logs

The API writes one JSON line per request with `request_id`, `method`, `path`,
`status`, `duration_ms` and `user_id`. Query strings, headers and bodies are never
logged, so personal data and tokens stay out of logs. Every response carries an
`X-Request-ID` header matching its log line.

Product actions are also written to the append-only `events` table (ids, counts and
categories only; never names, emails, phone numbers, free text or tokens).

## Demo data

```bash
cd backend
uv run python -m app.cli reset-demo   # wipe everything, restore the demo (~2 s). Run before every demo.
uv run python -m app.cli seed         # add/refresh seed data but keep live activity (claims, views)
uv run python -m app.cli migrate      # only apply migrations
uv run python -m app.cli dump-seed    # print the generated startups as crawler-shaped JSON
```

The seed is generated around `CITY_CENTER_LAT`/`CITY_CENTER_LNG` (`CITY_NAME` for
addresses) and is identical on every run: ~150 startups and ~300 members, students the
largest group. Startup domains end in `.example` (a reserved domain) so no seed record
points at a real company. It always contains the five demo stories:

| # | Story | Who |
| --- | --- | --- |
| 1 | Bridge match: biotech needing marketing ↔ deep-tech marketer | HelixRoot Biosciences (Dr. Meera Iyer) ↔ Kavya Menon |
| 2 | 3-person exchange circuit | Asha → Arjun (hiring), Arjun → Priya (fundraising), Priya → Asha (marketing) |
| 3 | Lower-tier college student matched on skills to a nearby hiring startup | Ravi Kumar ↔ LedgerLoop (about 1 km away) |
| 4 | Warm intro through a respected mentor | Rohan Mehta → Dr. Lakshmi Narayan → Vikram Shah |
| 5 | Capability gap | regulatory affairs: 36 needs, 2 offers |

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
