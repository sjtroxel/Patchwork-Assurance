"""Phase 9 Batch 4 — pipeline runner (offline; StubLLM + fake HTTP, no tokens, no network).

Key assertions:
- Unchanged sources produce no LLM call (the diff-gate keystone)
- changed + not_relevant → hash committed, verdict recorded, no staging
- changed + uncertain → hash NOT committed, no staging (retry next poll)
- changed + relevant + draft accepted → hash committed, two files staged
- changed + relevant + draft rejected → hash NOT committed, no files staged
- assess error → hash NOT committed, no files staged
- PipelineResult properties: total_changed, total_staged, all_staged_files
"""

import textwrap

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.pipeline import PipelineResult, SourceResult, run_pipeline
from patchwork_assurance.core.agent.poll import compute_hash
from patchwork_assurance.core.agent.store import HashStore
from patchwork_assurance.core.llm import StubLLM

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SOURCE = SourceEntry(
    jurisdiction="il",
    url="https://www.ilga.gov/Legislation/publicacts/view/103-0804",
    official_url="https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm",
    kind="html",
)

_HTML_CONTENT = b"<html><body><main>IL HB3773 enacted January 1 2026</main></body></html>"
_HTML_HASH = compute_hash(_HTML_CONTENT, "html")

_STATUTE_TEXT = "# IL HB 3773\n\n(L)(1) Prohibition on discriminatory AI use in employment."

_VALID_META_YAML = textwrap.dedent("""\
    law_id: il-hb3773-pipeline-test
    jurisdiction: Illinois
    short_name: IL HB 3773
    law_name: "Illinois Human Rights Act Amendment"
    citation: "775 ILCS 5/2-102(L)"
    status: effective
    signed_date: 2024-08-09
    effective_dates:
      - date: 2026-01-01
        applies_to: All provisions
    operative_standard: "Effect-based employment discrimination"
    regulated_tech_term: "Artificial intelligence"
    regulated_roles: [deployer]
    scope_domains: [employment]
    enforcement_authority: "Illinois Department of Human Rights"
    enforcement_mechanism: "Civil rights complaint"
    cure_period: null
    private_right_of_action: true
    key_obligations:
      - section: "775 ILCS 5/2-102(L)(1)"
        label: "Prohibition on AI use that results in employment discrimination"
    source_url: "https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm"
    source_page: "https://www.ilga.gov/Legislation/publicacts/view/103-0804"
    retrieved_on: 2026-06-25
""")


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str = "text/html") -> None:
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        pass


class _FakeHTTP:
    """Serves _HTML_CONTENT for the source URL and _HTML_CONTENT for the official URL."""

    def get(self, url: str, **kwargs) -> _FakeResponse:
        return _FakeResponse(_HTML_CONTENT)


def _assess_llm(verdict: str = "relevant") -> StubLLM:
    return StubLLM(
        text=f"verdict={verdict}",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            ("record_classification", {"verdict": verdict, "reason": f"Test verdict: {verdict}."}),
        ],
    )


def _draft_llm() -> StubLLM:
    return StubLLM(
        text="Draft complete.",
        tool_script=[
            ("submit_statute_text", {"law_id": "il-hb3773-pipeline-test", "text": _STATUTE_TEXT}),
            ("submit_metadata", {"metadata_yaml": _VALID_META_YAML}),
        ],
    )


def _empty_store(tmp_path) -> HashStore:
    return HashStore(tmp_path / ".hashes.json")


def _seeded_store(tmp_path) -> HashStore:
    """Hash store pre-seeded with the current content hash → changed=False."""
    store = HashStore(tmp_path / ".hashes.json")
    store.set(_SOURCE.url, _HTML_HASH)
    store.save()
    return store


# ---------------------------------------------------------------------------
# Diff-gate keystone: no change → no LLM call
# ---------------------------------------------------------------------------


def test_pipeline_no_change_produces_no_verdict(tmp_path):
    store = _seeded_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm(),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert len(result.source_results) == 1
    sr = result.source_results[0]
    assert sr.changed is False
    assert sr.verdict is None  # assess was never called


def test_pipeline_no_change_produces_no_staged_files(tmp_path):
    store = _seeded_store(tmp_path)
    staging = tmp_path / "staging"
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm(),
        llm_draft=_draft_llm(),
        staging_path=staging,
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert not staging.exists() or list(staging.iterdir()) == []


def test_pipeline_no_change_does_not_update_store(tmp_path):
    store = _seeded_store(tmp_path)
    original_hash = store.get(_SOURCE.url)
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm(),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert store.get(_SOURCE.url) == original_hash


# ---------------------------------------------------------------------------
# changed + not_relevant → hash committed, no staging
# ---------------------------------------------------------------------------


def test_pipeline_not_relevant_commits_hash(tmp_path):
    store = _empty_store(tmp_path)
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("not_relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert store.get(_SOURCE.url) == _HTML_HASH


def test_pipeline_not_relevant_produces_no_staged_files(tmp_path):
    store = _empty_store(tmp_path)
    staging = tmp_path / "staging"
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("not_relevant"),
        llm_draft=_draft_llm(),
        staging_path=staging,
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert not staging.exists() or list(staging.iterdir()) == []


def test_pipeline_not_relevant_source_result(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("not_relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.changed is True
    assert sr.verdict == "not_relevant"
    assert sr.staged is False


# ---------------------------------------------------------------------------
# changed + uncertain → hash NOT committed, no staging
# ---------------------------------------------------------------------------


def test_pipeline_uncertain_does_not_commit_hash(tmp_path):
    store = _empty_store(tmp_path)
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("uncertain"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert store.get(_SOURCE.url) is None  # hash not committed


def test_pipeline_uncertain_source_result(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("uncertain"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.verdict == "uncertain"
    assert sr.staged is False


# ---------------------------------------------------------------------------
# changed + relevant + draft accepted → hash committed, files staged
# ---------------------------------------------------------------------------


def test_pipeline_relevant_accepted_commits_hash(tmp_path):
    store = _empty_store(tmp_path)
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert store.get(_SOURCE.url) == _HTML_HASH


def test_pipeline_relevant_accepted_stages_two_files(tmp_path):
    store = _empty_store(tmp_path)
    staging = tmp_path / "staging"
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_draft_llm(),
        staging_path=staging,
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.staged is True
    assert len(sr.staged_files) == 2
    assert all(f.exists() for f in sr.staged_files)


def test_pipeline_relevant_accepted_source_result(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.changed is True
    assert sr.verdict == "relevant"
    assert sr.staged is True
    assert sr.rejection_reason is None


# ---------------------------------------------------------------------------
# changed + relevant + draft rejected → hash NOT committed, no files staged
# ---------------------------------------------------------------------------

_BAD_META_YAML = "law_id: broken\nstatus: banana\n"  # invalid Status value


def _rejected_draft_llm() -> StubLLM:
    return StubLLM(
        text="Draft attempted.",
        tool_script=[
            ("submit_statute_text", {"law_id": "broken", "text": _STATUTE_TEXT}),
            ("submit_metadata", {"metadata_yaml": _BAD_META_YAML}),
        ],
    )


def test_pipeline_relevant_draft_rejected_does_not_commit_hash(tmp_path):
    store = _empty_store(tmp_path)
    run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_rejected_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert store.get(_SOURCE.url) is None  # not committed


def test_pipeline_relevant_draft_rejected_stages_no_files(tmp_path):
    store = _empty_store(tmp_path)
    staging = tmp_path / "staging"
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_rejected_draft_llm(),
        staging_path=staging,
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.staged is False
    assert sr.rejection_reason is not None


# ---------------------------------------------------------------------------
# PipelineResult properties
# ---------------------------------------------------------------------------


def test_pipeline_result_total_changed_unchanged(tmp_path):
    store = _seeded_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm(),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert result.total_changed == 0


def test_pipeline_result_total_changed_changed(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert result.total_changed == 1


def test_pipeline_result_total_staged(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert result.total_staged == 1


def test_pipeline_result_all_staged_files(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm("relevant"),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert len(result.all_staged_files) == 2


def test_pipeline_result_no_staged_files_when_unchanged(tmp_path):
    store = _seeded_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=_assess_llm(),
        llm_draft=_draft_llm(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert result.all_staged_files == []


def test_pipeline_source_result_is_dataclass(tmp_path):
    store = _seeded_store(tmp_path)
    result = run_pipeline(
        source_set=[_SOURCE],
        llm_classify=StubLLM(),
        llm_draft=StubLLM(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    assert isinstance(result, PipelineResult)
    assert all(isinstance(sr, SourceResult) for sr in result.source_results)


# ---------------------------------------------------------------------------
# Poll-only sources (auto_draft=False): detect for free, never spend an LLM
# ---------------------------------------------------------------------------

_POLL_ONLY_SOURCE = SourceEntry(
    jurisdiction="co",
    url="https://leg.colorado.gov/bills/sb26-189",
    official_url="https://leg.colorado.gov/bill_files/116489/download",
    kind="html",  # poll hashes the HTML status page; kind here keeps the test hash == _HTML_HASH
    auto_draft=False,
)


class _RaisingLLM:
    """Any LLM method call is a test failure — proves the poll-only path spends nothing."""

    def run_tools(self, *a, **k):
        raise AssertionError("poll-only source must not invoke the LLM")

    def complete(self, *a, **k):
        raise AssertionError("poll-only source must not invoke the LLM")

    def complete_structured(self, *a, **k):
        raise AssertionError("poll-only source must not invoke the LLM")

    def stream(self, *a, **k):
        raise AssertionError("poll-only source must not invoke the LLM")


def test_pipeline_poll_only_first_sight_commits_baseline(tmp_path):
    store = _empty_store(tmp_path)
    result = run_pipeline(
        source_set=[_POLL_ONLY_SOURCE],
        llm_classify=_RaisingLLM(),
        llm_draft=_RaisingLLM(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.verdict == "baseline"
    assert sr.staged is False
    # Baseline is committed so steady state is silent on the next poll.
    assert store.get(_POLL_ONLY_SOURCE.url) == _HTML_HASH


def test_pipeline_poll_only_real_change_flags_manual_review(tmp_path):
    store = HashStore(tmp_path / ".hashes.json")
    store.set(_POLL_ONLY_SOURCE.url, "an-older-different-hash")
    store.save()
    result = run_pipeline(
        source_set=[_POLL_ONLY_SOURCE],
        llm_classify=_RaisingLLM(),
        llm_draft=_RaisingLLM(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.changed is True
    assert sr.verdict == "manual_review"
    assert sr.staged is False
    assert sr.rejection_reason is not None
    # Hash is NOT committed — the change keeps surfacing until a human acts.
    assert store.get(_POLL_ONLY_SOURCE.url) == "an-older-different-hash"


def test_pipeline_poll_only_no_change_is_silent(tmp_path):
    store = HashStore(tmp_path / ".hashes.json")
    store.set(_POLL_ONLY_SOURCE.url, _HTML_HASH)
    store.save()
    result = run_pipeline(
        source_set=[_POLL_ONLY_SOURCE],
        llm_classify=_RaisingLLM(),
        llm_draft=_RaisingLLM(),
        staging_path=tmp_path / "staging",
        hash_store=store,
        http_client=_FakeHTTP(),
    )
    sr = result.source_results[0]
    assert sr.changed is False
    assert sr.verdict is None  # handled by the no-change gate, no flag
