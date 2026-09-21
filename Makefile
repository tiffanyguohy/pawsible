.DEFAULT_GOAL := help
UV := uv run

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

dev:  ## Install all dependencies including dev group
	uv sync

db-up:  ## Start local Postgres 16 + pgvector
	docker compose up -d db

db-down:  ## Stop local Postgres
	docker compose down

fmt:  ## Format
	$(UV) black . && $(UV) ruff check --fix .

lint:  ## Lint without fixing
	$(UV) ruff check . && $(UV) black --check .

type:  ## Type check (strict on schema, text, extraction)
	$(UV) mypy

test:  ## Run the full suite
	$(UV) pytest

test-unit:  ## Unit tests only (no database)
	$(UV) pytest tests/unit tests/arch

test-db:  ## Tests requiring a live Postgres
	DATABASE_URL="postgresql+psycopg://pawsible:pawsible@localhost:5433/pawsible" $(UV) pytest -m db

codebook:  ## Regenerate the generated block inside evals/CODEBOOK.md
	$(UV) python -m pawsible.schema.codebook --write

check: lint type test  ## Everything CI runs, minus the eval gate

migrate:  ## Apply migrations
	$(UV) alembic upgrade head

sync:  ## Sync the metro from Petfinder
	$(UV) python -m pawsible.cli sync

extract:  ## Run the extraction pipeline over stale listings
	$(UV) python -m pawsible.cli extract

eval:  ## Run the golden set and write evals/reports/<prompt_version>.json
	$(UV) python -m evals.runner

run:  ## Serve the app locally
	$(UV) uvicorn pawsible.web.app:app --reload

.PHONY: help dev db-up db-down fmt lint type test test-unit test-db codebook check migrate sync extract eval run
