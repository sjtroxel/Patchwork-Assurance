VENV := .venv

.PHONY: install dev test lint eval eval-judge eval-dryrun sweep-knobs mcp pause resume

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

# Phase 14 offline dry run — the whole judged pipeline (arm dispatch, currency, groundedness,
# cross-judge, artifacts, provenance) on StubLLM at $0, over the built arms + the 13-case publish set.
# No API key, nothing contacted. Exercises the wiring before any paid run (build-order step 5).
eval-dryrun:
	@for arm in patchwork baseline-open baseline-primed; do \
		LLM_PROVIDER=stub $(VENV)/bin/python -m eval.run --stub-judged --arm $$arm \
			--baseline-model openai/gpt-5.6-sol --cases phase14 --cross-judge; \
	done

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
