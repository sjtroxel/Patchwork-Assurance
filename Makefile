VENV := .venv

.PHONY: install dev test lint

install:
	python -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"
	$(VENV)/bin/pre-commit install

dev:
	$(VENV)/bin/honcho start

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
