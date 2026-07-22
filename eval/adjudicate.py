"""Phase 14 step 9 — citation adjudication (the J.D. edge as instrumentation).

`score_citation_exists` marks a citation invalid if it does not resolve against our 12-law corpus. That
conflates three very different things:

    - **Fabricated**  — a section that exists in no real statute (a model error, the real finding).
    - **Repealed / superseded** — a real section, no longer current (SB 24-205, TRAIGA 1.0). A currency
      failure, which feeds the headline.
    - **Real, current, out of corpus** — correct but outside our 12 laws (Title VII's
      42 U.S.C. § 2000e-2, the Colorado Anti-Discrimination Act C.R.S. § 24-34-402). **Not an error.**
      Excluded and disclosed.

Publishing a single "X% of citations didn't resolve" number counts being *right* about a law we don't
carry as a hallucination — a factual error a lawyer catches on the first spot-check, and a breach of the
grounding rule in `.claude/rules/legal-content.md`. The write-up must report the three-way split, never
one percentage (phase-14 IMPLEMENTATION §9). The split *is* the finding.

This tool does the mechanical half so the human does only the judgment half. It re-derives every
unresolved citation from the persisted memos (the source of truth on disk) and the *current* corpus
sections — the same `locate_section` the eval scores with — groups them by **(arm, model)** (the model
read from the paired scorecard, because three models share each arm label), de-duplicates, and emits a
worksheet with an empty `bucket:` field per unique citation for a human to fill in by reading statutory
text. It writes only the worksheet, spends nothing, and is fully offline and re-runnable: the
adjudication is reproducible from the artifacts, not a one-time hand pass whose provenance is lost.

    python -m eval.adjudicate --since 20260721         # the core run: newest run of each (arm, model)
    python -m eval.adjudicate --arm baseline-open      # one arm (all its models)
    python -m eval.adjudicate --since 20260721 --out worksheet.md   # write the worksheet to a file
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from patchwork_assurance.config import settings
from patchwork_assurance.core.contracts import ComplianceMemo
from patchwork_assurance.core.grounding import corpus_section_texts, locate_section

RESULTS_DIR = Path(__file__).parent / "results"

# The full memo is embedded as pretty JSON inside a <details><pre> block by run.py (_memo_to_html).
# This is the same JSON `score_citation_exists` reads live, so re-parsing it re-derives the identical
# citation set — no separate persistence to drift out of sync.
_PRE_RE = re.compile(r"<details.*?<pre>(.*?)</pre>", re.DOTALL)


@dataclass(frozen=True)
class Unresolved:
    """One citation that did not resolve to the governing corpus, with the context a human needs to
    bucket it: which arm/model produced it, which case it came from, and the obligation text it was
    attached to."""

    arm: str
    model: str
    case_id: str
    citation: str
    obligation: str
    law_short_name: str


@dataclass(frozen=True)
class Run:
    """One scored run on disk: a memo dir and the (arm, model) it belongs to. The model is NOT in the
    dir name — three models share `grounded-single` and three share `baseline-open` — so it is read
    from the paired scorecard. This is why adjudication groups by (arm, model), not by arm."""

    stamp: str
    arm: str
    model: str
    memo_dir: Path


def extract_memo(html_path: Path) -> ComplianceMemo | None:
    """Pull the embedded ComplianceMemo JSON back out of a persisted memo HTML. Returns None for a memo
    that carries no structured block (an empty/failed raw generation) rather than raising — a skipped
    memo is a fact to report, not a crash."""
    match = _PRE_RE.search(html_path.read_text(encoding="utf-8"))
    if match is None:
        return None
    try:
        return ComplianceMemo.model_validate_json(html.unescape(match.group(1)))
    except ValidationError:
        return None


def unresolved_in_memo(
    memo: ComplianceMemo,
    sections: dict[str, set[str]],
    *,
    arm: str,
    model: str = "",
    case_id: str,
) -> list[Unresolved]:
    """Every obligation citation in the memo that does NOT resolve to a section in `sections`. Mirrors
    `score_citation_exists` exactly (`locate_section(...) is None`), so the tool can never disagree with
    the scored number it is adjudicating."""
    out: list[Unresolved] = []
    for finding in memo.per_law:
        for ob in finding.obligations:
            if locate_section(ob.citation, sections) is None:
                out.append(
                    Unresolved(
                        arm,
                        model,
                        case_id,
                        ob.citation.strip(),
                        ob.text.strip(),
                        finding.short_name,
                    )
                )
    return out


# A memo dir is `memos-<stamp>-<arm>` where <stamp> is exactly `YYYYMMDDTHHMMSSZ`. The strict pattern
# rejects the pre-arm June dirs (`memos-<stamp>` with no arm) and hand-named junk (`memos-multi-...`).
_DIR_RE = re.compile(r"memos-(\d{8}T\d{6}Z)-(.+)")


def _scorecard_model(results_dir: Path, stamp: str, arm: str) -> str | None:
    """The `memo_model` recorded next to a memo dir, or None if there is no readable scorecard. A dir
    without one is a crashed/interrupted run whose model can't be attributed — excluded, not guessed."""
    sc = results_dir / f"judged-{stamp}-{arm}.json"
    if not sc.exists():
        return None
    try:
        return json.loads(sc.read_text(encoding="utf-8")).get("memo_model")
    except (json.JSONDecodeError, OSError):
        return None


def runs(results_dir: Path, arm: str | None = None, since: str | None = None) -> list[Run]:
    """The newest scored run per (arm, model). Grouping by (arm, model) — not arm — is the correction
    that makes a benchmark honest here: `grounded-single` and `baseline-open` each label three different
    models, distinguished only by the scorecard's `memo_model`, so a per-arm view silently drops two of
    every three. `since` filters on the stamp prefix so one run session isolates cleanly (the core run
    is `since="20260721"`; `"20260721T20"` also excludes that day's one-case smokes)."""
    latest: dict[tuple[str, str], Run] = {}
    for d in sorted(results_dir.glob("memos-*")):
        m = _DIR_RE.fullmatch(d.name)
        if not d.is_dir() or not m:
            continue
        stamp, dir_arm = m.group(1), m.group(2)
        if (arm and dir_arm != arm) or (since and not stamp.startswith(since)):
            continue
        model = _scorecard_model(results_dir, stamp, dir_arm)
        if model is None:
            continue
        key = (dir_arm, model)
        if key not in latest or stamp > latest[key].stamp:
            latest[key] = Run(stamp, dir_arm, model, d)
    return sorted(latest.values(), key=lambda r: (r.arm, r.model))


def collect(
    results_dir: Path, arm: str | None = None, since: str | None = None
) -> tuple[dict[str, list[Unresolved]], list[tuple[str, str, int]], list[str]]:
    """Group unresolved citations by `"<arm> · <model>"` across the newest run of each (arm, model).
    Returns (grouped, manifest, warnings): the manifest is (label, stamp, n_memos) for every run
    included, printed so the human sees exactly which artifacts were adjudicated — no silent scope."""
    sections = corpus_section_texts(Path(settings.corpus_path))
    grouped: dict[str, list[Unresolved]] = defaultdict(list)
    manifest: list[tuple[str, str, int]] = []
    warnings: list[str] = []
    for run in runs(results_dir, arm, since):
        label = f"{run.arm} · {run.model}"
        memos = sorted(run.memo_dir.glob("*.html"))
        for html_path in memos:
            case_id = html_path.stem
            memo = extract_memo(html_path)
            if memo is None:
                warnings.append(f"{label} [{run.stamp}] {case_id}: no structured memo block")
                continue
            grouped[label].extend(
                unresolved_in_memo(memo, sections, arm=run.arm, model=run.model, case_id=case_id)
            )
        manifest.append((label, run.stamp, len(memos)))
    return dict(grouped), manifest, warnings


_BUCKETS = "fabricated | repealed | out-of-corpus"


def render_worksheet(
    grouped: dict[str, list[Unresolved]],
    manifest: list[tuple[str, str, int]],
    warnings: list[str],
) -> str:
    """A markdown worksheet: per `<arm> · <model>`, each *unique* citation once, with the cases it
    appeared in, an example obligation, a running count, and an empty `bucket:` for the human. De-duping
    matters — a model that repeats one bad citation across cases should be one adjudication, not N. The
    manifest at the top names exactly which runs were adjudicated, so the scope is never hidden."""
    lines: list[str] = [
        "# Phase 14 step 9 — citation adjudication worksheet",
        "",
        f"Bucket each unresolved citation as one of: **{_BUCKETS}**.",
        "Only *fabricated* and *repealed* count against the model; *out-of-corpus* is excluded and",
        "disclosed (§9). Report the three-way split per (arm, model), never one percentage.",
        "",
        "## Runs adjudicated",
        "",
    ]
    for label, stamp, n in manifest:
        lines.append(f"- {label} — {n} memos ({stamp})")
    lines.append("")
    for label in sorted(grouped):
        items = grouped[label]
        by_cite: dict[str, list[Unresolved]] = defaultdict(list)
        for u in items:
            by_cite[u.citation].append(u)
        lines.append(f"## {label} — {len(items)} unresolved across {len(by_cite)} unique citations")
        lines.append("")
        for cite in sorted(by_cite):
            group = by_cite[cite]
            cases = ", ".join(sorted({u.case_id for u in group}))
            example = group[0].obligation
            if len(example) > 180:
                example = example[:177] + "..."
            lines.append(f"- `{cite}`  (x{len(group)} — {cases})")
            lines.append(f"  - example: {example}")
            lines.append("  - **bucket:** ")
            lines.append("")
    if warnings:
        lines.append("## Skipped memos (no structured block)")
        lines.append("")
        lines.extend(f"- {w}" for w in warnings)
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--arm", default=None, help="only this arm (e.g. baseline-open)")
    parser.add_argument(
        "--since",
        default=None,
        help="only runs whose stamp starts with this (e.g. 20260721 for the core run)",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write the worksheet here instead of stdout"
    )
    args = parser.parse_args(argv)

    grouped, manifest, warnings = collect(args.results_dir, args.arm, args.since)
    worksheet = render_worksheet(grouped, manifest, warnings)
    if args.out:
        args.out.write_text(worksheet, encoding="utf-8")
        total = sum(len(v) for v in grouped.values())
        print(f"wrote {args.out} — {total} unresolved across {len(manifest)} run(s)")
    else:
        print(worksheet)


if __name__ == "__main__":
    main()
