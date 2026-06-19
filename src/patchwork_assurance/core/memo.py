from patchwork_assurance.core.contracts import ComplianceMemo, Msg, ScopeResult, Situation
from patchwork_assurance.core.prompts import MEMO_SYSTEM, render_memo_user
from patchwork_assurance.core.retrieval import RetrievalFilters


def generate_memo(situation: Situation, scope: list[ScopeResult], retriever, llm) -> ComplianceMemo:
    chunks = []
    for s in scope:
        if s.in_scope in ("yes", "uncertain"):
            chunks += retriever.retrieve(
                query=_focus(situation),
                filters=RetrievalFilters(jurisdiction=s.jurisdiction),
                k=5,
            )
    user = render_memo_user(situation, scope, chunks)
    return llm.complete_structured(MEMO_SYSTEM, [Msg(role="user", content=user)], ComplianceMemo)


def _focus(situation: Situation) -> str:
    return (
        f"obligations for {'/'.join(situation.roles) or 'a business'} using AI in "
        f"{'/'.join(situation.decision_domains) or 'consequential'} decisions"
    )
