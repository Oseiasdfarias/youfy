.PHONY: setup up down lint test migrate migrate-check ingest featurize split e2e dvc-push docs-build docs-serve

setup:
	uv sync --all-extras

up:
	docker compose up -d --wait

down:
	docker compose down

migrate:
	cd packages/catalog && uv run alembic upgrade head

migrate-check:
	cd packages/catalog && uv run alembic upgrade head && uv run alembic check

lint:
	uv run ruff check .

test:
	uv run pytest -v

ingest:
	uv run youfy pipeline ingest

featurize:
	uv run youfy pipeline featurize

split:
	uv run youfy pipeline split

e2e:
	uv run pytest pipelines/tests/test_pipeline_e2e.py -v

dvc-push:
	uv run dvc add data/features data/splits && uv run dvc push

docs-build:
	uv run mkdocs build --strict

docs-serve:
	uv run mkdocs serve

