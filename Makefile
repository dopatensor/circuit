# Common tasks. Run from the repo root, e.g. `make demo-check`.
.PHONY: help db reset-demo demo-check eval test lint dev-api dev-web

help:
	@echo "make db          start Postgres (docker compose)"
	@echo "make reset-demo  wipe the database and load the demo seed"
	@echo "make demo-check  check the five demo stories (PASS/FAIL each)"
	@echo "make eval        how often the match scorer agrees with labelled pairs"
	@echo "make test        run backend tests and the frontend build"
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
	cd frontend && npm run build

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

dev-api:
	cd backend && uv run python -m app --reload

dev-web:
	cd frontend && npm run dev
