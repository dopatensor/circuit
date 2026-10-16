# Circuit — Production reference

The single source of truth for how Circuit runs in production. If this file and
CLAUDE.md disagree on infrastructure, this file wins. Work through LAUNCH.md to get
here; use BACKLOG.md for everything after launch.

---

## 1. Architecture at a glance

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript + Vite PWA on Vercel | App at `<domain>`, previews per PR |
| API | FastAPI (Python 3.12) on Cloud Run, asia-south1 | Stateless, autoscaling, min instances in prod |
| Background jobs | Cloud Run Jobs + Cloud Scheduler | Matching, circuit rounds, crawler, cleanup |
| Database | Supabase Postgres + PostGIS + pgvector | Source of truth. Connect via pooler |
| Auth | Supabase Auth | Google sign-in + email OTP. JWT verified in FastAPI via JWKS |
| Files | Supabase Storage | `avatars` (public), `crawl-raw` (private) |
| Realtime | Supabase Realtime | Inbox, notifications, circuit status. RLS-scoped |
| Cache + rate limits | Redis (Upstash or Memorystore) | Disposable; Postgres fallback |
| Graph | Recursive SQL + networkx (graph/ interface) | Neo4j only if a BACKLOG.md trigger is hit |
| Timers | pg_cron | Expiring intros and circuit proposals |
| Secrets | Google Secret Manager | Never in repo, never in frontend |
| Images | Artifact Registry | Built by CI |
| CI/CD | GitHub Actions + Workload Identity Federation | No long-lived GCP keys |
| Errors | Sentry (frontend + backend) | PII scrubbed, releases + source maps |
| Logs | Cloud Logging (structlog JSON) | Request IDs end to end |
| Uptime | Better Stack or UptimeRobot | Alerts reach a phone |
| Email | Resend or Postmark | SPF, DKIM, DMARC on our domain |
| LLM | Anthropic API, claude-haiku-4-5-20251001 | Onboarding extraction, crawler. Monthly cap |

Request path: browser → Vercel (static) → `api.<domain>` (Cloud Run) → Redis cache →
Postgres (Supabase). Heavy work never runs inside a user request.

---

## 2. Environments

Four environments. `ENV` is one of `dev`, `demo`, `staging`, `production`.

| | dev | demo | staging | production |
|---|---|---|---|---|
| Purpose | Building and debugging | Investor, partner and outreach demos | Testing releases before production | Real users |
| Where | Laptop (docker compose) | Cloud Run + Vercel (own services) | Cloud Run + Vercel (own services + PR previews) | Cloud Run + Vercel |
| Supabase | Local Postgres | Free project | Free project | Pro project (backups + PITR) |
| Redis | Local container | Free tier | Free/small tier | Paid tier |
| Data | Seed + demo stories | Seed + demo stories ONLY, reset nightly and on demand | Seed + test accounts (never real users' data) | Real users only |
| Login | DEMO_AUTH personas + Supabase | DEMO_AUTH personas (DEMO_PUBLIC=true) + Supabase | Supabase only (DEMO_AUTH off) | Supabase only; DEMO_AUTH impossible |
| Email | Logged to console | Disabled (shown in UI only) | Provider test sender, to team inboxes | Provider, real sender |
| Search engines | n/a | noindex | noindex | Indexed (public pages only) |
| Deploy | Manual | Manual, from a release tag | Auto on merge to main | Manual approval after staging passes |
| Banner | "Dev" | "Demo — sample data" | "Staging" | none |

Rules:
- Every environment has its own keys, database, buckets, Redis and OAuth redirect URLs.
  No environment ever reads another's data. Real user data exists only in production.
- A typed settings module validates all variables at startup; missing = refuse to start.
- The app refuses to start if DEMO_AUTH=true and ENV is staging or production.
- Demo runs the same code as production (a release tag), only with demo config and data,
  so demos always show real, shipped features.
- `.env.example` documents every variable, with a note per environment. `.env` is gitignored.

---

## 2a. Domains and URLs (one place to change)

Nothing in code hard-codes a domain. Every URL comes from these variables, set per
environment. Until our domain is bought, demo and staging use the platform default
URLs; afterwards they become `demo.<domain>` and `staging.<domain>`.

| Variable | Used for | Before domain (staging) | After domain (production) |
|---|---|---|---|
| `APP_URL` | Frontend origin, email links, OG/sitemap URLs | `https://<project>.vercel.app` | `https://<domain>` |
| `API_URL` | Frontend API base, CSP connect-src | `https://<service>-<hash>.a.run.app` | `https://api.<domain>` |
| `CORS_ALLOWED_ORIGINS` | Exact origins allowed by the API (comma-separated) | `APP_URL` + `http://localhost:5173` (dev only) | `APP_URL` only |
| `CORS_PREVIEW_REGEX` | Vercel preview URLs (staging only, empty in prod) | `^https://<project>-git-.*\.vercel\.app$` | empty |
| `EMAIL_FROM` | Sender address | Provider's test/sandbox sender | `Circuit <hello@<domain>>` |
| `SUPPORT_EMAIL` | Footer, legal pages | A team inbox | `support@<domain>` |
| `SUPABASE_URL` | Auth, storage, realtime | Staging project URL | Production project URL |

Frontend reads `VITE_API_URL`, `VITE_APP_URL`, `VITE_SUPABASE_URL`,
`VITE_SUPABASE_ANON_KEY` at build time (set in Vercel per environment).

Switching to the real domain (checklist, ~1 hour plus DNS wait):
1. [YOU] Vercel: add `<domain>`, set DNS records, wait for HTTPS.
2. [YOU] API: map `api.<domain>` to Cloud Run (domain mapping, or a load balancer if
   domain mapping isn't available in asia-south1), set DNS, wait for certificate.
3. Update the variables above in Vercel and Secret Manager / Cloud Run env.
4. Supabase Auth: set Site URL to `APP_URL`, add redirect URLs (`APP_URL/auth/callback`,
   staging URL, `http://localhost:5173/auth/callback`).
5. Google OAuth client: add `APP_URL` to authorised JavaScript origins (redirect URI stays
   the Supabase callback).
6. Email: verify the domain in the provider (SPF, DKIM, DMARC), then switch `EMAIL_FROM`.
7. Redeploy frontend and API; run `make smoke URL=<APP_URL>` (sign-in, CORS preflight,
   one API read, one write, email send).

## 3. Security baseline

- Auth: Supabase JWT verified on every request (signature, expiry, audience, pinned algorithm).
- Authorization: role checks (`require_role`, `require_level`) plus partner scoping on every
  endpoint. Tests for IDOR on every endpoint that takes an ID.
- RLS enabled on every table; frontend reads only what RLS allows; all writes via FastAPI.
- Service role key: backend only, from Secret Manager.
- Rate limits (Redis): intros, applications, messages, connections, onboarding extraction.
- CORS: only our app domains per environment.
- Headers: CSP, HSTS, X-Content-Type-Options, Referrer-Policy, frame-ancestors.
- Input validation (Pydantic), request size limits, upload type/size checks.
- Logs and analytics never contain names, emails, phones or tokens (tested).
- Super-admin actions written to an audit log.
- Dependabot + secret scanning on; 2FA on every account (GitHub, GCP, Supabase, Vercel).

## 4. Roles and data access

| Role | Sees |
|---|---|
| student | Map, jobs, own matches/applications, "skills in demand" card. No dashboards |
| founder / mentor / investor | Own matches, intros, circuits; founders see own startup stats |
| partner_admin | Full dashboard scoped to their organisation only |
| super_admin | Everything; every action audit-logged; keep to 2–3 people |

Aggregates hide counts under 5. Heatmaps use neighbourhood-sized cells, never exact points.

## 5. Privacy and legal (India, DPDP Act)

- Privacy policy, terms, cookie notice live before real users; lawyer-reviewed.
- Consent stored with policy version + timestamp.
- Under-18 students: profile hidden by default, no direct messages from strangers.
- Data requests: export, correction, deletion (actually deletes or anonymises).
- Retention: events (permanent, pseudonymous), request logs (30 days), crawl raw pages
  (90 days), unverified accounts (purged after 30 days).
- Processors listed in the privacy policy: Supabase, Google Cloud, Vercel, Anthropic,
  email provider, Sentry, Redis host.
- Crawler: company data only, robots.txt respected, takedown form, claimed profiles never
  overwritten.

## 6. Data safety

- Supabase Pro: daily backups + point-in-time recovery on production.
- Restore drill: restore production backup to staging once before launch, then quarterly.
- Migrations: Alembic, reversible, expand-then-contract, tested on a staging copy.
- Redis is rebuildable from Postgres: `make rebuild-cache`.

## 7. Reliability

- `/health` (process up) and `/health/deps` (Postgres, Redis, Supabase Auth).
- Timeouts + retries with backoff on every external call; graceful fallbacks.
- Jobs are idempotent, have retry limits, and alert on failure.
- Cloud Run min instances ≥ 1 in production for the API.
- Supabase pooler; DB pool size × max instances stays under the connection limit.

## 8. Observability and alerts

| Signal | Tool | Alert when |
|---|---|---|
| Errors | Sentry | New error type, or error rate spike |
| Uptime | Uptime monitor | App, API or login down > 2 min |
| Latency | Cloud Monitoring | p95 API latency > 1s for 10 min |
| Jobs | Cloud Monitoring + logs | Any job fails twice in a row |
| Cost | GCP budgets, Supabase, Anthropic limits | 50%, 80%, 100% of monthly budget |

## 9. Performance targets

- API p95 < 300ms for reads served from cache; < 800ms otherwise.
- Initial JS < ~250KB gzipped; Lighthouse ≥ 90 (mobile) on landing and Home.
- Load test: ~1,000 concurrent users on key flows on staging before public launch.

## 10. Deploy and release

1. Pull request → CI: lint, strict type-check, unit, API, Playwright, axe. Merge blocked on failure.
2. Merge to main → build image → migrate staging → deploy staging → smoke tests.
3. Manual approval → migrate production → deploy production → smoke tests → tag release.
4. Rollback: previous Cloud Run revision + previous Vercel deployment (documented in RUNBOOK.md).

## 11. Cost guardrails (check current pricing)

- Fixed early costs: Supabase Pro, domain, Vercel (if Pro).
- Usage costs: Cloud Run, Redis, Anthropic API, email, Firecrawl (optional).
- Budget alerts on every paid service from day one. Apply for startup credits (Google for Startups).

## 12. Launch stages

1. Closed beta: 10–20 known students and founders. Needs LAUNCH.md Stages 1–3, 6–7.
2. Pilot college: one partner, ~150 verified local startups, 30–50 actively claimed. Needs all of LAUNCH.md.
3. Public launch: after pilot metrics are healthy and load test passes.

## 13. Pilot metrics (what we report to partners and investors)

- Sign-up → onboarding complete → first match → first action (apply, intro, circuit accept)
- Intro acceptance rate, local vs bridge
- Circuits proposed / activated / completed
- Startups claimed, roles posted, applications, shortlists
- Weekly active users, 4-week retention
