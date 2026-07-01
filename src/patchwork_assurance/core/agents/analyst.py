"""The per-law analyst agent (Phase 12 §4).

One agent per in-scope law, each a single constrained `complete_structured` call that reads ONLY its
own law's retrieved excerpts and returns that law's LawFinding. Grounded only in its own text, which
structurally prevents the cross-law contamination the per-law retrieval filter was added to fight (the
CA two-regime bug). Pure function of its inputs — no shared state — so it is threadpool-safe (§5).
"""

import time

from patchwork_assurance.core.agents.trace import AgentTrace
from patchwork_assurance.core.contracts import (
    LawFinding,
    Msg,
    RetrievedChunk,
    ScopeResult,
    Situation,
)
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.llm import LLMClient
from patchwork_assurance.core.prompts import ANALYST_SYSTEM, render_analyst_user


def analyze_law(
    law: LawMetadata,
    situation: Situation,
    scope: ScopeResult,
    chunks: list[RetrievedChunk],
    llm: LLMClient,
    model: str,
) -> tuple[LawFinding, AgentTrace]:
    """Extract ONE law's LawFinding from ONLY that law's excerpts. `model` is the resolved model string
    the orchestrator passes in (the Protocol has no model id) so per-agent attribution reaches the panel."""
    start = time.perf_counter()
    user = render_analyst_user(situation, scope, chunks, law)
    finding = llm.complete_structured(ANALYST_SYSTEM, [Msg(role="user", content=user)], LawFinding)

    # Identity + verdict + dates are deterministic, not the model's to set — stamp them from the scope
    # and metadata after the call (same discipline as the deterministic overlays). The agent owns the
    # analysis prose (why + obligations) only; it can't move an in/out verdict (the un-fishable gate).
    finding.law_id = scope.law_id
    finding.short_name = scope.short_name
    finding.in_scope = scope.in_scope
    finding.effective_dates = [ed.date.isoformat() for ed in law.effective_dates]

    ms = (time.perf_counter() - start) * 1000
    return finding, AgentTrace(law_id=scope.law_id, model=model, status="ok", ms=ms)
