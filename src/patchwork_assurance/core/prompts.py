from patchwork_assurance.core.contracts import RetrievedChunk, ScopeResult, Situation

DISCLAIMER = (
    "This is an educational analysis, not legal advice. The laws are new and unlitigated "
    "and subject to AG rulemaking. Consult a licensed attorney for a compliance decision."
)

MEMO_SYSTEM = (
    "You produce a grounded, educational statutory-compliance summary — NOT legal advice, "
    "NOT a prediction of litigation outcomes (these statutes are unlitigated, so cite statute "
    "SECTIONS, never case law). Ground every obligation ONLY in the provided statute excerpts "
    "and cite the section. If the provided text does not support a claim, omit it. Use hedged, "
    "educational language ('the statute requires', 'this appears to be in scope'); never say "
    "'you are compliant', 'you must', 'we certify/guarantee', or present unsettled interpretation "
    f"as settled. Always set the disclaimer field to exactly: {DISCLAIMER}"
)

CHAT_SYSTEM = (
    "You are an educational assistant for US state AI-regulation law. Answer ONLY from the "
    "provided statute excerpts and cite sections. Decline or hedge on out-of-scope or unlitigated "
    "questions. Never give legal advice or assert settled law on unsettled questions. " + DISCLAIMER
)


def render_memo_user(
    situation: Situation, scope: list[ScopeResult], chunks: list[RetrievedChunk]
) -> str:
    lines = ["## Situation\n"]
    lines.append(f"Jurisdictions: {', '.join(situation.jurisdictions) or '(not specified)'}")
    lines.append(
        f"AI decision domains: {', '.join(situation.decision_domains) or '(not specified)'}"
    )
    lines.append(f"Roles: {', '.join(situation.roles) or '(not specified)'}")
    lines.append(f"Uses AI in decisions: {situation.uses_ai_in_decisions}")
    if situation.notes:
        lines.append(f"Additional context: {situation.notes}")

    lines.append("\n## Scope Determination (deterministic — do not override)\n")
    for s in scope:
        lines.append(f"**{s.short_name}** ({s.jurisdiction}): in_scope={s.in_scope} — {s.reason}")

    lines.append(
        "\n## Statute Excerpts (ground all claims in these; cite the section pinpoint shown in "
        "brackets, e.g. 'Colorado § 6-1-1703')\n"
    )
    if chunks:
        for c in chunks:
            lines.append(
                f"[{c.pinpoint}] {c.section_heading}\n(full citation: {c.citation})\n{c.text}\n"
            )
    else:
        lines.append("(No excerpts retrieved — do not fabricate obligations.)")

    lines.append(
        "\nProduce the ComplianceMemo. Cite each obligation to the section pinpoint shown in "
        "brackets above (not the law-wide citation). Set disclaimer to the exact text specified in "
        "your instructions. Only report obligations supported by the provided excerpts."
    )
    return "\n".join(lines)


def render_grounding(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "## Statute Excerpts\n(none retrieved)"
    lines = [
        "## Statute Excerpts (answer ONLY from these; cite the section pinpoint shown in brackets, "
        "e.g. 'Colorado § 6-1-1703')\n"
    ]
    for c in chunks:
        lines.append(
            f"[{c.pinpoint}] {c.section_heading}\n(full citation: {c.citation})\n{c.text}\n"
        )
    return "\n".join(lines)
