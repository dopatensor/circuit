# Circuit code audit

**Scope:** the whole repository at `d0d092b` (R2 merged), branch `claude/serene-lovelace-p07aec`.
**Date:** 2026-10-13. **Goal:** a production product with real users, not a demo.
**Read:** CLAUDE.md, PROGRESS.md, DESIGN.md, README.md and every file under `backend/app`,
`backend/tests`, `frontend/src`, `frontend/e2e`. There is no PRODUCTION.md.
**No code was changed.** Analysis tools ran temporarily (`uvx` / `npx --yes` from a scratch
directory). Nothing was added to `pyproject.toml`, `package.json` or the lockfiles.

> Short version: the code is clean, small and well tested for its size. It is **not bloated**.
> What stands between it and production is not code quality. It is a handful of
> **production mechanics** that a demo never needed: real sign-in, an admin role separate
> from partner admins, rate limits, a job runner that is safe with more than one server,
> consistent errors, and one N+1 endpoint. Section 6 has the plain-language summary.

Out of scope because the code doesn't exist yet: Clerk on the frontend (the backend
verifies JWKS tokens, but there is no sign-in screen), Firecrawl or any crawler, a
storage layer, a page fetcher and a paid map provider. Where the brief asks about them
(timeouts, interfaces), the answer is "not built". They are listed as gaps, not findings.

---

## 1. Measurements

### 1.1 Lines of code (non-blank)

| Area | Lines | Notes |
| --- | ---: | --- |
| `backend/app` top-level modules | 3,213 | models 625, schemas 893, auth, config, profiles, proof, intros… |
| `backend/app/api` (15 routers) | 2,683 | jobs 540, startups 450, intros 395 |
| `backend/app/seed` | 2,204 | demo data generator and loader (demo-only code) |
| `backend/app/matching` | 833 | scoring 327, service 406 |
| `backend/app/github` | 782 | client, pure extractor, service |
| `backend/app/circuits` | 227 | engine 110 (pure), service 154 |
| `backend/app/graph` + `cache` | 205 | the interfaces CLAUDE.md requires |
| `backend/migrations` | 1,044 | 7 revisions |
| `backend/tests` | 3,648 | 263 test functions, 31 files |
| `frontend/src/screens` (19 screens) | 4,134 | Proof 428, Dashboard 440, Home 364 |
| `frontend/src/components` | 1,028 | plus `components/ds` 972 (design system) |
| `frontend/src/map`, `pwa`, `api`, top-level | 1,066 | |
| `frontend/src/api/schema.d.ts` | 5,039 | generated, not counted as code |
| `frontend/e2e` | 962 | 44 tests × 2 widths |

**Hand-written production code: about 10,100 lines of backend (8,000 without the seed) and
7,200 of frontend.** That is small for 12 features, 74 API operations and 19 screens.

**Largest files:** `schemas.py` 893, `seed/generator.py` 767, `seed/stories.py` 748,
`models.py` 625, `api/jobs.py` 540, `seed/loader.py` 463, `api/startups.py` 450,
`screens/Dashboard.tsx` 440, `screens/Proof.tsx` 428.

### 1.2 Complexity (radon, ruff `C901`, function length)

Backend: 779 functions, **average cyclomatic complexity 2.9 (A)**. 28 functions are over
50 lines; 9 of those are seed data or migrations.

| Function | Lines | Complexity | Comment |
| --- | ---: | ---: | --- |
| `seed/loader.py:127 load_dataset` | 331 | **F (52)** | demo-only, but the worst function in the repo |
| `matching/service.py:230 candidates` | 57 | **E (32)** | production hot path |
| `seed/generator.py:575 _Gen.connections` | 50 | D (26) | demo-only |
| `proof.py:188 student_proofs` | 64 | C (19) | |
| `api/matches.py:28 _describe` | 59 | C (19) | business logic in a router |
| `matching/service.py:102 load_context` | 123 | C (17) | loads the whole database |
| `api/jobs.py:152 list_jobs` | 74 | C (15) | in-memory pagination |
| `matching/ranking.py:25 rank` | – | C (15) | pure, fully tested |
| `auth.py:88 decode_token` | 59 | C (14) | fine: one branch per token type |
| `api/jobs.py:361 applicants` | 94 | C (12) | business logic in a router |

Frontend: 161 components or functions, **18 over 80 lines**. The largest: `Design` 276
(dev-only gallery), `Home.useNextStep` **192** (decision logic inside a hook), `Onboarding.Editor`
179, `ds/Dialog.DialogBase` 147, `StartupPage` 141, `PostJob` 137, `MapView` 137,
`Shell` 137. Deepest JSX nesting: `DemoStories` (13 levels), `Jobs` and `Stepper` (11).

### 1.3 Dead code

| Tool | Result |
| --- | --- |
| `vulture app --min-confidence 60` | Only false positives: 68 FastAPI route handlers and 4 Pydantic validators (called by decorators). **No dead Python functions.** |
| `ruff check` | Clean. |
| `knip` (frontend) | **0 unused files, 0 unused dependencies.** 8 unused exports (`usePersonas`, `initials`, `ExternalButton`, `useIsPhone`, `commitsLine`, `ATTRIBUTION`, `getTheme`, `applyTheme`) and 8 unused exported types. |
| Backend dependencies | All 18 are imported (psycopg through the database URL). |
| Env vars | None dead. 10 settings aren't documented in `.env.example` (`DB_CONNECT_TIMEOUT_S`, `ANTHROPIC_TIMEOUT_S`, `GITHUB_TIMEOUT_S`, `MATCH_RESULTS_PER_MEMBER`, `MATCH_BRIDGE_SHARE`…), nor are the frontend's `VITE_API_URL`, `VITE_MAP_TILES`, `VITE_MAP_GLYPHS`. |
| `jscpd` | **0.49% duplicated** (8 clones, 115 lines; the biggest is inside `ds/Button.tsx`). Tests: 0%. |

**API operations the frontend never calls: 24 of 74.** They fall into three groups, and
only the first is really dead:

| Group | Operations | Recommendation |
| --- | --- | --- |
| **Redundant**: a second way to do what `POST /api/onboarding/confirm` does | `POST /members/me/needs`, `POST /members/me/offers`, `PUT /members/me/skills`, `PUT /members/me/traits`, `PATCH`/`DELETE /needs/{id}`, `PATCH`/`DELETE /offers/{id}`, `POST /startups/{id}/needs` | Delete (about 230 lines with tests), or adopt them in the UI and drop the replace-everything confirm. Keep one way. |
| **Unused**: built without a consumer | `GET /map/startups/bbox`, `GET /members` (browse people; only an e2e test uses it), `GET /startups/{id}/interested` | Delete `bbox` unless map panning is planned. Keep the other two only if R3/R4 screens will use them. |
| **Missing UI**: production needs these | `POST /members/me` (create a profile), `DELETE /members/me`, `PUT /admin/members/{id}/verification` (F7 says admins set levels), `POST`/`PATCH`/`DELETE /startups`, `PATCH /jobs/{id}` (edit or close a job), `POST /applications/{id}/withdraw`, `PATCH /proof/items/{id}`, `POST /admin/matches/recompute`, `/health*` | Keep. These are gaps in the frontend, not dead code. |

### 1.4 Duplication found by reading (structural, not copy-paste)

- **Dependency aliases defined per router:** `BrowseUser` ×4, `AdminUser`/`PartnerAdmin` ×3, `MatchUser` ×2. These belong in `auth.py`.
- **"Get or 404" helpers:** 7 near-identical ones (`_get`, `_job_or_404`, `_member_or_404`, `_owned_need`…).
- **Distance from a point:** `ST_Distance(...)/1000` plus `lat_lng_columns` built in 5 places (`api/jobs.py` ×2, `api/startup_map.py`, `matching/service.py`, `geo.py`); `MAX_RADIUS_KM` is defined twice.
- **Two UI kits:** `components/ui.tsx` and `components/Sheet.tsx` re-export or wrap `components/ds` under the old names, and **14 files** still import them. `index.css` keeps the old colour aliases (`blue`, `green`, `surface`), used 11 times.
- **The same endpoint under several cache keys:** `/api/matches` (`["matches"]`, `["matches","top"]`, `["me-stat",…]`), `/api/intros/me` (`["intros"]`, `["intros","me","home"]`). Invalidation still works by prefix, but there is no key factory, so a new screen can easily miss it.
- **`# fmt: skip` 82 times:** hand-formatted event calls that the formatter would otherwise reflow. Two styles side by side.

### 1.5 Frontend bundle (production build, gzipped)

| Chunk | gzip | Loaded when |
| --- | ---: | --- |
| `index` (app shell) | **141.9 KB** | first load (budget 250 KB; `npm run size` says 140.5 KB) |
| `maplibre` | 282.0 KB | map or dashboard (lazy, not precached) |
| `Dashboard` (Recharts) | 106.5 KB | partner admins only (lazy) |
| largest screens | 2–4 KB each | per route (Proof 3.6, Design 3.8, Home 3.2) |
| CSS | 8.0 KB + 10.7 KB MapLibre | |

What's inside the 430 KB raw first-load chunk (source-map-explorer): react-dom **47%**,
**motion + framer-motion 20.9%** (88 KB raw), react-router 8.8%, our own code 8.2%,
TanStack Query 7.4%, **@use-gesture 4.6%**, openapi-fetch 1.5%. Motion and use-gesture
(about **25% of the first load**) are only used by sheets, dialogs and toasts.

### 1.6 Tests: coverage, speed, flakiness

- **Backend: 271 passed, 1 skipped in 153 s.** Coverage with plain `pytest-cov` reads **82%**,
  but that is a measurement artifact: SQLAlchemy's async layer switches greenlets and
  coverage loses track of router code. With `concurrency = greenlet,thread` the real
  figure is **96% (4,955 statements, 215 missed)**.

| Critical path | Line coverage | What's missing |
| --- | ---: | --- |
| Auth (`auth.py`, `api/auth.py`, `api/admin.py`) | 97% / 100% / 95% | provider (JWKS) path only tested with a local key set |
| Permissions (level and role checks) | covered per endpoint | **no test that a partner admin cannot do platform-admin things**, because the two aren't separated (§3.4) |
| Matching (`matching/*`) | 97–99% | no scale test (O(N²) candidates) |
| Circuits (`circuits/*`, `api/circuits.py`) | 99% | **no concurrency test** (two rounds at once) |
| Applications (`api/jobs.py`) | 95% | no race test (apply twice at the same moment) |
| Intros | 97–99% | no race test for the last free slot |
| Dashboard scoping | 100% of lines | **there is no scoping to test**: every partner admin sees the whole platform |
| Scheduler | **48%** | the job wrappers (error handling, sessions) are untested |
| `cli.py` | 60% | |

- **No test anywhere runs two requests concurrently** (`asyncio.gather` appears in no test). The locking code in intros, circuits and claims is therefore untested.
- **Slowest backend tests:** 19.2 s session seed setup (once), 15.1 s `test_admin_recompute`, 14.3 s `test_refresh_job_recomputes_matches` (both recompute all 300 members), 6.7 s reseed. Everything else is under 3 s.
- **The test database is shared and tests must run serially** (PROGRESS.md). Tests mutate seed rows and restore them, so the suite is order-sensitive and can't be parallelised.
- **Frontend: no unit tests at all.** Logic such as `useNextStep`, `strengthItems` and `sentenceFor` is only reached through Playwright.
- **Browser tests: 84 passed, 2 skipped (phone-only checks) in 12.5 min** (this run, both
  widths). 46 of 84 take over 10 s, mostly because tests reset the demo database (about 6 s,
  in `beforeEach` for mutating specs). The slowest: story 3 apply → shortlist (19.6–23.7 s),
  story 4 intro (17.6 s), the claim flow (17.6 s), the story 2 round (17.1 s). Resetting
  once per spec file and restoring only what a test changes would roughly halve the run.
- Known flake (PROGRESS.md): `pwa.spec.ts` offline test, once in about 60 runs. Two `waitForTimeout` sleeps in `design.spec.ts`.

### 1.7 Queries: N+1, indexes, unbounded reads

Measured on the seeded database (300 members, 150 startups) with a SQLAlchemy cursor counter:

| Endpoint | Queries | Time | Verdict |
| --- | ---: | ---: | --- |
| `GET /api/startups?limit=20` | **115** | 395 ms | **N+1**: `startup_out()` per row (5–6 queries each) |
| `GET /api/startups?limit=100` | **554** | 770 ms | **N+1** (the frontend's Startups tab and search use it) |
| `POST /api/matches/refresh` | 24 | 280 ms | loads the **whole database** (`load_context`) to recompute one member |
| `GET /api/jobs` (student) | 9 | 90 ms | batched, but reads up to 1,000 rows and paginates in Python |
| `GET /api/members/{id}`, `/members/me` | 10–11 | 19 ms | fine (7 small queries per profile) |
| `GET /api/startups/{id}`, `/jobs/{id}`, `/map/.../nearby` | 10 | 27–48 ms | fine |
| `GET /api/matches`, `/intros/me`, dashboard | 3–8 | 15–43 ms | fine |

- **Unbounded or capped silently:** `GET /api/jobs` fetches `MAX_SCAN = 1000` rows, then sorts and slices in Python, so `total` is wrong past 1,000 jobs. `GET /startups/{id}/applicants`, `GET /applications/me`, `GET /startups/{id}/interested` and `GET /dashboard/gaps/areas` have no limit. `GET /intros/me` stops at 200 and `GET /circuits/me` at 50, with no paging.
- **Whole-table loads in jobs:** `compute_all` and `load_context` read every member, startup, need, offer, trait and connection into memory. Candidate generation is O(members²): 300 members take **8.1 s** today (seed log).
- **Indexes:** good coverage. GIST on both locations, HNSW on both embedding columns, partial indexes on active needs and offers and open jobs, unique constraints where races matter. Missing: (a) trigram indexes for the `ILIKE '%q%'` searches on startups, members and jobs (sequential scans; fine below about 10k rows); (b) a composite `events (type, target_type, target_id, actor_id)` index. The events table is used as **state** (interest, view dedupe, stats) on every startup page view, and it grows without bound.
- **Every read is a write:** 9 GET endpoints insert an event and commit (`/jobs`, `/jobs/{id}`, `/members/{id}`, `/startups/{id}`, `/matches`, `/intros/path/{id}`, 4× dashboard). That adds write load and WAL, and stops these endpoints being served from a read replica or HTTP cache.

---

## 2. Bloat and over-engineering

**Verdict: little bloat. The code follows Occam's razor better than most MVPs.** The
abstractions that exist are the ones CLAUDE.md asks for.

### 2.1 Abstractions

| Abstraction | Implementations | Verdict |
| --- | --- | --- |
| `EmbeddingProvider` (fastembed, fake) | 2 | Required by the spec. Keep. |
| `GraphStore` / `PostgresGraph` | 1 | Required (future Neo4j). Keep. |
| `MatchCache` / `PostgresMatchCache` | 1 | Required (future Redis). Keep. |
| `Suggester` / `AnthropicSuggester` | 1 | Borderline, but it gives the "no key" fallback a seam and makes tests easy. Keep. |
| GitHub `Transport` dependency | 1 (tests swap it) | Fine as a test seam, but `api/members.py` imports it from `api/proof.py` (router-to-router coupling). Move it to `app/github`. |
| `profiles.py` / `jobs.py` / `proof.py` "assemblers" | – | Useful, not over-engineered. |

There are no needless factories, base classes or plugin systems.

### 2.2 Features, flags or code paths outside CLAUDE.md

- **Redundant API surface** (§1.3): the per-item need, offer, skill and trait endpoints, plus `bbox`.
- **`/design` gallery** (`Design.tsx`, 340 lines): dev and test only, gated by `VITE_DESIGN_PAGE`. Fine to keep; make sure production builds never set the flag.
- **PWA offline cache and install prompt:** not in CLAUDE.md, but in DESIGN.md (approved). Keep, but it adds failure modes (the known flake, cached API data).
- **`withdraw` for applications, `delete` for startups, the sender rate limit for intros:** beyond the spec, sensible for production. Keep.
- **`DEMO_PUBLIC`, persona switcher, `dev_code`:** spec-required demo features; they must stay off in production (see §2.5).

### 2.3 Business logic in routers or components

| Where | What | Should live in |
| --- | --- | --- |
| `api/jobs.py` `_job_outs` (56 lines), `applicants` (94), `list_jobs` sorting | assembling jobs, ranking applicants | `app/jobs.py` (service) |
| `api/matches.py` `_describe` (59, complexity 19) | turning cached matches into cards | `app/matching/` |
| `api/circuits.py` `_cards`, `_answer`, `loop_sentence` | the consent state machine and loop sentences | `app/circuits/service.py` |
| `api/intros.py` `_check`, `_role_and_actions`, `_out` | refusal rules, the intro state machine | `app/intros.py` (already half there) |
| `api/startups.py` claim flow, view dedupe, stats | claim state machine | `app/claims.py` (already exists, pure parts only) |
| `api/members.py` LinkedIn → level 2 upgrade | verification rule | `app/verification.py` or `auth.py` |
| `screens/Home.tsx` `useNextStep` (192 lines) | "what to do next" decision tree | a pure `nextStep(profile, apps, matches…)` function plus a hook |
| `MatchCard.tsx`, `Home.tsx` | `subtitle.split(" · ")[0]` to recover a startup name | add `startup_name` to `MatchOut` (additive API change) |
| Screens in general | 74 `useQuery`/`useMutation` calls inline; only 3 shared hooks in `api/hooks.ts` | per-domain hooks (`useJobs`, `useIntros`…) with a query key factory |

55 `session.commit()` calls live in routers. That's acceptable in FastAPI, but it means
transaction boundaries are decided per endpoint rather than in one place.

### 2.4 Inconsistent patterns

- **Error bodies:** almost everything returns `{"detail": "<sentence>"}`, but `POST /api/startups` returns `{"detail": {"message", "startup_id"}}`, which the frontend's `sentenceFor` can't read (it falls back to a generic message). Pydantic 422s return a list. There is **no global exception handler**, so an unexpected error returns Starlette's plain-text 500 with no request id in the body.
- **Status codes:** "wrong claim code" and "email not on the domain" are 422 (validation) while expired is 410; "already applied" is 409 and "already rated" is 409. Mostly fine, but undocumented.
- **Pagination:** `Page[T]` with limit and offset (members, startups, jobs); bare lists with a hidden cap (intros 200, circuits 50); bare lists with no cap (applications, applicants); `limit` without offset (matches, dashboard gaps).
- **Data fetching:** `unwrap` and `withMeta` are used consistently (good), but query keys are ad hoc strings and the endpoints behind "me" stats are fetched just to count things (PROGRESS.md already notes a `/members/me/summary` would be cleaner).
- **Two component layers** (`ui.tsx` vs `ds/`), described in §1.4.
- **Validation:** consistently Pydantic on the backend (good). The frontend re-implements some limits (chip counts 10/10/15/10, reason 10–500 characters) as constants that can drift from the API.
- **Logging:** consistent (structlog JSON, no PII found). Good.

### 2.5 Demo, debug or experimental code that must not reach production

| Item | Current guard | Risk |
| --- | --- | --- |
| `DEMO_AUTH` persona login | refused at start-up in production unless `DEMO_PUBLIC=true` | OK. With `DEMO_PUBLIC`, **anyone can log in as the partner admin persona** and set verification levels or run rounds. Acceptable only on a fake-data deployment. |
| `dev_code` returned by claim start | only outside production or with `DEMO_PUBLIC` | OK. |
| `reset-demo` (TRUNCATE everything) | `cli.py` refuses in production unless `DEMO_PUBLIC` | OK. |
| Frontend has **no real sign-in**: `Welcome` only lists demo personas; `auth.tsx` says "only demo logins exist so far" | none | **Blocker**: a production build has no way to sign up or sign in. |
| `/design` page | build flag | OK if the production build never sets `VITE_DESIGN_PAGE=1`. |
| `app/seed/catalog.py` (capabilities and traits) is imported by production code (`onboarding`, `dashboard`, `schemas`) | – | It's production reference data living in the demo package. Move it to `app/catalog.py`. |
| `api/auth.py` imports `DEMO_PERSONAS` from `app.seed.stories` | – | Pulls 748 lines of demo stories into the production import graph. Load lazily or move the persona list. |

---

## 3. Production readiness of the code

### 3.1 External calls: timeouts, errors, retries

| Call | Timeout | Error handling | Retries | Verdict |
| --- | --- | --- | --- | --- |
| Anthropic (onboarding) | 20 s | rate limit, status and connection errors → `manual` fallback | `max_retries=1` | Good. **No rate limit on our side**: every signed-in user (even level 0) can call it, and each call costs money. |
| JWKS (Clerk/Supabase) | 5 s, keys cached 1 h, run in a thread | unknown key → 401 | refetch on unknown `kid` | Good. |
| GitHub OAuth and API | 10 s | 401 → revoked; 403/429 → `RateLimited(reset)`; 5xx/network → error; writes only after a full success | rescheduled (reset + 1 min, or +1 h) | Good. Revoke is best effort. |
| fastembed model | – | – | – | Runs in a thread (good). **The ~130 MB model downloads on first use**, which can be inside a user's `POST /matches/refresh` after a deploy. Download it at build time. |
| Map tiles (OpenFreeMap) | browser only | MapLibre handles failures; tests block tiles | – | No backend call. Fine. |
| Postgres | 5 s connect | `pool_pre_ping` | – | **No `statement_timeout`, no pool size settings, no request timeout.** One slow query can tie up a connection indefinitely. |
| Email (claims) | – | 503 in production | – | **Not built.** Claiming is impossible in a real deployment. |
| Clerk frontend, Firecrawl, storage, page fetcher | – | – | – | **Not built.** |

### 3.2 Transactions and race conditions

| Scenario | Protection | Verdict |
| --- | --- | --- |
| Double apply | unique `(job_id, member_id)` + `IntegrityError` → 409 | ✅ correct, **untested concurrently** |
| Double intro request, last free slot | `SELECT … FOR UPDATE` on all involved members in id order (no deadlock), then re-plan | ✅ well designed, **untested concurrently**. Add a partial unique index on open `(from_member, to_member)` as a backstop. |
| Circuit consent (three people answering at once) | circuit and legs `FOR UPDATE` | ✅ |
| Claim verify (two founders) | conditional `UPDATE … WHERE claimed_by IS NULL` | ✅ |
| **Two circuit rounds at once** (admin "Run round now" while the weekly job runs, or two API replicas each running the scheduler) | **none**: `busy_members` is read before the insert, no lock | ❌ The same person can land in two proposed circuits. |
| **Scheduler with more than one process** | APScheduler `max_instances=1` is per process only | ❌ With 2 replicas every job runs twice: matches are recomputed twice, rounds double up. |
| **Match refresh during the 6-hourly recompute** | `compute_all` holds one long transaction for all members; `/matches/refresh` deletes and inserts the same member's rows | ⚠️ Plausible unique-violation 500 or lock wait. Not reproduced. |
| Student withdraws while founder hires | no lock on the application | ⚠️ Last write wins; a withdrawn application can end up "hired". Minor. |
| Featuring the 7th repo (max 6) | count-then-update | ⚠️ Minor. |
| "I'm interested" and view counting | check-then-insert | ✅ Counts use `DISTINCT`, so duplicates don't show. |

### 3.3 Idempotency and jobs

- `refresh_matches`, `expire_stale` and `refresh_github` are idempotent. Re-running them is harmless (apart from the cost).
- **`circuit_round` is not idempotent per week.** A second run in the same ISO week proposes more circuits among whoever is left. It needs a per-round lock and a check like "round already ran for this round_key".
- **CPU work blocks the event loop:** `choose_circuits` (CP-SAT, up to `SOLVER_SECONDS = 10`), `find_cycles` (networkx) and `network_matches` scoring run inside async functions without `to_thread`. While a round or recompute runs in the API process, **every request waits**. Embeddings and JWKS already use threads.
- **`refresh_matches` is one transaction** around embedding and recomputing everyone. It's long, holds row locks on `match_results`, and one failure discards all of it.
- POST endpoints that create things (`create_job`, `create_startup`, `add_item`) aren't idempotent: a double click creates two. A unique constraint or `Idempotency-Key` would fix the important ones.

### 3.4 Security (found while reading)

| # | Finding | Severity for production |
| --- | --- | --- |
| S1 | **Partner admin = platform superuser.** `require_admin()` means "partner_admin at level 3". Any college or incubator admin can set any member's verification level (including to 3, which unlocks intros), run circuit rounds for everyone, recompute all matches, and read the whole platform's dashboard. There is no "platform staff" role and no partner → ecosystem link. | **High** |
| S2 | **No rate limiting anywhere.** LLM cost (`/onboarding/suggest`, open to level 0), expensive recomputes (`/matches/refresh`, 280 ms and growing with N), claim code guessing, demo login. | **High** before public launch |
| S3 | **Claim codes can be brute-forced over time.** 5 wrong attempts expire a claim, but starting a new claim is unlimited and supersedes the old one. With real email this needs a per-member and per-startup limit on claim starts. | Medium (once email exists) |
| S4 | **Level 2 is self-asserted.** Typing any LinkedIn URL upgrades level 1 → 2 with no check. Level 2 unlocks matches and `/intros/path/{id}`, which reveals who knows whom (the social graph). Spec-conformant, but trivially bypassed. | Medium |
| S5 | **Profile enumeration at level 1:** `GET /api/members?q=` searches every member's name and bio and returns name, role, sector, city. Fine for a closed beta; a privacy decision for launch. | Low–medium |
| S6 | **Token in localStorage, no Content-Security-Policy or security headers** (HSTS, X-Frame-Options, Referrer-Policy) on the API or the static site. React escaping makes XSS unlikely; a CSP makes it much less damaging. | Low–medium |
| S7 | The GitHub token encryption key and the OAuth `state` signing key are both derived from `GITHUB_CLIENT_SECRET`. Rotating the secret silently disconnects everyone. Use `GITHUB_TOKEN_KEY` as required in production. | Low |
| S8 | Events keep `actor_id` after a profile is deleted. Ids are pseudonymous, so it's acceptable, but write it down for privacy requests. | Low |

Checked and fine: IDOR checks on needs, offers, applications, intros (a target can't see a
request before the mutual passes it on), circuits, proof repos and items; JWT algorithm
confusion (HS256 and RS/ES verified separately, demo subjects can't come from the provider);
production refusal of `DEMO_AUTH`; no PII in logs or event payloads (only the claim's email
domain); user links restricted to http/https; `partner_admin` not self-assignable; claim
codes hashed and compared in constant time.

### 3.5 Type safety

| Check | Result |
| --- | --- |
| `mypy app` (default) | **83 errors** in the backend. Mostly `str` passed where a `Literal` is expected (roles, statuses), `datetime \| None` passed on, and SQLAlchemy typing. A couple are real (`generator.py:609` reuses a variable for two types). |
| `mypy app --strict` | **285 errors in 44 of 62 files**: 122 untyped functions, 48 functions take an untyped `session` parameter, 47 bare generics (`dict`, `list`), 17 returning `Any`. |
| `Any` in backend source | 2 uses. |
| `tsc -b` (strict) | **Clean.** 0 `any`, 0 `@ts-ignore`, 3 type assertions. |
| `tsc` with `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` | 40 errors (array or map access assumed defined). |

The frontend's types come from the generated OpenAPI client, which is a strong guarantee.
The backend relies on Pydantic at the edges, but its internals aren't type-checked at all.

### 3.6 API design consistency

- **Naming** is consistent: `/api/<plural>`, `/me` for self, verbs as sub-resources for state changes (`/accept`, `/withdraw`, `/claim/verify`). Good.
- **Pagination, error format and status codes** are inconsistent (§2.4).
- **No versioning.** There are no external API consumers yet, so contract-breaking cleanups (deleting the redundant endpoints) are cheap **before launch**. After launch, add `/api/v1` or additive-only rules.
- The OpenAPI client is checked in and a test fails when it's stale. Good.

---

## 4. Verdict per module

Effort: S ≤ 1 day, M 2–4 days, L 1–2 weeks. **No module needs a rewrite.**

### Backend

| Module | Verdict | Reason | Risk | Effort |
| --- | --- | --- | --- | --- |
| `main.py`, `config.py`, `db.py`, `logging.py`, `events.py` | **KEEP** (+ small additions) | Clean. Add an exception handler, pool and statement timeouts, security headers. | Low | S |
| `auth.py` | **REFACTOR** | Sound token handling. Add a platform-admin role separate from `partner_admin`, and move the shared `BrowseUser`/`MatchUser`/`AdminUser` aliases here. | Medium (authorization) | S |
| `api/auth.py`, `api/admin.py` | **REFACTOR** | Admin endpoints move to platform admins. Stop importing demo stories eagerly. | Medium | S |
| `api/members.py`, `api/needs.py` | **REFACTOR** | Remove the redundant need, offer, skill and trait endpoints (or adopt them). Move the LinkedIn upgrade rule out of the router; stop importing `Transport` from another router. | Low | S |
| `api/startups.py`, `claims.py` | **REFACTOR** | Batch `startup_out` (554 → about 8 queries). Move the claim state machine into `claims.py`. Rate-limit claim starts. | Low–medium | M |
| `api/jobs.py`, `jobs.py`, `skill_match.py` | **REFACTOR** | Move `_job_outs` and `applicants` into the service; SQL-level pagination instead of `MAX_SCAN`. `skill_match.py` is pure and good: KEEP. | Medium (ranking must not change) | M |
| `api/startup_map.py`, `geo.py` | **REFACTOR** | Delete `bbox` (or use it); share the distance helper. | Low | S |
| `api/matches.py` | **REFACTOR** | Move `_describe` into matching; rate-limit `/refresh`. | Low | S |
| `matching/scoring.py`, `ranking.py`, `reasons.py`, `evaluate.py` | **KEEP** | Pure, 97–99% covered, eval at 100%. | – | – |
| `matching/service.py` | **REFACTOR** | Split `candidates()` (E-32). Incremental recompute for one member without loading the whole database. Run scoring off the event loop. | Medium (scores must stay identical: eval + demo-check guard it) | M |
| `intros.py`, `api/intros.py` | **KEEP** (light refactor) | The best-designed area: correct locking, polite refusals, pure helpers. Move `_check` and `_out` into `intros.py`; add concurrency tests. | Low | S |
| `circuits/engine.py` | **KEEP** | Pure, 99% covered, deterministic. | – | – |
| `circuits/service.py`, `api/circuits.py` | **REFACTOR** | Advisory lock and once-per-round guard; solver in a thread; move cards and the consent state machine out of the router. | Medium | S–M |
| `dashboard.py`, `api/dashboard.py` | **KEEP** now, **REFACTOR** with tenancy | SQL is fine. Scoping needs a partner → ecosystem model first (product decision). | Medium (schema) | M |
| `onboarding.py`, `api/onboarding.py` | **KEEP** | Good fallback design. Add a rate limit; fix the 3 `type: ignore`s. | Low | S |
| `github/*`, `proof.py`, `api/proof.py` | **KEEP** | Recent, well tested (91–99%), handles rate limits properly. Require an explicit token key in production. | Low | S |
| `graph/`, `cache/`, `embeddings.py` | **KEEP** | Spec-required interfaces, small. Pre-download the model at build time. | – | S |
| `scheduler.py` | **REFACTOR** | Leader lock (Postgres advisory) or a separate worker process; per-job transactions; tests (48% today). | Medium | S–M |
| `profiles.py` | **KEEP** | Add a batched variant for lists. | Low | S |
| `schemas.py` (893 lines) | **REFACTOR** (optional) | Split by domain (`schemas/jobs.py`…). Mechanical. | Low | S |
| `models.py`, `migrations/` | **KEEP** | Good constraints and indexes. Add the trigram and events indexes and the open-intro partial unique index in new migrations. | Low | S |
| `seed/*`, `demo_check.py`, `cli.py` | **KEEP** (demo tooling) | Move `catalog.py` out of `seed/`. Optionally split `load_dataset` (F-52). Keep out of the production import path. | Low | S |

### Frontend

| Module | Verdict | Reason | Risk | Effort |
| --- | --- | --- | --- | --- |
| `api/client.ts` | **KEEP** | One client, typed, readable errors. | – | – |
| `api/hooks.ts` + inline queries in screens | **REFACTOR** | Per-domain hooks and a query key factory; screens stop calling `api.GET` directly. | Low (Playwright guards it) | M |
| `auth.tsx`, `Welcome.tsx`, `DemoStories.tsx` | **REFACTOR** (extend) | Add a real provider sign-in (Clerk or Supabase, a new dependency to approve) and a "create your profile" screen; keep demo login behind the flag. | Medium | M |
| `components/ds/*` | **KEEP** | The design system, recent and consistent. | – | – |
| `components/ui.tsx`, `components/Sheet.tsx`, colour aliases | **REFACTOR → delete** | Migrate the 14 importing files to `ds`, then delete. | Low | S |
| `screens/Home.tsx` | **REFACTOR** | `useNextStep` (192 lines) → a pure function plus a small hook; stop parsing `subtitle`. | Low | S |
| `screens/Onboarding.tsx`, `Proof.tsx`, `StartupPage.tsx`, `PostJob.tsx` | **REFACTOR** (light) | Extract hooks and sub-components from the 130–180-line components. | Low | S each |
| `screens/Dashboard.tsx`, `map/*`, `pwa/*` | **KEEP** | Recent, tested, sensibly lazy-loaded. | – | – |
| `screens/Design.tsx` | **KEEP** | Dev-only gallery. | – | – |
| Bundle (motion, use-gesture) | **REFACTOR** | Load them with the first sheet or dialog instead of at start-up (about 25% of first-load JS). | Low | S |

### Tests

| Area | Verdict | Effort |
| --- | --- | --- |
| Backend unit and API tests | **KEEP**; add concurrency tests, scheduler tests, admin-vs-partner authorization tests; record coverage with the greenlet setting | M |
| Shared test database, serial run | **REFACTOR** later: a transaction-per-test fixture or a template database would allow parallel runs. Not urgent (153 s). | M |
| Playwright e2e | **KEEP**; replace the two `waitForTimeout` sleeps | S |
| Frontend unit tests | **ADD** (Vitest would be a new dependency, so it needs your approval) for `nextStep`, `strengthItems`, `sentenceFor` | S |

---

## 5. Sequenced plan

Every step is one small commit with before and after numbers. Each keeps `uv run pytest`,
`ruff`, `npm run build`, `npm run size`, the Playwright suite and **`make demo-check` (5/5)**
green. API contracts are preserved unless the step says so (before launch there are no
external clients, so removals are allowed if you approve them; after launch they'd be
versioned). **Where a module lacks the tests a refactor needs, the test commit comes first.**

### Phase A: quick wins (low risk, about 1 day in total)

| Step | Change | Before → after (expected) | Needs your decision? |
| --- | --- | --- | --- |
| A1 | Delete the 8 unused frontend exports and 8 unused types (knip list). | knip: 16 findings → 0 | no |
| A2 | Move `BrowseUser`, `MatchUser`, `AdminUser` and a generic `get_or_404` into `auth.py`/`db.py`. | 9 alias definitions → 3; 7 helpers → 1 | no |
| A3 | Migrate the 14 files from `ui.tsx`/`Sheet.tsx` to `components/ds`, delete both files and the colour aliases. | 2 UI layers → 1; about −130 lines | no |
| A4 | Delete the redundant need, offer, skill and trait endpoints and `POST /startups/{id}/needs` (onboarding/confirm stays the one way), and their tests. Regenerate the OpenAPI client. | 74 → 65 operations; about −230 lines | **yes** (API removal; or keep them and add UI) |
| A5 | Delete `GET /api/map/startups/bbox` and its tests (unless map panning is planned). | 65 → 64 operations; about −50 lines | **yes** |
| A6 | Move `seed/catalog.py` → `app/catalog.py`; load demo personas lazily in `api/auth.py`. | production imports of `app.seed`: 4 → 0 | no |
| A7 | Document the 10 undocumented settings and 3 `VITE_*` variables in `.env.example`. | – | no |

### Phase B: tests before the refactors that need them (about 2 days)

| Step | Change | Why first |
| --- | --- | --- |
| B1 | Coverage config (`concurrency = greenlet,thread`) and a `make coverage` target. Needs `pytest-cov` as a dev dependency. | So every later step reports a true number (96% today). **Dependency: yes.** |
| B2 | Concurrency tests with `asyncio.gather`: double apply, two intro requests for the last slot, three consents at once, two claim verifies, **two circuit rounds at once** (expected to fail today; marked `xfail` until C2). | Proves the locks that exist and exposes the ones that don't. |
| B3 | Scheduler tests: each job wrapper commits, logs and survives an exception. | 48% → about 95% before C2 touches it. |
| B4 | Authorization tests for the future split: a partner admin may read the dashboard but may **not** set levels, run rounds or recompute (`xfail` until C1). | Defines S1's fix before writing it. |
| B5 | Snapshot tests of `GET /api/jobs`, `/startups`, `/matches` and applicant ordering on the seed. | Lets C5–C7 prove they're behaviour-preserving. |

### Phase C: refactors ordered by production risk reduction

| Step | Change | Risk removed | Effort |
| --- | --- | --- | --- |
| C1 | **Separate platform admins from partner admins** (a `staff` role or flag; partner admins keep the dashboard). Migration plus `require_staff()`. | S1 | S |
| C2 | **Scheduler safety:** a Postgres advisory lock per job (`pg_try_advisory_xact_lock`), one circuit round per `round_key`, solver and scoring via `anyio.to_thread`, and an option to run jobs in a separate worker process (`SCHEDULER_ENABLED=false` on web replicas). | double rounds, double recomputes, blocked event loop | S–M |
| C3 | **Rate limits without a new dependency:** a small Postgres-backed limiter (counting recent events per actor) on `/onboarding/suggest`, `/matches/refresh`, claim start and demo login. (Or `slowapi`, if you'd rather approve a dependency.) | S2, S3, LLM cost | S |
| C4 | **One error format:** a global exception handler (JSON with `detail` and `request_id` on 500s), fix the dict `detail` on `POST /startups`, document status codes. | inconsistent errors, untraceable 500s | S |
| C5 | **Kill the N+1:** a batched `startup_outs()` for `GET /api/startups`. | 554 → about 8 queries; 770 ms → under 100 ms | S |
| C6 | **Database guardrails:** pool size and overflow settings, `statement_timeout`, migrations for the trigram, events composite and open-intro partial unique indexes. | runaway queries, slow searches | S |
| C7 | **SQL pagination for jobs** (sort by distance or newest in SQL; match sort pre-filtered by the cached match score or a bounded candidate set) and caps on the other unbounded lists. | wrong totals past 1,000, memory growth | M |
| C8 | **Stop writing on reads:** keep view events where the product uses them (startup views, which drive F3), and drop or sample `jobs.searched`, `matches.viewed`, `dashboard.viewed` and `member.viewed`. | write load on every GET | S |
| C9 | **Move business logic out of routers** (jobs, matches, circuits, intros, claims) into services, one module per commit. B5's snapshots must stay identical. | testability, consistency | M |
| C10 | **`matching/service.py`:** split `candidates()`, incremental per-member recompute (no whole-database load for `/refresh`), per-batch transactions in `compute_all`. Eval (100%) and demo-check must not change. | O(N²) growth, long transactions | M |
| C11 | **Frontend data layer:** per-domain hooks plus a key factory; `nextStep()` as a pure function; add `startup_name` to `MatchOut` (additive) and stop parsing strings. | duplicated keys, logic in components | M |
| C12 | **Bundle:** lazy-load motion and use-gesture with sheets and dialogs. | about −25% first-load JS (target under 110 KB gzipped) | S |
| C13 | **Types:** `mypy` default to 0 errors (83), then `--strict` package by package in CI order (`matching`, `circuits`, `github` first). Optional TS `noUncheckedIndexedAccess` (40). | silent type bugs | M |
| C14 | **Security headers** on the API and the static site (CSP, HSTS, frame-ancestors, Referrer-Policy); require `GITHUB_TOKEN_KEY` in production. | S6, S7 | S |

### Not refactors, but needed before real users (these need your decisions)

1. **Real sign-in and profile creation** in the frontend (Clerk or Supabase: a new dependency and a provider choice).
2. **Email delivery** for claim codes (a provider: a new dependency).
3. **Dashboard scoping:** what an ecosystem is (a college? an incubator's cohort? a city?) and how members join one. This is a schema and product change.
4. **Verification:** how level 2 is actually verified (work email codes? LinkedIn OAuth?) and who grants level 3.
5. **Deployment and CI:** a backend Dockerfile, the Render or Railway config, and a CI workflow running lint, tests, demo-check and e2e. None exist yet. Phase 12 planned it.
6. **Observability:** error tracking (Sentry or similar, a new dependency) and a retention policy for the events table.

---

## 6. Summary in plain language

### Health scores

| Area | Score | In one sentence |
| --- | :---: | --- |
| **Backend** | **7 / 10** | Clean, small and carefully written, with good database constraints and locking in the tricky places, but it still assumes one server, one trusted admin and friendly users. |
| **Frontend** | **6.5 / 10** | A consistent design system, a typed API client and a lean first load, but it has no real sign-in, keeps an old UI layer alongside the new one, and puts decision logic inside screens. |
| **Tests** | **7 / 10** | 96% backend line coverage and Playwright for every demo story at two widths, but nothing tests two things happening at once, the scheduler is half-tested, and the frontend has no unit tests. |
| *Production readiness (not code quality)* | *4 / 10* | *The missing pieces are mechanics, not rewrites: sign-in, admin separation, rate limits, safe background jobs, deployment.* |

### The 10 most important problems

1. **There is no real sign-in.** The frontend can only log in as demo personas, and there is no "create your profile" screen. Real users can't get in.
2. **Every partner admin is a superuser.** A college admin can raise anyone's verification level, run circuit rounds for the whole platform and see every ecosystem's data.
3. **No rate limits.** Anyone signed in can run up the AI bill, hammer the expensive "refresh my matches", or keep guessing claim codes.
4. **Background jobs aren't safe on more than one server.** Run two copies of the API and every job runs twice; two circuit rounds can put the same person in two loops.
5. **Heavy calculations freeze the API.** The circuit solver (up to 10 seconds) and match scoring run on the same thread that answers requests.
6. **The startup list makes 554 database queries for 100 startups** (770 ms). Everything else is batched; this one isn't.
7. **Errors aren't uniform.** One endpoint returns a different error shape the app can't read, and unexpected errors return plain text with no request id to trace.
8. **Lists don't page properly.** Jobs are loaded 1,000 at a time and sliced in memory (wrong totals beyond that); applicants and applications have no limit.
9. **Business logic sits in routers and screens** (applicant ranking, the circuit consent rules, Home's "next step" tree). It works, but it's harder to test and reuse.
10. **Some features can't work in production yet:** claiming needs real email, "level 2" is just typing a LinkedIn URL, and the dashboard has no idea which partner owns which members.

### Estimated size reduction

Honestly **small, because the code isn't bloated**: about **−400 to −600 lines** from deleting
dead and redundant code (redundant endpoints, `bbox`, the old UI layer, unused exports,
duplicated helpers), roughly **3%** of the 17,300 hand-written lines. Moving logic out of routers and
screens will shrink those files but not the total. The more valuable "reduction" is in
**the browser**: about **−25% first-load JavaScript** from lazy-loading the animation libraries,
and in the **database**: −98% queries on the startup list.

### What I'd do this week

1. **Monday:** quick wins A1–A3 and A6–A7 (no API changes), plus your decisions on A4 and A5.
2. **Tuesday:** tests first: B1 (coverage, if you approve `pytest-cov`), B2 concurrency tests, B4 authorization tests.
3. **Wednesday:** C1 (separate platform admins) and C2 (scheduler lock, solver off the event loop).
4. **Thursday:** C3 (rate limits, no new dependency) and C4 (one error format).
5. **Friday:** C5 (the startup list N+1) and C6 (database timeouts and indexes), then before and after numbers for everything.

In parallel, the decisions only you can make: **which auth provider** (Clerk or Supabase),
**which email provider**, and **what a partner's "ecosystem" is**. Those three unblock real users.

---

### Appendix: how the numbers were produced

| Measurement | Command (temporary tools, nothing installed in the project) |
| --- | --- |
| Lines, function lengths | small Python script over `git ls-files` (non-blank lines; `ast` for functions) |
| Complexity | `uvx radon cc app -s -n C`, `ruff check --select C901,PLR0912,PLR0915` |
| Dead Python | `uvx vulture app --min-confidence 60` |
| Dead frontend | `npx knip@5` |
| Unused endpoints | OpenAPI operations vs `api.<METHOD>("<path>")` calls in `frontend/src` |
| Duplication | `npx jscpd@4 --min-lines 5 --min-tokens 50` |
| Bundle | `npm run build`, `npm run size`, `vite build --sourcemap` + `source-map-explorer@2` |
| Coverage | `uv run --with pytest-cov pytest --cov=app` with `concurrency = greenlet,thread` |
| Types | `uv run --with mypy mypy app [--strict]`, `tsc -b`, `tsc --noUncheckedIndexedAccess --exactOptionalPropertyTypes` |
| Query counts | SQLAlchemy `before_cursor_execute` counter against a locally seeded database (`EMBEDDING_PROVIDER=fake`) |
| Browser tests | `npx playwright test --reporter=list` |
