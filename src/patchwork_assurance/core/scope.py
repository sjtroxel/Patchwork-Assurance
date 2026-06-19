from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from patchwork_assurance.core.contracts import ScopeResult, Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata

# A scope element's signal once compared to a law: the user gave info that lines up (MATCH), gave
# info that excludes this law (MISMATCH), or said nothing (BLANK). The 3-state distinction is what
# lets the screen tell "you didn't tell me" apart from "you told me, and it's a no".
GateState = Literal["match", "mismatch", "blank"]


@dataclass(frozen=True)
class ScopePolicy:
    """The strictness dial. One small, named object so 'too permissive / too strict' is a one-line
    change, not scattered logic. See the three presets below."""

    # A *necessary* element left BLANK by the user: stay cautious (uncertain) or clear them (no)?
    silence: Literal["uncertain", "no"] = "uncertain"
    # The user NAMED something that excludes this law (mismatch): a hard 'no', or hedge to
    # 'uncertain' in case our domain taxonomy is incomplete?
    mismatch: Literal["no", "uncertain"] = "no"


CAUTIOUS = ScopePolicy()  # default — middle of the road
LENIENT = ScopePolicy(silence="no")  # clears the user on blanks (the old, riskier behavior)
STRICT = ScopePolicy(mismatch="uncertain")  # almost never a flat 'no'; always defer to a lawyer


def load_law_metadata(corpus_path: Path) -> list[LawMetadata]:
    return [
        LawMetadata(**yaml.safe_load(f.read_text()))
        for f in sorted(corpus_path.glob("*.meta.yaml"))
    ]


def applicable_laws(
    situation: Situation, laws: list[LawMetadata], policy: ScopePolicy = CAUTIOUS
) -> list[ScopeResult]:
    """Match the situation against each law's metadata — generic over N statutes (no `if colorado`).
    Returns one ScopeResult per law. `uncertain` is honest, not a cop-out. The `policy` dial controls
    how silence and contradiction are treated (see ScopePolicy / the CAUTIOUS|LENIENT|STRICT presets)."""
    return [_screen_one(situation, law, policy) for law in laws]


def _gate(provided: list, law_values: list) -> GateState:
    """One scope element's 3-state signal: blank if the user said nothing, match if what they said
    overlaps the law's values, mismatch if they named something with no overlap."""
    if not provided:
        return "blank"
    return "match" if (set(provided) & set(law_values)) else "mismatch"


def _screen_one(situation: Situation, law: LawMetadata, policy: ScopePolicy) -> ScopeResult:
    # Affirmative exclusion: the user says AI isn't used in the relevant decisions. These laws only
    # bite AI-driven decisions, so this is a clean 'no' regardless of the other gates.
    if not situation.uses_ai_in_decisions:
        return _result(law, "no", "No AI is used to make or influence the relevant decisions.")

    # Jurisdiction is its own gate, but its values live on the law as a single string, not a list.
    jurisdiction = _gate(situation.jurisdictions, [law.jurisdiction])
    domain = _gate(situation.decision_domains, law.scope_domains)
    role = _gate(situation.roles, law.regulated_roles)
    gates = {"jurisdiction": jurisdiction, "domain": domain, "role": role}

    # Rule 1 — any MISMATCH fails a necessary element. Hard 'no' (or hedged, under STRICT).
    mismatched = [name for name, state in gates.items() if state == "mismatch"]
    if mismatched:
        verdict = policy.mismatch
        reason = (
            f"You provided {'/'.join(mismatched)} information that falls outside {law.short_name} "
            f"({law.jurisdiction}), so it does not appear to reach you."
        )
        if verdict == "uncertain":
            reason += " Treated as uncertain pending a lawyer's review."
        return _result(law, verdict, reason)

    # Rule 2 — all three confirmed → facially in scope.
    if all(state == "match" for state in gates.values()):
        return _result(
            law,
            "yes",
            (
                f"Operates in {law.jurisdiction}, acts as a regulated party, and uses AI in a regulated "
                f"decision domain — facially within {law.short_name}. (Facially = before any exemptions; "
                "size/threshold carve-outs are not yet modeled.)"
            ),
        )

    # Rule 3 — no contradictions, but at least one necessary element is BLANK → unconfirmed.
    blanks = [name for name, state in gates.items() if state == "blank"]
    verdict = policy.silence
    reason = (
        f"Operates in/uses AI relevant to {law.short_name} ({law.jurisdiction}), but you haven't "
        f"provided your {'/'.join(blanks)} — that's needed before scope can be confirmed."
    )
    if verdict == "no":
        reason = f"No confirmed {'/'.join(blanks)} nexus to {law.short_name} ({law.jurisdiction})."
    return _result(law, verdict, reason)


def _result(law: LawMetadata, verdict: str, reason: str) -> ScopeResult:
    return ScopeResult(
        law_id=law.law_id,
        short_name=law.short_name,
        jurisdiction=law.jurisdiction,
        in_scope=verdict,  # type: ignore[arg-type]
        reason=reason,
    )
