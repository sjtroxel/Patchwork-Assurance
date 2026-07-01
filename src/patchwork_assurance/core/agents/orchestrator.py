"""Phase 12 orchestrator — the fan-out (§5).

Runs the per-law analysts across a threadpool: each reads ONLY its own law's chunk bucket, in
parallel. The LLMClient is synchronous (core/llm.py), so parallelism is a ThreadPoolExecutor over the
blocking `complete_structured` calls, never an async rewrite. Latency scales with the slowest single
law, not the sum of all of them.

The reviewer (§6) and the full `run_multi_agent_memo` assembly (§7) build on top of this in later
steps; this module currently owns the analyst fan-out primitive.
"""

import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from patchwork_assurance.config import settings
from patchwork_assurance.core.agents.analyst import analyze_law
from patchwork_assurance.core.agents.trace import AgentEvent, AgentTrace
from patchwork_assurance.core.contracts import LawFinding, RetrievedChunk, ScopeResult, Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata

OnEvent = Callable[[AgentEvent], None]


def run_analysts(
    situation: Situation,
    in_scope: list[ScopeResult],
    buckets: dict[str, list[RetrievedChunk]],
    laws_by_id: dict[str, LawMetadata],
    analyst_llm,
    analyst_model: str,
    on_event: OnEvent | None = None,
) -> tuple[list[LawFinding], list[AgentTrace]]:
    """Fan the analysts over the in-scope laws in parallel; return (findings, traces) in SCOPE order
    (deterministic), not completion order. `on_event` streams start/done events for the live panel."""
    results: dict[str, tuple[LawFinding, AgentTrace]] = {}
    workers = max(1, min(settings.analyst_max_workers, len(in_scope)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for s in in_scope:
            if on_event:
                on_event(
                    AgentEvent(
                        kind="analyst_start",
                        model=analyst_model,
                        law_id=s.law_id,
                        detail=s.short_name,
                    )
                )
            # copy_context() snapshots this thread's ContextVars (incl. the obs request_id) so the
            # worker runs under them — a ThreadPoolExecutor does NOT propagate context on its own
            # (only anyio's run_in_threadpool does, which is why the API path works). One FRESH copy
            # per submit: a Context object can't be entered by two threads at once.
            ctx = contextvars.copy_context()
            fut = pool.submit(
                ctx.run,
                analyze_law,
                laws_by_id[s.law_id],
                situation,
                s,
                buckets[s.law_id],
                analyst_llm,
                analyst_model,
            )
            futures[fut] = s
        for fut in as_completed(futures):
            finding, trace = fut.result()
            results[trace.law_id] = (finding, trace)
            if on_event:
                on_event(
                    AgentEvent(
                        kind="analyst_done",
                        model=trace.model,
                        law_id=trace.law_id,
                        ms=trace.ms,
                    )
                )
    findings = [results[s.law_id][0] for s in in_scope]
    traces = [results[s.law_id][1] for s in in_scope]
    return findings, traces
