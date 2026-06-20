from typing import Literal

from pydantic import BaseModel

from patchwork_assurance.core.corpus.metadata import RegulatedRole, ScopeDomain

InScope = Literal["yes", "no", "uncertain"]


# ---- retrieval ----
class RetrievedChunk(BaseModel):
    text: str
    citation: str  # the law-wide citation (e.g. "Colo. Rev. Stat. §§ 6-1-1701 to 6-1-1709")
    section_number: str
    section_heading: str
    jurisdiction: str
    law_id: str
    score: float

    @property
    def pinpoint(self) -> str:
        """Section-anchored citation for display/grounding, e.g. 'Colorado § 6-1-1703' or
        'Connecticut Sec. 4'. The law-wide `citation` is too coarse to pin an obligation to a
        section; this composes the section pinpoint generically over CO ('6-1-1703') and CT
        ('Sec. 4') numbering. Falls back to the law-wide citation if no section is attached."""
        sec = self.section_number.strip()
        if not sec:
            return self.citation
        # CT already carries 'Sec. N'; CO sections are bare numbers, so prefix '§'.
        label = sec if sec.lower().startswith("sec") else f"§ {sec}"
        return f"{self.jurisdiction} {label}"


# ---- scope input ----
class Situation(BaseModel):
    """User-described facts. Drives the deterministic scope screen.

    `jurisdictions` means states the business has a *nexus* to (employees, applicants,
    customers/consumers, or residents it decides about) — not where it is headquartered (Phase 4.6).
    """

    # context/personalization; auto-counts as nexus if it is a regulating state
    home_state: str = ""
    jurisdictions: list[str] = []
    decision_domains: list[ScopeDomain] = []
    roles: list[RegulatedRole] = []
    # "no" excludes (clean affirmative exclusion); "unsure" is cautious — not excluded, surfaced in the memo
    ai_use: Literal["yes", "no", "unsure"] = "yes"
    notes: str = ""


# ---- scope output (deterministic) ----
class ScopeResult(BaseModel):
    law_id: str
    short_name: str
    jurisdiction: str
    in_scope: InScope
    reason: str


# ---- corpus-derived form vocabulary (GET /meta) ----
class CorpusVocab(BaseModel):
    """The form's controlled vocabulary, aggregated from the loaded corpus so the UI populates itself.
    Adding a law (a file pair, zero code) extends these automatically (Phase 4.6, invariant 2)."""

    jurisdictions: list[str]
    decision_domains: list[str]
    roles: list[str]


# ---- memo output ----
class MemoObligation(BaseModel):
    text: str
    citation: str


class LawFinding(BaseModel):
    law_id: str
    short_name: str
    in_scope: InScope
    why: str
    obligations: list[MemoObligation] = []
    effective_dates: list[str] = []


class DraftNotice(BaseModel):
    kind: str
    jurisdiction: str
    text: str


class DeadlineItem(BaseModel):
    date: str
    what: str
    law: str


class ComplianceMemo(BaseModel):
    per_law: list[LawFinding]
    draft_notices: list[DraftNotice] = []
    deadline_checklist: list[DeadlineItem] = []
    next_steps: list[str] = []  # condensed, hedged "what to do next" orientation (Phase 4.6)
    disclaimer: str


# ---- chat ----
class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatTurn(BaseModel):
    reply: str
    citations: list[str] = []
