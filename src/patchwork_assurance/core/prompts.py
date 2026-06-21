from patchwork_assurance.core.contracts import RetrievedChunk, ScopeResult, Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata

DISCLAIMER = (
    "This is an educational analysis, not legal advice. The laws are new and unlitigated "
    "and subject to AG rulemaking. Consult a licensed attorney for a compliance decision."
)

MEMO_SYSTEM = (
    "You produce a grounded, educational statutory-compliance summary — NOT legal advice, "
    "NOT a prediction of litigation outcomes (these statutes are unlitigated, so cite statute "
    "SECTIONS, never case law). For each law, LEAD the 'why' field with a plain verdict matching the "
    "deterministic scope ('Likely applies:', 'May apply:', or 'Does not appear to apply:') then a one- "
    "or two-sentence reason in business terms. Ground every obligation ONLY in the provided statute "
    "excerpts and cite the section; if the provided text does not support a claim, omit it. Use the "
    "exact operative term each excerpt uses (do not swap or harmonize the two laws' terms). The law "
    "facts block is authoritative background, not a citable source; cite statute sections. Do NOT "
    "state specific effective dates or deadlines in your prose — a separate, authoritative deadline "
    "list is added by the system. Use hedged, educational language ('the statute requires', 'this "
    "appears to be in scope'); never say 'you are compliant', 'you must', 'we certify/guarantee', or "
    "present unsettled interpretation as settled. Write in plain prose without em dashes. "
    f"Always set the disclaimer field to exactly: {DISCLAIMER}"
)

CHAT_SYSTEM = (
    "You are an educational assistant for US state AI-regulation law. Answer ONLY from the provided "
    "statute excerpts and the authoritative law facts, and cite sections. The law facts are "
    "human-verified: never contradict them about who a law binds or the exact operative term, but "
    "they are background, not a source: cite the statute sections, never cite 'law facts' and do not "
    "write the phrase 'law fact(s)' anywhere in your answer. Only discuss the laws present in the law "
    "facts above. If asked about any other state, jurisdiction, country, or law, say plainly that this "
    "tool only covers the laws it has and recommend a licensed attorney in that jurisdiction; do NOT "
    "name, cite, describe, or characterize any law not in the provided facts/excerpts, and do not claim "
    "what a jurisdiction has or has not enacted (your training may be stale). Many "
    "users are out-of-state businesses: a single employee, applicant, customer, or resident in a "
    "regulated state can create a nexus, so address reach (where their people are), not just where they "
    "are headquartered. You handle GENERAL questions about what these laws say. For situation-specific "
    "questions ('does this apply to me', 'what are my obligations'), give the general statutory picture "
    "but do NOT deliver a definitive personal applicability verdict; instead recommend the user run the "
    "Compliance Memo (it runs a deterministic scope screen on their specific facts) and consult a "
    "licensed attorney. Decline or hedge on out-of-scope or unlitigated questions. Never give legal "
    "advice or assert settled law on unsettled questions. Write in plain prose without em dashes. "
    + DISCLAIMER
)


def render_law_facts(laws: list[LawMetadata]) -> str:
    """Deterministic, human-verified facts from corpus metadata — authoritative guardrails the model
    must not contradict (who each law binds, the exact operative term, covered domains). The
    key-obligation labels encode WHO is bound (e.g. 'provider disclosure obligations to consumers'),
    exactly the kind of thing a small model otherwise guesses wrong."""
    if not laws:
        return ""
    lines = [
        "## Law facts (AUTHORITATIVE internal reference, human-verified): use these for which law "
        "covers what, who is bound, and the exact operative term, and never contradict them. This is "
        "background, not a citable source: cite the statute sections from the excerpts (e.g. "
        "'Connecticut Sec. 9'); never cite 'law facts'.\n"
    ]
    for law in laws:
        lines.append(f"### {law.short_name} ({law.jurisdiction})")
        lines.append(f"- Operative standard: {law.operative_standard}")
        lines.append(f"- Regulated parties: {', '.join(law.regulated_roles)}")
        lines.append(f"- Covered domains: {', '.join(law.scope_domains)}")
        lines.append(f"- Enforcement: {law.enforcement_authority}")
        if law.key_obligations:
            lines.append("- Key obligations (each label states who is bound):")
            for ob in law.key_obligations:
                lines.append(f"  - {ob.section}: {ob.label}")
        lines.append("")
    return "\n".join(lines)


def render_memo_user(
    situation: Situation,
    scope: list[ScopeResult],
    chunks: list[RetrievedChunk],
    laws: list[LawMetadata] | None = None,
) -> str:
    lines = ["## Situation\n"]
    if situation.home_state:
        lines.append(f"Home state (context): {situation.home_state}")
    lines.append(
        f"Nexus states (where they have people/customers): "
        f"{', '.join(situation.jurisdictions) or '(not specified)'}"
    )
    lines.append(
        f"AI decision domains: {', '.join(situation.decision_domains) or '(not specified)'}"
    )
    lines.append(f"Roles: {', '.join(situation.roles) or '(not specified)'}")
    lines.append(f"Uses AI in decisions: {situation.ai_use}")
    if situation.notes:
        lines.append(f"Additional context: {situation.notes}")

    facts = render_law_facts(laws or [])
    if facts:
        lines.append("\n" + facts)

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
        "\nProduce the ComplianceMemo. Lead each per-law 'why' with a plain verdict (Likely applies "
        "/ May apply / Does not appear to apply). Cite each obligation to the section pinpoint shown "
        "in brackets above (not the law-wide citation). Do not state effective dates in prose; leave "
        "next_steps empty (the system fills it). Set disclaimer to the exact text specified in your "
        "instructions. Only report obligations supported by the provided excerpts."
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
