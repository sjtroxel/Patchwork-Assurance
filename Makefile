VENV := .venv

.PHONY: install dev test lint eval eval-judge sweep-knobs mcp pause resume

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

mcp:  ## run the MCP server over stdio
	$(VENV)/bin/python -m patchwork_assurance.mcp.server

# Railway cost control — Patchwork's "off switch" (no native Railway pause). See docs/RAILWAY_COST.md.
# pause stops billing (removes deployments); resume is a COLD redeploy (~1-3 min). Needs 'railway link' once.
pause:  ## take Patchwork offline on Railway (stops the ~$18/mo billing)
	sh bin/patchwork-pause.sh

resume:  ## bring Patchwork back online (cold redeploy, ~1-3 min)
	sh bin/patchwork-resume.sh

# Phase 8 knob sweep — re-tune top_k / chunk size / embedding model (free, offline).
sweep-knobs:
	$(VENV)/bin/python -m eval.sweep_knobs
