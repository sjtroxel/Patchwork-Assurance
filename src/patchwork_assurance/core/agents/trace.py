"""What the observability panel and logs read off the multi-agent pipeline (Phase 12 §9).

Per-agent metrics are RETURNED from each agent call as these plain dataclasses, never read from the
`core.obs` module global — that global accumulates across calls and is racy under the analyst
threadpool, so it can't attribute tokens/cost to a specific agent. `model` is carried explicitly (the
LLMClient Protocol exposes no model id) so the panel can show which model produced each contribution.
"""

from dataclasses import dataclass

# AgentEvent.kind values emitted by the orchestrator's on_event hook (drives the SSE panel, step 8):
# "analyst_start" | "analyst_done" | "review_verdict" | "review_summary" | "done".
AgentEventKind = str


@dataclass
class AgentTrace:
    """One agent call's outcome, returned alongside its result. tokens/cost are best-effort (None when
    the provider/stub doesn't surface usage)."""

    law_id: str
    model: str
    status: str  # "ok" | "error"
    ms: float
    tokens: int | None = None
    cost_usd: float | None = None


@dataclass
class AgentEvent:
    """A progress event streamed to the UI as each pipeline step completes. `model` is required so the
    panel can label who produced each line (analyst model vs reviewer model)."""

    kind: AgentEventKind
    model: str
    law_id: str = ""
    detail: str = ""
    tokens: int | None = None
    cost_usd: float | None = None
    ms: float | None = None
