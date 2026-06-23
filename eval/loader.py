"""Load the gold evaluation set into typed objects.

Reuses the production `Situation` contract, so a malformed gold case fails loudly at load
time with the same validation the app uses (e.g. an invalid decision_domain or role raises).
"""

from pathlib import Path

import yaml
from pydantic import BaseModel

from patchwork_assurance.core.contracts import InScope, Situation

GOLD_PATH = Path(__file__).parent / "gold" / "cases.yaml"


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
