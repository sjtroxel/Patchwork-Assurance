VENV := .venv

.PHONY: install dev test lint eval eval-judge eval-dryrun eval-smoke sweep-knobs mcp pause resume

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
	@for arm in patchwork baseline-open baseline-primed grounded-single; do \
		case $$arm in \
			grounded-single) model=deepseek/deepseek-v4-pro ;; \
			*) model=openai/gpt-5.6-sol ;; \
		esac; \
		LLM_PROVIDER=stub $(VENV)/bin/python -m eval.run --stub-judged --arm $$arm \
			--baseline-model $$model --cases phase14 --cross-judge; \
	done

# Phase 14 paid smoke test — build-order step 7. SPENDS ~$0.45-0.50 (measured 2026-07-20; the build
# order's "~$0.10" predates the §1.2 amendment that made every arm read all twelve statutes). One case
# through each of the seven rows the §2.1 run list actually pays for, to catch structured-output
# refusals and auth/id errors before the full run. --no-groundedness: this exercises memo PRODUCTION,
# not judging. Each row is a separate process, so each hits confirm_spend separately: seven prompts.
# A failing row does NOT abort the rest — finding out WHICH models fail is the point of the step.
eval-smoke:
	@for row in \
		"patchwork:" \
		"grounded-single:openai/gpt-5.6-sol" \
		"grounded-single:anthropic/claude-fable-5" \
		"grounded-single:deepseek/deepseek-v4-pro" \
		"baseline-open:openai/gpt-5.6-sol" \
		"baseline-open:anthropic/claude-fable-5" \
		"baseline-open:google/gemini-3.5-flash" \
	; do \
		arm=$${row%%:*}; model=$${row#*:}; \
		echo "=== smoke: $$arm $$model ==="; \
		$(VENV)/bin/python -m eval.run --judge --no-groundedness --arm $$arm \
			$${model:+--baseline-model $$model} --cases phase14 --limit 1 \
			|| failed="$$failed\n  $$arm $$model"; \
	done; \
	if [ -n "$$failed" ]; then \
		printf "\nSMOKE FAILURES (report these, do not paper over them - phase-14 s12):$$failed\n"; \
		exit 1; \
	fi; \
	printf "\nAll smoke rows passed.\n"

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
