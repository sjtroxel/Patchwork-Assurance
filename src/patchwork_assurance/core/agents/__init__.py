"""Phase 12 multi-agent memo pipeline: per-law analysts -> grounding/hedge reviewer -> assembly.

Keystone-legal: imports only inward (core.contracts, core.retrieval, core.grounding, core.judge,
core.prompts, core.obs, core.llm). Nothing in api/ or ui/. `run_multi_agent_memo` (the orchestrator
entry) is re-exported here once it lands in step 5.
"""

from patchwork_assurance.core.agents.analyst import analyze_law
from patchwork_assurance.core.agents.orchestrator import run_analysts, run_multi_agent_memo
from patchwork_assurance.core.agents.reviewer import review_findings
from patchwork_assurance.core.agents.trace import AgentEvent, AgentTrace

__all__ = [
    "analyze_law",
    "run_analysts",
    "run_multi_agent_memo",
    "review_findings",
    "AgentEvent",
    "AgentTrace",
]
