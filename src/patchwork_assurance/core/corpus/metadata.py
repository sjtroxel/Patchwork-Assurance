from datetime import date
from typing import Literal

from pydantic import BaseModel

ScopeDomain = Literal[
    "education",
    "employment",
    "housing",
    "financial_lending",
    "insurance",
    "health_care",
    "government_services",
    "online_safety_minors",
    "ai_companion",
    "generative_ai_provenance",
    "frontier_models",
]
Status = Literal["enacted", "effective", "enjoined", "repealed"]
RegulatedRole = Literal["developer", "deployer"]


class EffectiveDate(BaseModel):
    date: date
    applies_to: str


class Obligation(BaseModel):
    section: str
    label: str


class LawMetadata(BaseModel):
    """Law-level metadata — the human-authored source of truth (SPEC §4).
    The loader flattens this into Chroma-safe chunk metadata (SPEC §6)."""

    law_id: str
    jurisdiction: str
    short_name: str
    law_name: str
    citation: str
    also_known_as: list[str] = []
    status: Status
    signed_date: date
    effective_dates: list[EffectiveDate]
    operative_standard: str
    regulated_tech_term: str
    regulated_roles: list[RegulatedRole]
    scope_domains: list[ScopeDomain]
    enforcement_authority: str
    enforcement_mechanism: str
    cure_period: str | None
    private_right_of_action: bool
    key_obligations: list[Obligation] = []
    source_url: str
    source_page: str | None = None
    retrieved_on: date
