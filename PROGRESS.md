# Circuit — progress

Snapshot for picking the work up in a new session. The spec is [CLAUDE.md](CLAUDE.md)
(including the "Spec additions" and "Testing" sections at the end); setup details are
in [README.md](README.md).

Branch: `claude/kind-noether-bp70jm`. Phases 0–4 are merged into `main` (pull requests
#1–#3 in `dopatensor/circuit`). Phase 5 is committed and pushed on this branch and is
not merged yet; no pull request has been opened for it.

## Status at a glance

| Phase | State |
| --- | --- |
| 0 Scaffold | ✅ done |
| 1 Data model + seed (+ F11 jobs tables and seed jobs) | ✅ done |
| 2 Auth + profiles, onboarding (F1), verification (F7) | ✅ done |
| 3 Geo + claim (F2, F3) + jobs/applications API (F11) | ✅ done |
| 4 Matching (F4) | ✅ done |
| 5 Intros + events (F5, F10) | ✅ done (waiting for the user's OK) |
| **6 Circuits (F6)** | ⏭️ **next: not started** |
| 7–12 | not started |

Last verified (2026-10-07, Phase 5 commit):

- Backend tests: **203 passed, 1 skipped, 0 failing**. The skipped test
  (`tests/test_embeddings.py::test_real_model_puts_related_sentences_closer`) downloads
  the real embedding model, so it only runs with `RUN_MODEL_TESTS=1`.
- `ruff check`, `ruff format --check` and `alembic check` are clean; the new migration
  upgrades, downgrades and re-applies.
- `make demo-check`: **5/5 PASS** on a fresh `make reset-demo` (story 4 now goes through
  the intro API).
- `make eval`: 53 labelled pairs, 100% agreement.
- Frontend: only the Phase 0 placeholder; `npm run build` passes.

## What Phase 5 built (for reference)

- `app/intros.py`: pure helpers (weekly `Load` and the next free date, ranking mutuals,
  path sentences, polite busy messages) plus database helpers (`plan_path` using the
  recursive SQL in `app/graph`, `loads`, `sender_load`, `match_is_bridge`,
  `expire_stale`).
- `app/api/intros.py`: `GET /api/intros/path/{member_id}` (level 2), `POST /api/intros`
  (level 3), `GET /api/intros/me`, and `POST /api/intros/{id}/forward|accept|decline|
  withdraw|rate`. Each response lists the `actions` the caller can take, for the UI.
- Statuses: `pending` → `forwarded` (mutual passed it on) → `accepted` / `declined` →
  `completed` (sender rated 1–5); also `withdrawn` and `expired`. Migration
  `a5cb711b8b42` adds `forwarded`, `withdrawn`, `forwarded_at` and an index on
  `created_at`.
- Capacity: `members.open_intro_slots` per rolling 7 days, counting requests received
  (unless a mutual declined before it arrived) and requests to pass on. Senders: at most
  `INTRO_REQUESTS_PER_WEEK` (5). Refusals are 429 with a dated, polite message and
  `Retry-After`. Rows are locked (`SELECT … FOR UPDATE`) so two requests can't take the
  last slot at once.
- Accepting an intro adds a `connections` row (`source="intro"`, strength 0.5).
- Hourly scheduler job expires requests unanswered for `INTRO_EXPIRY_DAYS` (14).
- Events: `intro.path_viewed`, `intro.requested`, `intro.forwarded`, `intro.accepted`,
  `intro.declined` (`by`: mutual or target), `intro.withdrawn`, `intro.rated`,
  `intro.refused` (capacity), `intro.expired`. `tests/test_events_coverage.py` fails if
  any write endpoint doesn't record an event.
- Matching's load penalty now counts `forwarded` requests as well as `pending` ones.

## Phase 6: exactly what's left (all of it)

Spec: F6 exchange circuits.

1. **Dependencies**: `networkx` and `ortools` are on the spec's approved list but not
   installed. Add them with `uv add` and check that wheels exist for macOS ARM64 and
   Linux x86_64 (OR-Tools does publish both).
2. **CAN_HELP edges**: A → B when one of A's active offers meets one of B's active needs
   (by capability; optionally embedding similarity), only for members with
   `circuits_opt_in`. Each edge has a weight from the match score. Put it behind the
   `app/graph` interface (e.g. `can_help_edges`).
3. **Cycles**: 3-person directed cycles with networkx (`simple_cycles` with
   `length_bound=3`, or a direct triangle search); score each by its **weakest link**.
4. **Choose circuits**: CP-SAT picks non-overlapping cycles (each person in at most one)
   that maximise the total score.
5. **Rounds**: a weekly scheduler job plus an admin `POST /api/admin/circuits/run`
   ("Run round now"). Store `circuits` and `circuit_legs` (tables exist from Phase 1).
   Each leg needs consent, and the offer expires after 72 hours.
6. **Member endpoints**: `GET /api/circuits/me` returns a loop card ("You help X with A,
   X helps Y with B, Y helps you with C"), plus accept and decline. The circuit becomes
   `active` when all three accept and `declined` when anyone declines; afterwards legs
   are marked fulfilled and rated.
7. **Events** for round run, proposed, accepted, declined, expired, fulfilled and rated.
   The events-coverage test will catch any write endpoint without one.
8. **Tests**: a hand-built graph where the right circuits are known (overlapping
   triangles, where the solver must choose the best non-overlapping set); weakest-link
   scoring; consent and expiry; only legs' members can respond.
9. **demo-check, story 2**: run the round (read-only, e.g. a dry-run function) and
   check it finds Asha → Arjun → Priya → Asha. Today it only checks the data.
10. README section, `PROGRESS.md`, full test run, commit "Phase 6: …", explain, stop for OK.

## Remaining phases after 6 (from CLAUDE.md)

- **7 Dashboard API**: gap by capability and by area (map heat), network stats, intro
  acceptance local vs bridge (seeded and live intros have `is_bridge`; `accepted` and
  `completed` count as accepted; ignore `withdrawn`, and count `expired` as not
  accepted). demo-check story 5 should switch to the dashboard API.
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
  warm intro flow (path sentence → request with reason → inbox with the `actions` each
  item lists; show 429 messages as-is), circuit loop card with accept and decline. For
  a *startup* match, the intro target is its claiming founder (no intro if unclaimed);
  this mapping isn't in the API yet.
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
