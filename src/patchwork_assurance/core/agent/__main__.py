"""Entry point for the Phase 9 monitoring pipeline.

Run as: python -m patchwork_assurance.core.agent

Loads settings from the environment (LLM_PROVIDER, ANTHROPIC_API_KEY, etc.),
runs stages 1–4 of the pipeline, and prints a JSON summary to stdout. The
GitHub Actions workflow reads this output and opens a PR if staged_files is
non-empty.

Environment:
  LLM_PROVIDER       anthropic | openrouter | stub (default: stub)
  ANTHROPIC_API_KEY  required when LLM_PROVIDER=anthropic
  STAGING_PATH       where staged files are written (default: corpus/_staging)
  HASH_STORE_PATH    last-seen hash store (default: .agent_hashes.json)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from patchwork_assurance.config import settings
from patchwork_assurance.core.agent.pipeline import run_pipeline
from patchwork_assurance.core.agent.store import HashStore
from patchwork_assurance.core.llm import build_llm


def main() -> None:
    staging = Path(settings.staging_path)
    staging.mkdir(parents=True, exist_ok=True)

    hash_store = HashStore(settings.hash_store_path)
    llm_classify = build_llm(settings, settings.classify_model)
    llm_draft = build_llm(settings, settings.draft_model)

    result = run_pipeline(
        source_set=settings.source_set,
        llm_classify=llm_classify,
        llm_draft=llm_draft,
        staging_path=staging,
        hash_store=hash_store,
    )

    summary = {
        "total_changed": result.total_changed,
        "total_staged": result.total_staged,
        "staged_files": [str(f) for f in result.all_staged_files],
        "sources": [
            {
                "jurisdiction": r.source.jurisdiction,
                "changed": r.changed,
                "verdict": r.verdict,
                "staged": r.staged,
                "rejection_reason": r.rejection_reason,
            }
            for r in result.source_results
        ],
    }
    print(json.dumps(summary, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
