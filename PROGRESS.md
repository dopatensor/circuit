# Circuit — progress

Snapshot for picking the work up in a new session. The spec is [CLAUDE.md](CLAUDE.md)
(including the "Spec additions" and "Testing" sections at the end); setup details are
in [README.md](README.md).

Branch: `claude/youthful-dirac-1uej54`. PR #1 (Phase 0 only) is already **merged** into
`main`. Everything after it (Phases 1–4) is committed and pushed on this branch but not
merged; open a **new** pull request for it.

## Status at a glance

| Phase | State |
| --- | --- |
| 0 Scaffold | ✅ done |
| 1 Data model + seed (+ F11 jobs tables and seed jobs) | ✅ done |
| 2 Auth + profiles, onboarding (F1), verification (F7) | ✅ done |
| 3 Geo + claim (F2, F3) + jobs/applications API (F11) | ✅ done |
| 4 Matching (F4) | ✅ done |
| **5 Intros + events (F5, F10)** | ⏭️ **next: not started** (no work in progress) |
| 6–12 | not started |

Last verified (2026-10-07, at commit `6153556`):

- Backend tests: **185 passed, 1 skipped, 0 failing**. The skipped test
  (`tests/test_embeddings.py::test_real_model_puts_related_sentences_closer`) downloads
  the real embedding model, so it only runs with `RUN_MODEL_TESTS=1`. It passed when run
  that way.
- `ruff check`, `ruff format --check` and `alembic check` (models match migrations) are clean.
- Migrations apply from scratch, downgrade and re-apply (tested in `tests/test_migrations.py`).
- `make demo-check`: **5/5 PASS** on a fresh `make reset-demo`.
- `make eval`: 53 labelled pairs, 100% agreement (see the caveat under "Known issues").
- Frontend: only the Phase 0 placeholder; `npm run build` passes.

## Phase 5: exactly what's left (all of it)

Spec: F5 warm intros and F10 events.

1. **Warm path endpoint**: for any match, return the best mutual connection within 1–2
   hops. `app/graph/PostgresGraph.paths()` already implements the recursive SQL, and a
   test (`tests/test_matching.py::test_graph_paths_use_recursive_sql`) covers it. What's
   missing is the endpoint, e.g. `GET /api/intros/path/{member_id}`, returning the via
   person, the tie strengths and a sentence for the UI.
2. **Intro requests**: `POST /api/intros` with a reason.
   - It goes *via the mutual* when one exists (`via_member`), otherwise direct.
   - It needs verification level 3 (F7: "3 = intros").
   - The `intro_requests` table exists (Phase 1) with `from_member`, `to_member`,
     `via_member`, `status`, `reason`, `is_bridge`, `outcome_rating` and timestamps. It
     probably needs a column for the mutual's step, e.g. `via_status` or a `forwarded`
     status (requested → forwarded by the mutual → accepted or declined by the target).
     That means a new migration.
3. **Capacity**: limits per person per week. Count requests received (as target, and as
   the via person) in the last 7 days against `members.open_intro_slots`. Beyond capacity,
   refuse politely with a friendly 409/429 message such as "Lakshmi has had a busy week —
   try again after <date>". Matching already uses pending requests as `load_penalty`
   (`app/matching/service.py` reads pending `intro_requests`).
4. **Responses and outcome**: endpoints for the mutual to forward or decline, for the
   target to accept or decline, `GET /api/intros/me` (sent and received), and an outcome
   rating of 1–5 after an accepted intro. Mark `is_bridge` from the match when the
   request is created; the Phase 7 dashboard needs it.
5. **Events for every action (F10)**: audit every endpoint and add any missing event.
   Events already exist for profiles, needs and offers, onboarding, startups, views,
   interest, claims, jobs, applications and matches. Add the intro events. Payloads must
   never contain names, emails, phones, free text or tokens.
6. **Tests**: happy path via a mutual; direct path; level below 3 refused; capacity
   refusal; only the right person can forward, accept or rate; events written.
7. **demo-check, story 4**: upgrade it to go through the intro API (Rohan's path to
   Vikram is via Lakshmi). It must not leave data behind: either check the path endpoint
   only, or create and then clean up inside a transaction.
8. README section, full test run, commit "Phase 5: …", explain, stop for OK.

## Remaining phases after 5 (from CLAUDE.md)

- **6 Circuits**:
  - CAN_HELP edges, 3-cycles with networkx, scoring by weakest link, and non-overlapping
    selection with OR-Tools CP-SAT.
  - Weekly round plus an admin "Run round now" button; consent endpoints with a 72-hour
    expiry.
  - Tests on a hand-built graph where the right circuits are known.
  - networkx and ortools are on the approved list but not installed yet.
  - Must reliably find Asha → Arjun → Priya (story 2), then upgrade demo-check story 2.
- **7 Dashboard API**: gap by capability and by area (map heat), network stats, intro
  acceptance local vs bridge (seeded intros already have `is_bridge`). demo-check
  story 5 should switch to the dashboard API.
- **8 Frontend shell**:
  - Tailwind, a client generated with openapi-typescript (no hand-written fetch),
    TanStack Query, layout, persona switcher (F9), login state, verification badges.
  - Playwright tests at phone and laptop widths start here.
  - Ask before adding any frontend dependency that isn't listed (e.g. `openapi-fetch`,
    `@playwright/test`).
- **9 Map view**: MapLibre map, filters, pins and popups (with job counts), interest
  button, startup page with the claim flow; jobs list, job page, apply with a note,
  "My applications" with status badges, founder applicants view (F11).
- **10 Network app**: onboarding chips (F1 UI), matches with reasons and Bridge badges,
  warm intro flow, circuit loop card with accept and decline.
- **11 Dashboard UI**: gap chart (Recharts), map heat layer, stats, acceptance split.
- **12 Demo readiness**: DEMO.md 5-minute script (story 3 includes applying and
  shortlisting), Railway or Render config, final README.

## Decisions and deviations from CLAUDE.md

All of these were explained at the end of their phase; the user confirmed by continuing.

**Dependencies** (approved by the user, or on the spec's list):
- **Added with approval:** uvicorn, pydantic-settings, ruff (dev), @vitejs/plugin-react,
  @types/react and @types/react-dom (Phase 0); PyJWT[crypto] (Phase 2).
- **From the spec's list:** alembic, geoalchemy2, pgvector, anthropic, fastembed,
  apscheduler.
- **Not added:** `@types/node` was avoided, so the Vite proxy target is hard-coded to
  `http://localhost:8000`.

**Data model additions beyond the spec's list:**
- `members.sector` (needed to tell bridge from local matches), `members.auth_subject`
  (JWT `sub`), `members.linkedin_url` (level 2).
- `member_skills.level` (1–3).
- `intro_requests.is_bridge` and `outcome_rating`.
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
- **Story 2 is only checked at the data level** (all three needs and offers exist). That
  the circuit round reliably finds the loop is Phase 6's job.
- **No way to withdraw interest.** "I'm interested" can't be undone, because events are
  append-only and there's no "withdrawn" event yet.
- **`startups.hiring` isn't derived from open jobs.** It's set when a job is created but
  not cleared when every job closes.
- **`jobs.searched` events are noisy:** one is written on every jobs list call, including
  pagination.
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
git checkout claude/youthful-dirac-1uej54
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
