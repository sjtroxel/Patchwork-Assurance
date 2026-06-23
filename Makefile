VENV := .venv

.PHONY: install dev test lint eval eval-judge

install:
	python -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"
	$(VENV)/bin/pre-commit install

dev:
	$(VENV)/bin/honcho -f Procfile.dev start

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

# Deterministic eval tier — free, offline, no API key.
eval:
	$(VENV)/bin/python -m eval.run

# Judged tier — SPENDS API TOKENS. Generates real memos (Sonnet) + judges them (Opus).
# Needs LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY in .env.
eval-judge:
	$(VENV)/bin/python -m eval.run --judge
