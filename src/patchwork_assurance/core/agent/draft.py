"""Draft stage (Phase 9 Batch 3).

Stage 4 of the five-stage monitoring pipeline: LLM-on-change, after a 'relevant' assess.
Only call this when AssessResult.verdict == 'relevant'.

The Sonnet LLM is given the official text and asked to:
  1. Call submit_statute_text(law_id, text) with the cleaned statute .md content.
  2. Call submit_metadata(metadata_yaml) with a YAML string conforming to LawMetadata.

Gate checks before staging (reject-not-stage):
  - official_text is None (no content to draft from).
  - Either tool not called (incomplete draft).
  - scan_for_injection flags in the statute text (security — reject, not flag).
  - Missing or empty source_url in submitted metadata YAML.
  - LawMetadata Pydantic validation failure.

Output (DraftResult):
  - All gates pass: files written to staging_path/<law_id>.md + .meta.yaml; rejected=False.
  - Any gate fails: no files written; rejected=True with rejection_reason.

Public API:
    DRAFT_TOOLS        - Anthropic-shaped tool definitions
    DraftResult        - dataclass returned by draft_seam1_pair
    draft_seam1_pair   - runs the Sonnet draft tool-use loop and gates the result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.assess import AssessResult
from patchwork_assurance.core.contracts import Msg
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.corpus.sanitize import scan_for_injection
from patchwork_assurance.core.llm import LLMClient

_DRAFT_SYSTEM = """\
You are a legal corpus agent for Patchwork Assurance, an AI-regulation compliance tool.
Your task: given the official text of a newly relevant AI-regulation statute, produce the
Seam 1 file pair that the Patchwork corpus loader expects.

Steps:
1. Call `submit_statute_text` with:
   - law_id: a short slug for this statute (e.g. "ca-cpra-admt", "nyc-ll144").
   - text: the cleaned official statute text in Markdown. Copy statutory language VERBATIM
     from the provided text — do NOT paraphrase, summarize, or author new content.
     Permitted cleaning: fix obvious OCR artifacts, standardize heading levels, remove
     irrelevant navigation/footer text. Every word of substance must come from the source.

2. Call `submit_metadata` with the complete YAML for the LawMetadata record. Required fields:
   law_id, jurisdiction, short_name, law_name, citation, status, signed_date,
   effective_dates, operative_standard, regulated_tech_term, regulated_roles, scope_domains,
   enforcement_authority, enforcement_mechanism, cure_period, private_right_of_action,
   key_obligations, source_url, retrieved_on.
   source_url MUST be the official source URL — the gate rejects drafts without it.

Integrity rule: you CLEAN, not author. Record source_url and retrieved_on accurately."""

DRAFT_TOOLS = [
    {
        "name": "submit_statute_text",
        "description": (
            "Submit the cleaned official statute text as the .md corpus file content. "
            "Copy statutory language verbatim — cleaning only (OCR fixes, heading levels). "
            "Call this before submit_metadata."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "law_id": {
                    "type": "string",
                    "description": "Short slug for this law (e.g. 'ca-cpra-admt', 'nyc-ll144').",
                },
                "text": {
                    "type": "string",
                    "description": "Cleaned official statute text in Markdown.",
                },
            },
            "required": ["law_id", "text"],
        },
    },
    {
        "name": "submit_metadata",
        "description": (
            "Submit the law metadata as a YAML string conforming to the LawMetadata schema. "
            "Include source_url (required) — the gate rejects drafts without it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metadata_yaml": {
                    "type": "string",
                    "description": "Complete YAML string for the LawMetadata record.",
                },
            },
            "required": ["metadata_yaml"],
        },
    },
]


@dataclass
class DraftResult:
    source: SourceEntry
    law_id: str | None
    rejected: bool
    rejection_reason: str | None
    injection_flags: list[str] = field(default_factory=list)
    statute_md_path: Path | None = None
    metadata_yaml_path: Path | None = None
    law_metadata: LawMetadata | None = None


def draft_seam1_pair(
    assess_result: AssessResult,
    llm: LLMClient,
    staging_path: Path | str,
) -> DraftResult:
    """Draft the Seam 1 file pair (.md + .meta.yaml) into staging from a relevant AssessResult.

    All gate failures return a DraftResult with rejected=True and no files written.

    Raises:
        ValueError: if assess_result.verdict != 'relevant' (caller bug; the pipeline prevents this).
    """
    if assess_result.verdict != "relevant":
        raise ValueError(
            f"draft_seam1_pair called with verdict={assess_result.verdict!r}. "
            "Only call the draft stage after a 'relevant' verdict from assess_change."
        )

    source = assess_result.source

    if assess_result.official_text is None:
        return DraftResult(
            source=source,
            law_id=None,
            rejected=True,
            rejection_reason="official_text is None — no content to draft from.",
        )

    state: dict = {"law_id": None, "statute_text": None, "metadata_yaml": None}

    def dispatch(name: str, args: dict) -> str:
        if name == "submit_statute_text":
            state["law_id"] = (args.get("law_id") or "").strip() or None
            state["statute_text"] = args.get("text", "")
            return "Statute text submitted."
        if name == "submit_metadata":
            state["metadata_yaml"] = args.get("metadata_yaml", "")
            return "Metadata submitted."
        return f"Unknown tool: {name}"

    hint_url = assess_result.official_url_fetched or source.official_url or source.url
    user_msg = (
        f"Official text for **{source.jurisdiction.upper()}** statute fetched from {hint_url}.\n\n"
        "Produce the Seam 1 corpus pair: call `submit_statute_text` with the cleaned statute "
        "text and `submit_metadata` with the full LawMetadata YAML.\n\n"
        f"--- OFFICIAL TEXT ---\n{assess_result.official_text}"
    )

    llm.run_tools(
        _DRAFT_SYSTEM,
        [Msg(role="user", content=user_msg)],
        DRAFT_TOOLS,
        dispatch,
    )

    law_id: str | None = state["law_id"]
    statute_text: str | None = state["statute_text"]
    metadata_yaml: str | None = state["metadata_yaml"]

    # Gate: both tools must have been called
    if statute_text is None or metadata_yaml is None:
        return DraftResult(
            source=source,
            law_id=law_id,
            rejected=True,
            rejection_reason=(
                "Draft loop ended without both submit_statute_text and submit_metadata being called."
            ),
        )

    # Gate: injection scan (security — reject before anything is staged)
    injection_flags = scan_for_injection(statute_text)
    if injection_flags:
        return DraftResult(
            source=source,
            law_id=law_id,
            rejected=True,
            rejection_reason=f"Injection pattern(s) detected in statute text: {injection_flags}",
            injection_flags=injection_flags,
        )

    # Gate: parse YAML
    try:
        meta_dict = yaml.safe_load(metadata_yaml)
    except yaml.YAMLError as exc:
        return DraftResult(
            source=source,
            law_id=law_id,
            rejected=True,
            rejection_reason=f"Metadata YAML parse error: {exc}",
        )

    if not isinstance(meta_dict, dict):
        return DraftResult(
            source=source,
            law_id=law_id,
            rejected=True,
            rejection_reason="Metadata YAML did not parse to a mapping.",
        )

    # Gate: source_url must be present and non-empty
    if not str(meta_dict.get("source_url") or "").strip():
        return DraftResult(
            source=source,
            law_id=law_id,
            rejected=True,
            rejection_reason="Metadata missing or empty source_url — draft rejected at gate.",
        )

    # Gate: LawMetadata Pydantic validation
    try:
        law_metadata = LawMetadata(**meta_dict)
    except (ValidationError, TypeError) as exc:
        return DraftResult(
            source=source,
            law_id=law_id,
            rejected=True,
            rejection_reason=f"LawMetadata validation failed: {exc}",
        )

    # All gates passed — write to staging
    staging = Path(staging_path)
    staging.mkdir(parents=True, exist_ok=True)
    final_law_id = law_metadata.law_id
    md_path = staging / f"{final_law_id}.md"
    yaml_path = staging / f"{final_law_id}.meta.yaml"

    md_path.write_text(statute_text, encoding="utf-8")
    yaml_path.write_text(metadata_yaml, encoding="utf-8")

    return DraftResult(
        source=source,
        law_id=final_law_id,
        rejected=False,
        rejection_reason=None,
        injection_flags=[],
        statute_md_path=md_path,
        metadata_yaml_path=yaml_path,
        law_metadata=law_metadata,
    )
