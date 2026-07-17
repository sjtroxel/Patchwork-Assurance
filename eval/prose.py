"""Render a gold `Situation` into the prose a business owner would actually type.

Phase 14's measurement instrument (phase-14 IMPLEMENTATION §5). Patchwork consumes the structured
gold fields through a deterministic gate; a frontier model has to be handed prose, because prose is
what a person types into a chat box. Rendering is what makes those two comparable — hand Patchwork
tidy fields and the baselines a vague paragraph and you have compared two input formats, not two
systems.

Three rules, all load-bearing:

  Deterministic  A committed, diffable template. No LLM anywhere near this file.
  Lossless       Every field carrying a value appears. Nothing hinted, nothing withheld.
  Neutral        No legal vocabulary that leaks the answer. Never write "materially influence a
                 consequential decision" — that is Colorado's operative term, and writing it hands
                 the model the finding. Write what a business owner would say.

Review this as carefully as scoring code. Both failure directions are real: tipping the answer makes
the baselines look better than they are, stilted phrasing makes them look worse.

A blank field renders nothing, which faithfully mirrors a user who did not say. The absence is the
signal (it is what drives an "uncertain" verdict through the gate), so the renderer must not paper
over it with a guess.
"""

from patchwork_assurance.core.contracts import Situation

# Plain-language gloss for each corpus domain, in the words a business owner would use. Keyed by the
# ScopeDomain literal so a new domain in the corpus surfaces here as a KeyError rather than silently
# rendering nothing (the corpus seam is data; this map is the prose side of it).
_DOMAIN_PROSE: dict[str, str] = {
    "employment": "employees and job applicants",
    "housing": "housing applicants and tenants",
    "financial_lending": "people applying for credit or loans",
    "insurance": "people applying for insurance, and their pricing and claims",
    "health_care": "patients and the care they receive",
    "education": "students and applicants to our programs",
    "government_services": "people applying for public benefits or services",
    "online_safety_minors": "users of our product who are under 18",
    "ai_companion": "people who chat with our conversational AI product",
    "generative_ai_provenance": "the images, audio, video, and text our product generates",
    "frontier_models": "the large general-purpose AI models we train and release",
}

# Role, in plain words. The corpus taxonomy calls these "deployer" and "developer"; those are the
# operative terms in several of the statutes, so the prose describes the underlying fact instead of
# naming the category. Unambiguous, but not jargon — the model has to do the mapping work, which is
# exactly the work Patchwork's gate does deterministically.
_ROLE_PROSE: dict[str, str] = {
    "deployer": "We buy or license the AI systems we use. We do not build them ourselves.",
    "developer": "We build the AI systems ourselves and provide them to other businesses.",
}

_BOTH_ROLES_PROSE = (
    "We build AI systems and provide them to other businesses, and we also use them ourselves."
)


def _join_and(items: list[str]) -> str:
    """Oxford-comma join. '' / 'Texas' / 'Texas and Colorado' / 'Texas, Colorado, and Illinois'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _ai_use_sentence(situation: Situation, subjects: str) -> str:
    """The AI sentence, which carries both `ai_use` and `decision_domains`."""
    if situation.ai_use == "no":
        if subjects:
            return f"We make decisions about {subjects}. We do not use AI or any automated tool to help make them."
        return "We do not use AI or any automated tool to help make decisions about people."
    if situation.ai_use == "unsure":
        if subjects:
            return (
                f"We make decisions about {subjects}. We are not sure whether the software we use "
                "for this involves AI."
            )
        return "We are not sure whether the software we use to make decisions about people involves AI."
    if subjects:
        return f"We use AI to help make decisions about {subjects}."
    return "We use AI to help make decisions about people."


def render_situation_prose(situation: Situation) -> str:
    """Deterministic, lossless, neutral prose rendering of a gold situation.

    No LLM. This is part of the measurement instrument — review it as carefully as scoring code.
    """
    parts: list[str] = []

    if situation.home_state:
        parts.append(f"Our business is based in {situation.home_state}.")

    subjects = _join_and([_DOMAIN_PROSE[d] for d in situation.decision_domains])
    parts.append(_ai_use_sentence(situation, subjects))

    if situation.jurisdictions:
        where = _join_and(list(situation.jurisdictions))
        parts.append(f"The people these decisions affect are in {where}.")

    roles = set(situation.roles)
    if roles == {"deployer", "developer"}:
        parts.append(_BOTH_ROLES_PROSE)
    elif len(roles) == 1:
        parts.append(_ROLE_PROSE[roles.pop()])

    if situation.notes:
        parts.append(situation.notes)

    return " ".join(parts)
