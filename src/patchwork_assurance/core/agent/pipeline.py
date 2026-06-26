"""Pipeline runner (Phase 9 Batch 4).

Orchestrates stages 1–4 of the five-stage monitoring pipeline:
  1. Poll     (cron, free)    poll_all()
  2. Detect   (free)          hash/diff inside poll_all
  3. Assess   (LLM-on-change) assess_change() — only when changed=True
  4. Draft    (LLM)           draft_seam1_pair() — only when verdict='relevant'
  5. Gate     (human)         caller / workflow opens a PR; human reviews + merges

run_pipeline handles stages 1–4 and returns a PipelineResult with staged file paths.
Stage 5 (PR opening) is the workflow's responsibility (.github/workflows/monitor.yml).

Hash-store commit discipline (see Batch 1 store.py):
  relevant + draft accepted → store.set + store.save  (fully processed, staged)
  not_relevant              → store.set + store.save  (assessed, not relevant, move on)
  uncertain                 → do NOT update hash       (retry next poll)
  poll / assess / draft err → do NOT update hash       (retry next poll)

Poll-only sources (SourceEntry.auto_draft=False — e.g. CO/CT image-scan PDFs the agent can't
auto-extract): detected for free, never spend an LLM, never auto-draft.
  first sight (no prior hash) → store.set + store.save, verdict="baseline"  (quiet baseline)
  real change vs baseline     → do NOT commit, verdict="manual_review"       (surfaced until acted)

Public API:
    SourceResult   - per-source outcome from one pipeline run
    PipelineResult - aggregated outcome (total_changed, total_staged, all_staged_files)
    run_pipeline   - orchestrates stages 1–4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.assess import assess_change
from patchwork_assurance.core.agent.draft import draft_seam1_pair
from patchwork_assurance.core.agent.poll import poll_all
from patchwork_assurance.core.agent.store import HashStore
from patchwork_assurance.core.llm import LLMClient

log = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """Per-source outcome from one pipeline run."""

    source: SourceEntry
    changed: bool
    verdict: str | None  # None if unchanged — no LLM call was made
    staged: bool
    staged_files: list[Path] = field(default_factory=list)
    rejection_reason: str | None = None


@dataclass
class PipelineResult:
    """Aggregated outcome from one complete pipeline run."""

    source_results: list[SourceResult]

    @property
    def total_changed(self) -> int:
        return sum(1 for r in self.source_results if r.changed)

    @property
    def total_staged(self) -> int:
        return sum(1 for r in self.source_results if r.staged)

    @property
    def all_staged_files(self) -> list[Path]:
        files: list[Path] = []
        for r in self.source_results:
            files.extend(r.staged_files)
        return files


def run_pipeline(
    source_set: list[SourceEntry],
    llm_classify: LLMClient,
    llm_draft: LLMClient,
    staging_path: Path | str,
    hash_store: HashStore,
    *,
    http_client: httpx.Client | None = None,
    allowed_source_domains: list[str] | None = None,
) -> PipelineResult:
    """Orchestrate stages 1–4 for every source in source_set.

    Stage 1–2: poll_all returns PollResults; changed=False sources short-circuit here
               with no LLM construction or call (the cost-control keystone).
    Stage 3:   assess_change (llm_classify) runs only for changed sources.
    Stage 4:   draft_seam1_pair (llm_draft) runs only for relevant assessments.

    Hash store is updated immediately after each source is fully processed (not at end-of-run)
    so a crash mid-run doesn't re-process already-staged sources on the next poll.
    """
    staging = Path(staging_path)
    poll_results = poll_all(source_set, hash_store, http_client=http_client)
    source_results: list[SourceResult] = []

    for pr in poll_results:
        # Stage 2 gate: no change → skip entirely, no LLM
        if not pr.changed:
            source_results.append(
                SourceResult(source=pr.source, changed=False, verdict=None, staged=False)
            )
            continue

        # Poll-only source (auto_draft=False): never spend an LLM, never auto-draft. Used for
        # sources the agent can't faithfully auto-ingest (image-scan PDFs like CO/CT). The HTML
        # status page is still monitored for free; a real change is surfaced for a human.
        if not pr.source.auto_draft:
            if hash_store.get(pr.source.url) is None:
                # First sight: record the baseline quietly so steady state is silent.
                hash_store.set(pr.source.url, pr.new_hash)
                hash_store.save()
                source_results.append(
                    SourceResult(source=pr.source, changed=True, verdict="baseline", staged=False)
                )
            else:
                # Real change vs the stored baseline: flag for manual review. Hash is NOT committed
                # so it keeps surfacing in the run summary until a human acts (no LLM spend either
                # way — the flag is free).
                source_results.append(
                    SourceResult(
                        source=pr.source,
                        changed=True,
                        verdict="manual_review",
                        staged=False,
                        rejection_reason=(
                            "Poll-only source changed; manual review required "
                            "(no auto-draft — official text is an unextractable PDF)."
                        ),
                    )
                )
            continue

        # Stage 3: assess
        try:
            ar = assess_change(
                pr,
                llm_classify,
                http_client=http_client,
                allowed_source_domains=allowed_source_domains,
            )
        except Exception as exc:
            log.error("assess_change failed for %s: %s", pr.source.url, exc)
            source_results.append(
                SourceResult(
                    source=pr.source,
                    changed=True,
                    verdict=None,
                    staged=False,
                    rejection_reason=f"assess error: {exc}",
                )
            )
            continue

        verdict = ar.verdict

        if verdict == "not_relevant":
            hash_store.set(pr.source.url, pr.new_hash)
            hash_store.save()
            source_results.append(
                SourceResult(source=pr.source, changed=True, verdict=verdict, staged=False)
            )
            continue

        if verdict == "uncertain":
            # Do not commit hash — human gate should see it on the next poll too
            source_results.append(
                SourceResult(source=pr.source, changed=True, verdict=verdict, staged=False)
            )
            continue

        # verdict == "relevant" — Stage 4: draft
        try:
            dr = draft_seam1_pair(ar, llm_draft, staging, allowed_source_domains)
        except Exception as exc:
            log.error("draft_seam1_pair failed for %s: %s", pr.source.url, exc)
            source_results.append(
                SourceResult(
                    source=pr.source,
                    changed=True,
                    verdict=verdict,
                    staged=False,
                    rejection_reason=f"draft error: {exc}",
                )
            )
            continue

        if dr.rejected:
            # A gate check failed — do not commit hash; human should investigate
            source_results.append(
                SourceResult(
                    source=pr.source,
                    changed=True,
                    verdict=verdict,
                    staged=False,
                    rejection_reason=dr.rejection_reason,
                )
            )
            continue

        # Draft accepted — commit hash and record staged files
        staged_files = [p for p in [dr.statute_md_path, dr.metadata_yaml_path] if p is not None]
        hash_store.set(pr.source.url, pr.new_hash)
        hash_store.save()
        source_results.append(
            SourceResult(
                source=pr.source,
                changed=True,
                verdict=verdict,
                staged=True,
                staged_files=staged_files,
            )
        )

    return PipelineResult(source_results=source_results)
