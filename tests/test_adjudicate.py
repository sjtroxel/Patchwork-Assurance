"""Phase 14 step 9 — citation adjudication tool (offline, no API key, no embeddings).

Covers the round-trip that makes the tool trustworthy: it re-derives unresolved citations from a
persisted memo HTML using the SAME `locate_section` the eval scores with (so the adjudication can never
disagree with the number it adjudicates), separates unresolved from resolved, de-duplicates a repeated
bad citation into one worksheet line, and degrades gracefully on an empty/failed memo instead of
crashing.
"""

import html as _html
from pathlib import Path

from eval.adjudicate import (
    extract_memo,
    render_worksheet,
    unresolved_in_memo,
)

from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    LawFinding,
    MemoObligation,
)

# A tiny fake corpus: two real sections in one jurisdiction. Anything else is "unresolved".
SECTIONS = {"Colorado": {"6-1-1703", "6-1-1704"}}


def _memo(*obligations: tuple[str, str]) -> ComplianceMemo:
    return ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="CO",
                short_name="Colorado AI Act",
                in_scope="yes",
                why="test",
                obligations=[MemoObligation(text=t, citation=c) for t, c in obligations],
            )
        ],
        disclaimer="Educational tool, not legal advice.",
    )


def test_unresolved_separates_real_from_unresolvable():
    memo = _memo(
        ("real, in corpus", "C.R.S. § 6-1-1703"),
        ("real but out of corpus (Title VII)", "42 U.S.C. § 2000e-2(k)"),
        ("fabricated section", "C.R.S. § 6-1-9999"),
    )
    out = unresolved_in_memo(memo, SECTIONS, arm="baseline-open", model="m", case_id="c1")
    cites = {u.citation for u in out}
    assert cites == {"42 U.S.C. § 2000e-2(k)", "C.R.S. § 6-1-9999"}  # the in-corpus one is dropped
    assert all(u.arm == "baseline-open" and u.case_id == "c1" for u in out)
    # It carries the obligation text so a human can bucket without opening the memo.
    assert any(u.obligation == "fabricated section" for u in out)


def test_digit_boundary_is_respected():
    # 6-1-170 is NOT 6-1-1703 — locate_section uses a digit-boundary match; the tool inherits it.
    memo = _memo(("near-miss", "C.R.S. § 6-1-170"))
    out = unresolved_in_memo(memo, SECTIONS, arm="a", case_id="c")
    assert [u.citation for u in out] == ["C.R.S. § 6-1-170"]


def test_extract_memo_round_trips_through_the_details_block(tmp_path: Path):
    # Mirror _memo_to_html's embedding: html-escaped model_dump_json inside <details><pre>.
    memo = _memo(("x", "C.R.S. § 6-1-9999"))
    body = _html.escape(memo.model_dump_json(indent=2))
    page = tmp_path / "case.html"
    page.write_text(f"<h1>memo</h1><details><summary>raw</summary><pre>{body}</pre></details>")
    got = extract_memo(page)
    assert got is not None
    assert got.per_law[0].obligations[0].citation == "C.R.S. § 6-1-9999"


def test_extract_memo_returns_none_on_a_memo_with_no_block(tmp_path: Path):
    page = tmp_path / "empty.html"
    page.write_text("<h1>generation failed</h1><p>no structured memo</p>")
    assert extract_memo(page) is None


def _write_memo_dir(
    results: Path,
    stamp: str,
    arm: str,
    model: str,
    case_memos: dict[str, ComplianceMemo],
) -> None:
    """A memo dir plus its paired scorecard — the tool reads the model from the scorecard, so a dir
    without one is (correctly) ignored, exactly as a crashed run would be."""
    import json

    d = results / f"memos-{stamp}-{arm}"
    d.mkdir(parents=True)
    for case_id, memo in case_memos.items():
        body = _html.escape(memo.model_dump_json(indent=2))
        (d / f"{case_id}.html").write_text(f"<details><pre>{body}</pre></details>")
    (results / f"judged-{stamp}-{arm}.json").write_text(json.dumps({"memo_model": model}))


def test_collect_groups_by_arm_model_and_uses_the_newest_run(tmp_path: Path, monkeypatch):
    import eval.adjudicate as adj

    monkeypatch.setattr(adj, "corpus_section_texts", lambda _p: SECTIONS)
    results = tmp_path / "results"
    # Two models share the SAME arm label — the per-(arm,model) grouping must keep BOTH, not collapse
    # to the newest (the bug that silently dropped two of every three core-run models).
    _write_memo_dir(
        results, "20260721T205802Z", "baseline-open", "sol", {"c1": _memo(("s", "§ 5-5"))}
    )
    _write_memo_dir(
        results, "20260721T234300Z", "baseline-open", "fable", {"c1": _memo(("f", "§ 4-4"))}
    )
    # An OLDER run of (baseline-open, sol) carries a different bad cite that must NOT appear.
    _write_memo_dir(
        results, "20260101T000000Z", "baseline-open", "sol", {"c1": _memo(("old", "§ 1-1"))}
    )
    grouped, manifest, warnings = adj.collect(results)
    assert set(grouped) == {"baseline-open · sol", "baseline-open · fable"}
    assert {u.citation for u in grouped["baseline-open · sol"]} == {
        "§ 5-5"
    }  # newest sol, not § 1-1
    assert {u.citation for u in grouped["baseline-open · fable"]} == {"§ 4-4"}
    assert {label for label, _, _ in manifest} == set(grouped)
    assert warnings == []


def test_since_filter_scopes_to_a_run_session(tmp_path: Path, monkeypatch):
    import eval.adjudicate as adj

    monkeypatch.setattr(adj, "corpus_section_texts", lambda _p: SECTIONS)
    results = tmp_path / "results"
    _write_memo_dir(
        results, "20260719T000000Z", "grounded-single", "old", {"c1": _memo(("o", "§ 1"))}
    )
    _write_memo_dir(results, "20260721T202859Z", "patchwork", "sonnet", {"c1": _memo(("n", "§ 2"))})
    grouped, manifest, _ = adj.collect(results, since="20260721")
    assert set(grouped) == {"patchwork · sonnet"}  # the 7/19 run is filtered out


def test_dir_without_a_scorecard_is_ignored(tmp_path: Path, monkeypatch):
    import eval.adjudicate as adj

    monkeypatch.setattr(adj, "corpus_section_texts", lambda _p: SECTIONS)
    results = tmp_path / "results"
    d = results / "memos-20260721T234300Z-baseline-open"  # no paired scorecard
    d.mkdir(parents=True)
    (d / "c1.html").write_text(
        f"<details><pre>{_html.escape(_memo(('x', '§ 9-9')).model_dump_json())}</pre></details>"
    )
    # Also a hand-named junk dir that must never parse.
    (results / "memos-multi-25-20260702").mkdir()
    grouped, manifest, _ = adj.collect(results)
    assert grouped == {} and manifest == []


def test_worksheet_dedupes_a_repeated_citation_and_flags_skips(tmp_path: Path, monkeypatch):
    import json

    import eval.adjudicate as adj

    monkeypatch.setattr(adj, "corpus_section_texts", lambda _p: SECTIONS)
    results = tmp_path / "results"
    d = results / "memos-20260721T230350Z-baseline-open"
    d.mkdir(parents=True)
    (results / "judged-20260721T230350Z-baseline-open.json").write_text(
        json.dumps({"memo_model": "sol"})
    )
    # Same bad cite in two cases => one worksheet line (x2). Plus one failed memo => a warning.
    for case_id in ("c1", "c2"):
        body = _html.escape(_memo(("dup", "§ 9-9-9999")).model_dump_json(indent=2))
        (d / f"{case_id}.html").write_text(f"<details><pre>{body}</pre></details>")
    (d / "c3.html").write_text("<h1>failed</h1>")

    grouped, manifest, warnings = adj.collect(results)
    sheet = render_worksheet(grouped, manifest, warnings)
    assert "`§ 9-9-9999`  (x2 — c1, c2)" in sheet
    assert "**bucket:**" in sheet
    assert sheet.count("`§ 9-9-9999`") == 1  # de-duped to a single line
    assert any("c3" in w for w in warnings)
    assert "Skipped memos" in sheet
    assert "baseline-open · sol — 3 memos" in sheet  # manifest names the run + its memo count
