.PHONY: setup up down lint test ingest featurize split

setup:
	uv sync --all-extras

up:
	docker compose up -d --wait

down:
	docker compose down

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
