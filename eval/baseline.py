"""Produce a baseline compliance memo from a raw frontier model (phase-14 IMPLEMENTATION §6).

The baselines are the comparison arm: what a strong general model returns when asked the same question
Patchwork answers, given no retrieval and no curated corpus. This module is the bridge that lets a
prose-emitting model feed the SAME schema-consuming harness Patchwork uses, so every arm is scored by
byte-identical downstream code (`--arm` on `eval/run.py`).

Two arms:
  open    primed_laws=None   The model names the applicable laws itself. It is told NOTHING about the
                             corpus: not which laws exist, not the law count, not the jurisdiction
                             count. The states arrive naturally, because a business describing itself
                             says where its people are. (§6, §7.2.)
  primed  primed_laws=[...]   The model is handed the exact law ids + short names to consider and asked
                             to rule each in or out. The steelman-plus: it does not even have to know
                             the laws exist.

Fairness is the whole point (§11). The prompts (`eval/prompts/baseline_*.txt`, committed verbatim and
frozen before the run) are written to make the baseline WIN: they warn the model about the exact
failure modes we measure — cite the in-force version, keep similar laws distinct, say so when nothing
applies. What the baselines deliberately do NOT get is Patchwork's retrieved statute text; handing them
the excerpts would make them a RAG system, not a raw model, and erase the comparison. That asymmetry is
the experiment, not a thumb on the scale, and it is disclosed in the write-up.

Requiring the schema is the steelman, not a handicap (§6): it forces a commitment to specific,
checkable citations, where a model free to waffle in prose is HARDER to catch fabricating.
"""

from pathlib import Path

from eval.prose import render_situation_prose
from patchwork_assurance.core.contracts import ComplianceMemo, Msg, Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.prompts import DISCLAIMER

_PROMPTS = Path(__file__).parent / "prompts"
# Frozen, committed prompts (§6): loaded once at import so a run always uses the version in the repo.
BASELINE_OPEN_SYSTEM = (_PROMPTS / "baseline_open.txt").read_text(encoding="utf-8").strip()
BASELINE_PRIMED_SYSTEM = (_PROMPTS / "baseline_primed.txt").read_text(encoding="utf-8").strip()


def _primed_law_block(laws: list[LawMetadata]) -> str:
    """The corpus scope handed to the primed arm: law ids + short names + jurisdiction, as DATA in the
    user message (not baked into the frozen prompt template). Generic over the corpus — a new law
    appears here automatically, the same seam discipline as everything else."""
    lines = ["", "## Laws to consider (rule each one in or out for this business):", ""]
    for law in laws:
        lines.append(f"- {law.law_id} — {law.short_name} ({law.jurisdiction})")
    return "\n".join(lines)


def produce_baseline_memo(
    situation: Situation, llm, *, primed_laws: list[LawMetadata] | None = None
) -> ComplianceMemo:
    """One baseline memo. primed_laws=None -> open arm; a law list -> primed arm.

    The model emits the ComplianceMemo schema directly (complete_structured) — no prose-then-extract
    second call, which would add cost, latency, and a confound (extraction errors would score as model
    errors). Unlike the Patchwork memo path, effective_dates is left free here: it is one of the places
    a raw model reveals a stale-currency date, and the currency screen reads it.
    """
    prose = render_situation_prose(situation)
    if primed_laws is None:
        system = BASELINE_OPEN_SYSTEM
        user = prose
    else:
        system = BASELINE_PRIMED_SYSTEM
        user = prose + "\n" + _primed_law_block(primed_laws)
    memo = llm.complete_structured(system, [Msg(role="user", content=user)], ComplianceMemo)
    # Chrome is invariant #4: the not-legal-advice disclaimer rides on every published surface, and
    # these baseline memos are published. Pin it to the canonical text deterministically — identical
    # across every arm, and never a field the model is scored on (score_currency excludes it too).
    memo.disclaimer = DISCLAIMER
    return memo
