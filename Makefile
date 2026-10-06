.DEFAULT_GOAL := help

.PHONY: help format format-check lint lint-check typecheck test

help:
	@printf '%s\n' \
		'make format        Format Python code with Ruff' \
		'make format-check  Check Python formatting without changing files' \
		'make lint          Fix auto-fixable lint issues with Ruff' \
		'make lint-check    Check Python code with Ruff without changing files' \
		'make typecheck     Check Python types with ty' \
		'make test          Run tests with pytest'

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check --fix .

lint-check:
	uv run ruff check .

typecheck:
	uv run ty check

test:
	uv run pytest
