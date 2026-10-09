# Circuit — progress

Snapshot for picking the work up in a new session. The spec is [CLAUDE.md](CLAUDE.md)
(including the "Spec additions" and "Testing" sections at the end). **The frontend
must also follow [DESIGN.md](DESIGN.md)**, the user's design and PWA brief for Phases
8–11. Setup details are in [README.md](README.md).

Branch: `claude/circuit-context-rebuild-vqqtw8` (Phase 10 onward). Phases 0–9 are
merged into `main` (pull requests #1–#7 in `dopatensor/circuit`). Phases 10 and 11 are
committed and pushed on this branch; no pull request has been opened for them yet. Each new session
gets its own branch name: start it from this branch (or `main`, once merged).

## Where we stopped (2026-10-09)

- **Frontend redesign in progress** (the user's brief: R1–R7, see DESIGN.md v3, approved
  2026-10-09). R1 was merged (pull request #10). R2 branch:
  `claude/focused-thompson-ntybkh`.
- **R2 is finished, committed and pushed**, waiting for the user's OK to start R3
  (connections, follow, notifications). R2 also built the user's new **F12 GitHub
  proof of work** spec (added to CLAUDE.md under "Spec additions (agreed 2026-10-09)").
- Phase 12 (demo readiness) comes after the redesign.
- Approved dependencies for the redesign: `motion`, `@tanstack/react-virtual` (not yet
  installed; needed for long lists), `@use-gesture/react`. Ask before anything else.
- The open question about GitHub API calls from the backend is answered: yes, through
  OAuth, a background import and a weekly refresh (F12).
- **To try a real GitHub connection:** create a GitHub OAuth App (callback
  `http://localhost:5173/me/github/callback`), put its id and secret in `.env`
  (`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`), restart the API. Never tried with a real
  app yet: tests use a fake GitHub.

## Redesign status

| Phase | State |
| --- | --- |
| R1 Design system, components, /design, navigation shell | ✅ done (merged, #10) |
| R2 Profiles, proof of work (F12 GitHub + other work), profile strength, privacy | ✅ done (waiting for OK) |
| R3 Connections, follow, notifications | ⏭️ next |
| R4 Home opportunities feed, global search | – |
| R5 Inbox (messages) | – |
| R6 Animation pass, circuit loop moment | – |
| R7 Playwright at 375/1280 for new UI, Lighthouse, DEMO.md | – |

## What R2 built (proof of work, F12)

**Backend**
- **Tables** (migration `614af2272cae`): `github_accounts` (one per student; GitHub's
  numeric account id is unique, login, profile/homepage URLs, the access token
  **encrypted** with Fernet, status `importing|ok|rate_limited|error`, `last_error`
  code, merged external PRs, active weeks, `fetched_at`, `next_fetch_at`),
  `github_repos` (original repos with the student's commits: languages, frameworks,
  commits theirs/total, README excerpt, homepage, `featured`, `hidden`; cascade-deleted
  with the account), `proof_items` (non-code proof), `members.show_college`.
- **`app/github/`**: `client.py` (httpx; rate limits → `RateLimited(reset_at)` from
  `x-ratelimit-*` or `retry-after`, 401 → `TokenRevoked`, 5xx/network → `GitHubError`;
  OAuth code exchange; grant revocation), `extract.py` (pure: original repos by
  **owner id**, commit counts, frameworks from topics/description/README,
  README excerpt, safe homepage URLs, external merged PRs, activity weeks, languages
  and frameworks → capabilities), `service.py` (signed `state`, connect, import,
  `refresh_due`, disconnect).
- **Flow:** `POST /api/proof/github/start` → GitHub (no `scope`, so read-only public
  data) → web app `/me/github/callback` → `POST /api/proof/github/finish {code, state}`:
  the state must name the signed-in student; the token's `/user` id is the ownership
  proof; one GitHub account per profile (409). The import runs as a background task
  right after, then the hourly scheduler job `refresh_github` imports accounts whose
  `next_fetch_at` is due (weekly; after a rate limit at GitHub's reset time + 1 min;
  after an error within the hour; never for revoked access or seeded rows). An import
  writes only after every call succeeded, so failures keep the last good data.
- **Other endpoints:** `GET /api/proof/me`, `PATCH /api/proof/github/repos/{id}`
  (feature up to 6; hide), `DELETE /api/proof/github` (deletes everything, revokes the
  grant), `POST/PATCH/DELETE /api/proof/items` (kind detected from the host: Behance,
  Dribbble, GitHub/GitLab links are plain "code" links; no link = case study with 40+
  characters). Students only (403 otherwise). Deleting a profile also disconnects.
- **Profiles:** `MemberPublic` now has `skills` and `proof` (GitHub: verified
  capabilities, featured non-hidden repos, PRs, activity; other items). College is
  hidden when `show_college` is false (you still see it in `MemberMe`).
- **Scoring** (`app/matching/scoring.py`, pure): `StudentProof`, `github_signal`
  (share of the job's capabilities GitHub verifies × strength from original repos,
  recent activity and external PRs), `portfolio_signal` (same idea for other work),
  `proof_bonus` = 0.03·max(github, portfolio) + 0.06·founder ratings + 0.05·completed
  circuits (`PROOF_SHARE` 0.14). `student_job_score` = 0.86·(old score) + bonus, so the
  order without proof is unchanged. Founder ratings = circuit legs the student gave
  to founders, rated; completed circuits = circuits with status `completed`.
  Applicants get `proof` and `rank_score` and are sorted by it.
- **Seed:** Ravi has a saved GitHub import (`ravi-kumar`, 4 repos, 2 featured, 2
  external PRs, URLs on `github.example`); new persona **Sneha Pillai** (story 3,
  design student) with a Behance link and a case study. She is added after the random
  parts of the generator (`LATE_STORY_MEMBERS`), so connections, intros and events are
  unchanged (dashboard still 52% vs 80%).
- `make demo-check` story 3 also checks Ravi's verified skills and Sneha's items.
- The eval's job threshold moved from 0.6 to 0.52 (= 0.6 × 0.86), the same boundary
  for students without proof; 100% agreement.

**Frontend**
- `src/screens/Proof.tsx` (`/me/proof`), `GitHubCallback.tsx` (`/me/github/callback`),
  `Profile.tsx` (`/people/:memberId`), `src/components/proof.tsx` (VerifiedChips,
  RepoSummary, ProofItemSummary, githubSummary). Me: "Proof of work" card and
  "Privacy". Home's student path: Profile → Proof → Apply → Interview. Profile strength
  adds "Show proof of work". Applicants show GitHub-verified chips and other proof.
- **Tests:** `e2e/proof.spec.ts` (feature/hide with Undo and the public profile,
  disconnect, the connect round trip with stubbed start/finish, a design student adds
  and removes work, hiding the college, Home's proof step), `story3.spec.ts` checks
  the verified chips on Ravi's application.

**Dependencies:** none new. `httpx` moved from dev to runtime dependencies (it was
already installed, and DESIGN.md v3 named it), and `cryptography` is now listed
explicitly (it was already installed through `pyjwt[crypto]`; used for Fernet).

## What R1 built

- **Tokens and fonts** (`src/index.css`): light (default) and dark themes, amber accent,
  teal signal, IBM Plex Sans 400/600 + Plex Mono 500 in `public/fonts/` (OFL). Older
  colour names (`blue`, `green`, `surface`) are aliases so screens restyled later still
  work. `src/theme.ts` + an inline script in `index.html`: Light / Dark / Same as device,
  saved per browser (Me → Appearance).
- **Design system** `src/components/ds/`: Icon (inline SVG) and Logo, Avatar (initials;
  one-word names use their capitals), Button/ButtonLink/IconButton, Card, Section, List,
  ListRow, Score, Badge (Verification with a pop, Bridge, Hiring), Chip, BottomSheet and
  Modal (`<dialog>`, motion springs, drag-to-dismiss on phones, stops blocking the page
  as soon as it starts closing), Tabs (arrow keys) and TabLinks, Toast with Undo,
  SkeletonBlock/SkeletonRows (shimmer), EmptyState, ErrorBlock, Stepper, Checklist.
  `components/ui.tsx` and `Sheet.tsx` keep the old names on top of these.
- **`/design`** (`screens/Design.tsx`): every block, in dev and `VITE_DESIGN_PAGE=1`
  builds (Playwright sets it).
- **Navigation** (`nav.ts`, `components/Shell.tsx`): Home · Discover · [action] ·
  Circuits · Inbox; Me on the avatar (phones) / in the sidebar. Right rail from 1280px
  (`RightRail.tsx`: profile strength + people worth meeting / jobs near you).
  Discover (`screens/Discover.tsx`) wraps Matches, Jobs, Startups, Map as tab routes;
  `/inbox` is the intros screen; `/intros` redirects.
- **Home** (`screens/Home.tsx`): next-step card per role from profile, applications,
  intros and circuits; top matches (minus the featured one) or intros to pass on.
- **Post a job** (`screens/PostJob.tsx`, `components/PostSheet.tsx`), founders only;
  needs a claimed startup (`StartupLink.is_claimer`, new in the API).
- **Startups** tab: `FindStartup.tsx` browses and searches all startups (founders still
  see "Claim").
- **Map**: theme-aware style (`mapStyle()`), sits in a bordered box under Discover's
  tabs; pins amber for hiring.
- **Icons** regenerated: the Circuit mark on off-white (`npm run icons`).
- **Tests:** `e2e/design.spec.ts` (gallery, sheet/modal focus and Escape, drag to
  dismiss on phones, toast Undo, tabs keyboard, theme follows device and sticks, Home
  next step for stories 1 and 3, founder posts a job, unclaimed founder told to claim).
  `helpers.goToTab` maps old tab names to the new navigation. Backend test for
  `is_claimer`.

Last verified (2026-10-09, R1):

- Backend: **226 passed, 1 skipped**; ruff clean. `make demo-check`: **5/5 PASS**.
- Browser tests: **72 passed, 2 skipped** across the full run plus the reruns after the
  last fixes (design and shell specs: 35 passed).
- `npm run size`: **140 KB** first-load JavaScript gzipped (budget 250 KB).
- Lighthouse mobile: `/welcome` 95/100/100/100, `/home` as Ravi 97/100/100/100, as Meera
  93/100/100/100.

## Phase 12 plan and older notes

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
| 9 Map view + jobs UI (F2, F3, F11) | ✅ done |
| 10 Network app (F1 UI, matches, intros, circuits) | ✅ done |
| 11 Dashboard UI (F8) | ✅ done (waiting for the user's OK) |
| **12 Demo readiness** | ⏭️ **next: not started** |

Last verified (2026-10-08, Phase 11 commit):

- Backend tests: **225 passed, 1 skipped** (no backend changes in Phase 11). `ruff` clean.
- Browser tests: **53 passed, 1 skipped** in two full runs (the second after the last changes).
- `npm run size`: 96.8 KB first-load JavaScript, gzipped. Service worker precache
  435 KB (MapLibre, its worker and the dashboard chunk are cached on first use instead).
- Lighthouse (mobile, slow 4G): `/dashboard` as Nandini 95–96 / 100 / 100 / 100. `/jobs`
  99. `/map` as Ravi 73–86 Performance on this machine, and the unchanged Phase 10 build
  scores the same here (it was 89–92 on the Phase 9 machine), so it's not a regression.
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

## What Phase 10 built (network app: F1 UI, F4 actions, F5, F6)

- **Backend:** `MatchOut.intro_member_id`: who a warm intro goes to (the person, or the
  founder who claimed a startup; `None` for jobs and unclaimed startups). Test:
  `test_matches_say_who_an_intro_would_go_to`.
- **Onboarding** (`src/screens/Onboarding.tsx`, route `/me/profile`, not for partner
  admins): a textarea (saved as the bio) and "Suggest chips" (`/api/onboarding/suggest`).
  `source: "llm"` replaces the chips with the suggestion and says how many were picked;
  `"manual"` says suggestions are off and keeps your current chips. Pickers
  (`src/components/Chips.tsx`): chosen and suggested chips first, "Show all 62" for the
  full list grouped by category, with the API's limits (10 needs, 10 offers, 15 skills,
  10 traits). Students get "Your skills" instead of needs and offers (their existing
  needs and offers are sent back unchanged, because confirm replaces everything).
  Need and offer texts are kept from the profile or the suggestion. "Save and see
  matches" → `/api/onboarding/confirm`, then `/api/matches/refresh` (level 2+), then
  Matches with "Saved". Entry points: Me ("Edit") and Matches (link, and the empty state).
- **Matches:** one action per card: "Ask for intro" (people, claimed startups; not for
  students), "View job", "View startup".
- **Intro sheet** (`src/components/IntroSheet.tsx`): the path as avatars (You → mutual →
  them), the API's `sentence`, then one of: the form (reason 10–500 characters, "Send
  request"), "You already asked" (`open_request_id`), or `blocked_reason` as-is. After
  sending: "Sent. <mutual> will see it first and pass it on."
- **Intros tab** (`src/screens/Intros.tsx`): capacity line, sections "To pass on", "For
  you", "You asked"; each card has a headline, status pill, path, reason, Bridge badge,
  and the buttons in `actions` (Pass it on, Accept, Decline, Withdraw; rating 1–5 via
  `src/components/Rating.tsx`).
- **Circuits tab** (`src/screens/Circuits.tsx`): loop card with an SVG circle (three
  avatars, clockwise arrowheads drawn halfway along each arc; SVG markers looked like
  they pointed the wrong way), the three "who helps whom" lines with each giver's answer,
  Accept / Decline with hours left, "You accepted. Waiting for the others.", and "Rate the
  help you got from X with Y" once active.
- **Dashboard tab** (`src/screens/Dashboard.tsx`): for now only the "Run round now" card
  (`/api/admin/circuits/run`), showing the round's numbers and the proposed loops.
  Phase 11 adds the rest. The old placeholder screens (`placeholders.tsx`, `Soon.tsx`)
  are gone.
- **Partner admins get an Intros tab** (Dashboard · Map · Intros · Me), because in story
  1 the mutual is Nandini (a partner admin) and she had no way to pass requests on.
  DESIGN.md updated.
- **Tests** (`e2e/network.spec.ts`, both widths): story 1 (Bridge card → intro path via
  Nandini → send → "You already asked"), story 4 (Rohan → Lakshmi passes on → Vikram
  accepts → Rohan rates 5), level-2 founder sees why she can't ask, story 2 (Nandini
  runs the round → Asha, Priya, Arjun accept → active → Arjun rates), a decline calls the
  circuit off, onboarding by hand, and onboarding with suggested chips (the suggest
  response is stubbed in the browser, since tests have no API key).
- `scripts/screenshots.mjs` has Phase 10 shots (onboarding, intro sheet, intros, run
  round, circuits).

## What Phase 11 built (partner dashboard UI, F8)

- **Dependency:** `recharts` 3.10.1 (on the spec's list). It lives only in the lazy
  Dashboard chunk (~106 KB gzipped).
- **`src/screens/Dashboard.tsx`**, top to bottom, each section with its own query,
  loading block (sized like the real section, `SIZE`), error state and retry:
  1. `Stats`: members, startups hiring, intros made (`/api/dashboard/stats`).
  2. `Gaps`: the 10 biggest gaps (`/api/dashboard/gaps?limit=100`, first 10 shown): one
     sentence ("Regulatory affairs: 35 needs, 2 offers."), a legend, a horizontal
     Recharts bar chart (needs `#2f8cff`, offers `#1a9e58`, 12px bars with 4px rounded
     ends, values at the bar ends, hairline grid, custom tooltip, labels wrap on phones)
     and "Show as a table". Empty state when nobody has needs yet.
  3. `GapMap`: capability `<select>` (every capability with needs, default the biggest
     gap), a status line ("Regulatory affairs: 17 areas (about 2 km across) with more
     needs than offers.") and the heat map. Old data stays (dimmed) while a new
     capability loads. The map loads only when it's within 200px of the screen
     (IntersectionObserver), which took the page's blocking time from 1.8 s to 0.2 s.
  4. `IntroSplit`: local vs bridge acceptance as two bars with %, "x of y accepted".
  5. `RunRound` (from Phase 10), now also refreshing the stats.
- **Chart colours** were checked with the dataviz palette validator on the card surface
  `#0c0d10`: both pass the lightness band, chroma, colour-blind separation (ΔE 25) and
  3:1 contrast. The neon green `#39ff8f` fails the lightness band for filled marks,
  hence the darker green.
- **`src/map/HeatMap.tsx`**: a MapLibre `heatmap` layer, weight = gap / max gap (cells
  with gap ≤ 0 left out), one blue hue (dark to light), radius growing with zoom so
  neighbouring 2 km cells merge into areas. The heat source and layer are part of the
  style from the start, because MapLibre's `load` event never fires when the street
  tiles can't be reached. Fits the cells; `data-heat-settled` for tests;
  `cooperativeGestures` so one finger scrolls the page on phones.
- **Fixed a hidden Phase 9 bug:** MapLibre 6 looks for its worker file next to its own
  code, but the build bundles that code into a hashed chunk, so the worker failed to
  load and production builds drew no street tiles (tests block tiles, so nothing
  noticed). `src/map/setup.ts` imports the worker with Vite's `?url` and calls
  `setWorkerUrl`. The story 5 test fails if a worker error is logged (checked by
  removing the fix).
- **Build:** `vite.config.ts` puts MapLibre in a named `maplibre` chunk (it's shared by
  the map and the dashboard now) and leaves `maplibre-*` and `Dashboard-*` out of the
  precache; they're cached on first use (`circuit-map` cache, CacheFirst).
- **Tests:** `e2e/dashboard.spec.ts` (both widths): story 5 (numbers, "35 needs, 2
  offers", table's first row, 17 areas, picker switches to clinical trials, 52% vs
  80%, no worker errors) and a failing section showing its error and retrying while the
  others still work. `network.spec.ts` now finds the round result by test id.
- `scripts/screenshots.mjs`: `partner-dashboard` and `partner-gap-map`.

## Phase 12: the plan (demo readiness)

From CLAUDE.md:
1. **DEMO.md**: a 5-minute demo script following the five stories, with the persona to
   switch to at each step and what to say. Story 3 includes applying and shortlisting
   (CLAUDE.md F11). Start with `make reset-demo && make demo-check`. Note that "Run
   round now" uses up story 2 until the next reset.
2. **reset-demo verified** from scratch (fresh database, migrations, seed).
3. **README** setup for Mac (Apple Silicon) and WSL2, checked end to end.
4. **Deployment config** for Railway or Render: one backend service, one static
   frontend, managed Postgres with PostGIS and pgvector. Ask the user which provider.
   `DEMO_PUBLIC=true` only for a fake-data demo deployment; `VITE_API_URL` for the static
   frontend; CORS origins; the embedding model download on first start.
5. All tests passing; a Playwright run that walks the whole DEMO.md path in order.
6. Consider before demos: a rate limit on `/api/onboarding/suggest` (see known issues).

## Remaining phases after 12

None: Phase 12 is the last phase in CLAUDE.md.

## Decisions and deviations from CLAUDE.md

All of these were explained at the end of their phase; the user confirmed by continuing.

**Dependencies** (approved by the user, or on the spec's list):
- **From the spec's list (Phase 11):** recharts 3.10.1.
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

**Phase 10:**
- `MatchOut.intro_member_id` added so startup matches can lead to an intro with the
  claiming founder.
- Partner admins have an Intros tab (they can be the mutual in an intro).
- The Dashboard tab holds "Run round now" until Phase 11 builds the full dashboard.
- Onboarding: a new suggestion replaces the chips (it describes the whole person);
  the user can still change any chip before saving.

**Phase 11:**
- The three dashboard numbers are members, startups hiring and intros made.
- The chart shows the 10 biggest gaps (needs minus offers), not the 10 most-needed
  capabilities; the full list is in the map's picker.
- Offers use a darker green (`#1a9e58`) than the brand neon, which fails the
  chart lightness check.

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
- **Unclaimed startups have no intro target**, so their match card says "View startup".
- **One unexplained browser-test failure** (2026-10-08): `pwa.spec.ts` "jobs, matches and
  applications stay readable offline" failed once at phone width in a full run, then
  passed in about 60 further runs (alone, with the other files, and in full runs). The
  error output was lost when the next run overwrote `test-results/`. If it fails again,
  keep `test-results/` and read the trace. It's probably the service-worker cache
  timing mentioned under "Offline e2e tests" below.
- **The real AI suggestion path is only tested with a stubbed response in the browser**
  (and a fake Messages API server on the backend). Try "Suggest chips" once with a real
  `ANTHROPIC_API_KEY`.
- **Intros tab has no paging and no "older" folding**: done and declined requests stay
  in the lists (at most 200 from the API).
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
- **On the Phase 11 machine the map scores 73–86 for Performance** (the same for the
  Phase 10 build there). Earlier note, from the Phase 9 machine:
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
git checkout claude/circuit-context-rebuild-vqqtw8   # or main once Phase 10 is merged
cp .env.example .env               # set DEMO_AUTH=true for the persona logins
make db                            # docker compose up -d --wait  (Postgres+PostGIS+pgvector)
cd backend && uv sync && cd ..     # Python 3.12 deps (uv downloads Python itself)
cd frontend && npm install && cd ..  # needs Node 22.12+
make reset-demo                    # migrate + seed + embed + compute matches (~15 s; model download first time)
```

### Every day

```bash
make dev-api        # API on http://localhost:8000  (docs: /docs)
make dev-web        # web app on http://localhost:5173
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

No Docker is needed. Then use the same `make` commands. Also:

- Run `cp .env.example .env` once in a new container. `.env` is gitignored, and without
  it `DEMO_AUTH` is off, so the persona switcher says "Demo sign-in is turned off".
- The network policy blocks `tiles.openfreemap.org`, so maps in screenshots show pins
  on black without streets. Real browsers load the tiles. To allow it, add the host
  under Network access → Allowed domains in the environment settings.
- Stop servers by port (`fuser -k 8000/tcp 4183/tcp`), not with `pkill -f "python -m
  app"`: that pattern also matches the shell running it.
- Playwright 1.56.1 matches the preinstalled Chromium; don't run `playwright install`.

If uv warns that
`UV_NATIVE_TLS` is deprecated, export `UV_SYSTEM_CERTS=1` and unset `UV_NATIVE_TLS`; the
warning is harmless.
