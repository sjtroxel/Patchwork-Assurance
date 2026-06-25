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


class GoldCase(BaseModel):
    id: str
    rationale: str = ""
    situation: Situation
    expect: GoldExpect


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
