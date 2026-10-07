# Common tasks. Run from the repo root, e.g. `make demo-check`.
.PHONY: help db reset-demo demo-check eval test e2e lighthouse api-client lint dev-api dev-web

help:
	@echo "make db          start Postgres (docker compose)"
	@echo "make reset-demo  wipe the database and load the demo seed"
	@echo "make demo-check  check the five demo stories (PASS/FAIL each)"
	@echo "make eval        how often the match scorer agrees with labelled pairs"
	@echo "make test        backend tests, frontend build + size budget, browser tests"
	@echo "make e2e         browser tests only (phone and laptop widths)"
	@echo "make lighthouse  Lighthouse scores (needs make dev-api and a preview on :4183)"
	@echo "make api-client  regenerate the frontend's typed API client"
	@echo "make lint        lint and format checks"
	@echo "make dev-api     run the API on :8000 (auto-reload)"
	@echo "make dev-web     run the web app on :5173"

db:
	docker compose up -d --wait

reset-demo:
	cd backend && uv run python -m app.cli reset-demo

demo-check:
	cd backend && uv run python -m app.demo_check

eval:
	cd backend && uv run python -m app.matching.evaluate

test:
	cd backend && uv run pytest
	cd frontend && npm run build && npm run size && npx playwright test

e2e:
	cd frontend && npx playwright test

lighthouse:
	cd frontend && npm run lighthouse -- http://localhost:4183/welcome

api-client:
	cd frontend && npm run gen:api

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

dev-api:
	cd backend && uv run python -m app --reload

dev-web:
	cd frontend && npm run dev
