.DEFAULT_GOAL := help

.PHONY: help format lint typecheck test

help:
	@printf '%s\n' \
		'make format     Format Python code with Ruff' \
		'make lint       Check Python code with Ruff' \
		'make typecheck  Check Python types with ty' \
		'make test       Run tests with pytest'

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run ty check

test:
	uv run pytest
