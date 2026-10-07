# Circuit

A startup ecosystem platform that matches people on what they **need** and what they
can **offer**, across sectors, with exchange circuits and a map of who is hiring nearby.
See [CLAUDE.md](CLAUDE.md) for the full MVP spec and build phases.

**Status:** Phase 0 (scaffold) — backend and frontend start, Postgres with PostGIS +
pgvector runs in Docker, request logging and health checks are in place.

## Layout

```
backend/    FastAPI app (Python 3.12, uv)
  app/        config, logging middleware, db, API routers
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

## Logs

The API writes one JSON line per request with `request_id`, `method`, `path`,
`status`, `duration_ms` and `user_id`. Query strings, headers and bodies are never
logged, so personal data and tokens stay out of logs. Every response carries an
`X-Request-ID` header matching its log line.

## Database

- `docker compose up -d --wait` starts Postgres on port 5432 (change `POSTGRES_PORT`
  in `.env` if something else uses it — and update the URLs to match).
- Two databases are created on first start: `circuit` (app) and `circuit_test` (tests),
  both with PostGIS and pgvector enabled.
- `docker compose down -v` deletes the data volume for a completely fresh start.
