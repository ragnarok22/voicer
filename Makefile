.DEFAULT_GOAL := help

.PHONY: help format format-check lint lint-check typecheck test coverage check

TEST_ARGS ?=

help:
	@printf '%s\n' \
		'make format        Format Python code with Ruff' \
		'make format-check  Check Python formatting without changing files' \
		'make lint          Fix auto-fixable lint issues with Ruff' \
		'make lint-check    Check Python code with Ruff without changing files' \
		'make typecheck     Check Python types with ty' \
		'make test          Run tests with pytest' \
		'make coverage      Run tests with branch coverage' \
		'make check         Run formatting, lint, types and coverage checks'

format:
	uv run --locked ruff format .

format-check:
	uv run --locked ruff format --check .

lint:
	uv run --locked ruff check --fix .

lint-check:
	uv run --locked ruff check .

typecheck:
	uv run --locked ty check

test:
	uv run --locked pytest $(TEST_ARGS)

coverage:
	uv run --locked pytest --cov=voicer --cov-branch --cov-report=term-missing --cov-report=xml $(TEST_ARGS)

check: format-check lint-check typecheck coverage
