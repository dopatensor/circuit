# Circuit — Backlog

Everything agreed but not yet done, in priority order. Pull items into a LAUNCH.md
stage or a new phase; don't build from here directly. Tick items when merged.

Priority: P0 = before pilot · P1 = during pilot · P2 = after pilot · Later = only when data says so.

---

## P0 — before the pilot (also covered by LAUNCH.md)

- [ ] Consolidate specs: CLAUDE.md, PRODUCTION.md, DESIGN.md, LAUNCH.md agree; PROGRESS.md status table
- [ ] Supabase migration: Auth (Google + email OTP), RLS on all tables, Storage, Realtime
- [ ] Redis: match + dashboard cache with TTL and invalidation, rate limits, Postgres fallback
- [ ] graph/ interface: warm paths and circuit cycles via recursive SQL + networkx, tested on known graphs
- [ ] Access control: super_admin role, organisations + partner scoping, founder-only stats, counts < 5 hidden
- [ ] Landing page, sign-up → onboarding → first match in < 2 minutes
- [ ] Exchange circuits polished: loop card, live status, completion moment, mark done, ratings, notifications
- [ ] Account settings: profile, notifications, privacy, export, delete
- [ ] Email notifications (intros, applications, circuits) with preferences and unsubscribe
- [ ] Report and block; moderation queue; admin panel
- [ ] Legal pages + consent + under-18 defaults
- [ ] CI/CD, environments, monitoring, backups (see PRODUCTION.md)
- [ ] Fresh-eyes test with 5 real users

## P1 — during the pilot

### Design and networking (redesign R1–R7)
- [ ] DESIGN.md: palette, type scale, spacing, motion rules, circuit line motif, voice; banned anti-patterns
- [ ] Design system components + /design page (dev only)
- [ ] Navigation: mobile tab bar with centre action; desktop three columns; Cmd/Ctrl+K search
- [ ] Home opportunities feed (matches, nearby jobs, circuits, intros, profile views, skills in demand). No likes, no posts
- [ ] Profiles: headline, verification badge, capability chips, proof of work first, profile strength meter
- [ ] Connections (request with note, accept/decline, mutuals) feeding warm paths
- [ ] Follow startups
- [ ] Notifications centre (grouped, read/unread)
- [ ] Global search: people, startups, jobs, skills
- [ ] Inbox (connected members only; students can't message strangers) via Supabase Realtime
- [ ] Animation pass: page transitions, staggered lists, bottom sheets, swipe on match cards (with buttons), circuit loop animation; reduced-motion respected
- [ ] PWA: manifest, icons, offline shell, update prompt, install prompt incl. iOS

### Students and proof of work
- [ ] Searchable student profiles (opt-in) so founders can find students
- [ ] Students can post offers (skills) and join circuits
- [ ] GitHub proof of work via OAuth: original repos, merged PRs, languages → capabilities; capped score weight; disconnect deletes data
- [ ] Non-code proof: portfolio, Behance/Dribbble, case studies
- [ ] "Project" job type for short paid gigs

### Data
- [ ] Production crawler: separate Cloud Run Job, PageFetcher interface (own fetcher + optional Firecrawl), robots.txt, LLM extraction, dedupe, geocode, confidence score
- [ ] Review queue for low-confidence records; "Unclaimed · from public sources" label
- [ ] Public "Remove my startup" form + takedown queue
- [ ] Pilot city: ~150 verified startups; freshness re-crawl every 2–4 weeks
- [ ] Startup claim outreach: get 30–50 to claim and post a real role

### Matching
- [ ] v1.x tuning from real acceptance data (weights, bridge share, thresholds)
- [ ] Grow eval set from 50 to a few hundred labelled pairs using real outcomes
- [ ] Gap map as a partner report export (PDF/CSV)

### Ops
- [ ] Load test staging (~1,000 concurrent users)
- [ ] Repo cleanup + CODE_AUDIT.md (measure, delete dead code, consistent patterns)
- [ ] Product analytics funnels (privacy-friendly)

## P2 — after the pilot

- [ ] Matching v2: learned weights (logistic regression) once a few hundred rated outcomes exist
- [ ] Mentor chains (altruistic givers start open chains)
- [ ] Peer circles (groups of 4–6 with complementary skills)
- [ ] Reputation score from rated help (PageRank over "helped" edges)
- [ ] Need decomposition (goal → sub-needs, each matched)
- [ ] Level 4 community vouching
- [ ] Regional language support
- [ ] Partner self-serve onboarding (create organisation, invite students)
- [ ] Investor tier (paid dealflow view; founders control visibility)
- [ ] Corporate innovation needs (companies post problems, matched to startups)
- [ ] Services marketplace and perks

## Later — only when measurements or data justify it

- [ ] Matching v3: learning-to-rank (LightGBM) after thousands of outcomes
- [ ] Bandit-learned bridge-match share per user
- [ ] Circuit scoring with predicted acceptance probabilities
- [ ] Portable signed badges (W3C Verifiable Credentials)
- [ ] Ecosystem reports (anonymised, sponsored)
- [ ] Neo4j behind the graph/ interface. Trigger: warm-path or circuit queries exceed ~500ms p95, or the circuit round takes > 10 minutes, or we need multi-hop network features SQL can't express cleanly
- [ ] Rust (PyO3) or Go for a specific hot path, only if profiling shows Python is the bottleneck
- [ ] Graph neural networks (only at tens of thousands of active users)

## Decided against (don't reopen without new evidence)

- Social feed with likes, follower counts and public posts
- Scraping LinkedIn or any site that forbids it; proxy rotation / anti-bot evasion
- Building our own password auth
- Success fees on fundraising (SEBI risk, bad incentives)
- Paying for placement in match rankings
- Microservices / Kubernetes at pilot scale
- Full backend rewrite (Django, Rust or Go) before the pilot
- Neo4j for the pilot (Postgres + networkx is enough; see trigger in Later)
- Restarting the codebase from scratch (continue and refactor instead; see CODE_AUDIT)
