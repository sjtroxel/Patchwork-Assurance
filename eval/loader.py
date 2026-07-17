"""Load the gold evaluation set into typed objects.

Reuses the production `Situation` contract, so a malformed gold case fails loudly at load
time with the same validation the app uses (e.g. an invalid decision_domain or role raises).
"""

from pathlib import Path

import yaml
from pydantic import BaseModel

from patchwork_assurance.core.contracts import InScope, Situation

GOLD_PATH = Path(__file__).parent / "gold" / "cases.yaml"
RETRIEVAL_GOLD_PATH = Path(__file__).parent / "gold" / "retrieval_cases.yaml"


class GoldExpect(BaseModel):
    scope: dict[str, InScope]  # law_id -> expected verdict ("yes" | "no" | "uncertain")
    grounding_sections: list[str] = []
    obligations: list[str] = []


class CurrencyMarkers(BaseModel):
    """Phrases whose presence is evidence an output describes a SUPERSEDED version of the law.

    Phase 14's currency probe (IMPLEMENTATION §8). Markers are data, not code: adding a probe means
    adding markers to a case, never a branch in a scorer — the same discipline as the corpus seam.

    A valid marker must clear a TWO-SIDED bar. It must be absent from:

      1. the CURRENT STATUTE TEXT in `corpus/`  — a phrase the law still uses fires on a correct
         memo. This is how "disparate impact" and "reasonable care" were caught as unusable TX
         markers: both appear in enacted TRAIGA, the first inside the very clause that states the
         correct answer (§ 552.056(c)).
      2. the CASE'S OWN GOLD ANSWER            — a phrase the correct answer uses cannot be evidence
         of a wrong one. This is how "impact assessment" was caught for Texas, whose gold obligation
         says the Act "imposes NO impact-assessment ... duty". A substring screen cannot read that
         negation, so the phrase is disqualified rather than adjudicated.

    Both sides are enforced by `tests/test_currency.py` against the real corpus and the real gold —
    not left to the author's care. A marker is a claim about primary text, so a corpus update must
    BREAK the test rather than quietly rot the metric.

    The bar costs recall on purpose: a stale answer that uses only disqualified vocabulary slips
    through. That error runs toward FALSE NEGATIVES, which under-claims against Patchwork's own
    thesis — the safe direction for a benchmark published about one's own product.

    A match is EVIDENCE, NOT PROOF. Every hit is hand-verified before it reaches the write-up
    (IMPLEMENTATION §8) — for BOTH probes, not just Texas. This number is too important to leave to
    a substring search.
    """

    stale: list[str] = []
    # An effective date belonging to the superseded version. Reported separately from `stale`
    # because "cites the repealed act" and "states the wrong date for the live act" are different
    # failures, and the Texas probe is entirely the second kind.
    stale_effective_date: str | None = None


class GoldCase(BaseModel):
    id: str
    rationale: str = ""
    situation: Situation
    expect: GoldExpect
    # Additive and optional: only the currency probes carry markers; the other 42 cases are
    # unaffected and `score_currency` returns None for them.
    currency_markers: CurrencyMarkers | None = None


def load_gold(path: Path = GOLD_PATH) -> list[GoldCase]:
    raw = yaml.safe_load(path.read_text())
    return [GoldCase(**case) for case in raw]


class RetrievalQueryCase(BaseModel):
    """An exact-term / citation retrieval case (Phase 8 §7): a free-text query whose answer is a known
    statute section. Drives the lexical/hybrid/routed rungs on the queries semantic retrieval misses."""

    id: str
    query: str
    jurisdiction: str | None = None
    grounding_sections: list[str] = []


def load_retrieval_gold(path: Path = RETRIEVAL_GOLD_PATH) -> list[RetrievalQueryCase]:
    raw = yaml.safe_load(path.read_text())
    return [RetrievalQueryCase(**case) for case in raw]
