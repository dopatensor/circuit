# Circuit — Launch plan

How to use this file:
- Do one stage per session (or two small, related stages, e.g. 1 + 2). Read only those stages plus CLAUDE.md and PRODUCTION.md.
- Each stage ends with: tests pass, commit, tick the boxes below, update PROGRESS.md, explain in plain language, stop.
- Items marked [YOU] need the human (accounts, money, approvals). Claude Code lists them, never fakes them.

Stack: FastAPI on Cloud Run (asia-south1) · Cloud Run Jobs + Scheduler · Supabase (Postgres + PostGIS + pgvector, Auth, Storage, Realtime) · Redis · React PWA on Vercel · GitHub Actions. Full details in PRODUCTION.md; later work in BACKLOG.md.

---

## Stage 0 — Snapshot (read-only, no code changes)
- [ ] Mark every item in Stages 1–10 as Done / Partial / Missing with evidence (file or test)
- [ ] List code that conflicts with CLAUDE.md / PRODUCTION.md (keep, refactor or delete)
- [ ] List all [YOU] items I need to do, in order
- [ ] Estimate effort per stage (S/M/L)

## Stage 1 — Environments and config
- [ ] Four environments per PRODUCTION.md §2: dev (local), demo, staging, production
- [ ] [YOU] Supabase projects: demo (free), staging (free), production (Pro plan)
- [ ] [YOU] GCP project(s), Vercel project, GitHub org secrets
- [ ] One typed settings module; app refuses to start if a required variable is missing
- [ ] No hard-coded domains anywhere: all URLs come from the PRODUCTION.md §2a variables (grep test in CI)
- [ ] Staging and demo fully working on default URLs (*.vercel.app + *.run.app) including sign-in and CORS
- [ ] Environment banner (Dev / Demo / Staging) and noindex outside production
- [ ] Demo: `make reset-demo ENV=demo` plus a nightly reset job; demo deploys from release tags
- [ ] `make smoke URL=...` script: sign-in page loads, CORS preflight passes, one read, one write, test email
- [ ] .env.example complete and documented; no secrets in repo or git history
- [ ] DEMO_AUTH and demo seed data only in dev and demo (tests prove staging and production refuse them)
- [ ] [YOU] Redis (Upstash or Memorystore) for demo, staging and production
- [ ] Redis: cache + rate limits behind cache/ interface, Postgres fallback when down (tested)
- [ ] Graph queries (warm paths, circuits) behind graph/ interface using recursive SQL + networkx

## Stage 2 — Auth and security
- [ ] Supabase Auth: Google sign-in + email OTP; FastAPI verifies JWT via JWKS
- [ ] members table linked to auth users; roles, verification, partner scope stay in our DB
- [ ] Row-level security on every table; service role key only in backend (Secret Manager)
- [ ] Authorization tests on every endpoint (IDOR, role, partner scoping)
- [ ] Rate limits on writes (intros, applications, messages, connections)
- [ ] Security headers (CSP, HSTS, nosniff, referrer policy, frame protection) on Vercel + API
- [ ] CORS limited to our domains per environment
- [ ] Input validation, request size limits, upload type/size checks
- [ ] No personal data in logs (test); super-admin actions audit-logged
- [ ] Dependabot + secret scanning enabled

## Stage 3 — Product basics (user-facing)
- [ ] Landing page (plain headline, students / founders / circuits sections, CTAs, footer)
- [ ] Sign-up → role → onboarding → location → consent (under-18 hidden by default)
- [ ] Landing to first useful match or job in under 2 minutes (measured)
- [ ] Every screen: loading, empty, error, offline states
- [ ] Account settings: edit profile, notifications, privacy, export data, delete account
- [ ] Circuits polished: loop card, live status via Realtime, completion moment, mark done, rating
- [ ] Notifications in-app (Realtime) and email for intros, applications, circuits
- [ ] [YOU] Email provider account (staging uses its test sender; domain DNS — SPF, DKIM, DMARC — once the domain exists)
- [ ] Report and block users
- [ ] Help/FAQ page, support contact, 404 and 500 pages

## Stage 4 — Admin and trust
- [ ] Super-admin panel: verify members, review crawled startups, takedowns, reports, key metrics, run circuit round
- [ ] Partner admin dashboard scoped to their organisation; counts under 5 hidden
- [ ] Moderation queue with actions (warn, hide, suspend) and audit log

## Stage 5 — Legal and privacy (India, DPDP Act)
- [ ] Privacy policy, terms, cookie notice pages (drafts)
- [ ] [YOU] Lawyer reviews final text
- [ ] Consent stored with version + timestamp
- [ ] Data request process (access, correction, deletion) and breach checklist in RUNBOOK.md
- [ ] Third-party processor list in privacy policy
- [ ] Data retention rules + scheduled cleanup job

## Stage 6 — Deploy pipeline
- [ ] [YOU] Buy domain, then follow PRODUCTION.md §2a "Switching to the real domain" (config only, no code changes); HTTPS + HSTS
- [ ] GitHub Actions on PR: lint, strict type-check, unit, API, Playwright; merge blocked on failure
- [ ] On merge: build, migrate, deploy to staging, smoke tests
- [ ] Production deploy = manual approval after staging passes; tagged releases
- [ ] Workload Identity Federation (no long-lived GCP keys)
- [ ] Migrations reversible and backwards-compatible; tested on a staging copy
- [ ] Rollback documented and tried once (Cloud Run revision + Vercel deployment)

## Stage 7 — Reliability and monitoring
- [ ] Health + readiness endpoints; Cloud Run min instances for production
- [ ] Timeouts, retries, fallbacks on every external call (LLM, GitHub, maps, email, crawler)
- [ ] Background jobs idempotent with retry limits and failure alerts
- [ ] Supabase pooler; pool sizes tuned for Cloud Run
- [ ] [YOU] Sentry account; Sentry on frontend + backend, source maps, PII scrubbed
- [ ] Uptime monitoring + alerts that reach a human
- [ ] Backups + point-in-time recovery on production; restore tested to staging
- [ ] Budget alerts on GCP, Supabase and LLM spend

## Stage 8 — Frontend quality and performance
- [ ] PWA: manifest, icons, offline shell, update prompt, install prompt (incl. iOS)
- [ ] SEO: titles, descriptions, OG images, sitemap, robots.txt; private pages not indexed
- [ ] Initial JS under ~250KB gzipped; Lighthouse 90+ on landing and Home (mobile)
- [ ] Accessibility WCAG AA; axe checks in CI
- [ ] Privacy-friendly analytics for key funnels (no personal data)
- [ ] Load test staging (~1,000 concurrent users on key flows); fix top bottlenecks

## Stage 9 — Repo cleanup (do LAST, after everything works)
- [ ] Delete dead code, unused files, components, endpoints, env vars and dependencies (measure first)
- [ ] Remove debug code, stray TODOs, commented-out code, leftover experiments
- [ ] One consistent pattern each for errors, data fetching, validation, logging
- [ ] Clear folder structure; README with setup in under 10 minutes on Mac and WSL
- [ ] Docs: CLAUDE.md, PRODUCTION.md, LAUNCH.md, BACKLOG.md, DESIGN.md, RUNBOOK.md, PROGRESS.md; delete outdated docs
- [ ] All tests green, `make check` green, before/after size numbers recorded

## Stage 10 — Go live
- [ ] RUNBOOK.md complete: deploy, rollback, restore, rotate secrets, outage, data request, takedown
- [ ] [YOU] Fresh-eyes test with 5 real users on staging; fix what confused them
- [ ] Production smoke test checklist run after deploy
- [ ] [YOU] Pilot college onboarded
