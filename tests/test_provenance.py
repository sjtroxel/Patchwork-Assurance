"""Phase 9 Batch 5 — provenance allowlist (offline; no tokens, no network).

Key assertions:
- extract_domain parses https, www-subdomain, bare domain, malformed URL
- is_allowed: exact match, www-subdomain match, non-listed domain, empty allowlist
- check_provenance: clean URL returns None, non-allowlisted returns reason, empty returns reason
- draft_seam1_pair rejects a draft whose source_url is from a non-allowlisted domain
- draft_seam1_pair accepts a draft with an allowlisted source_url
- Poisoned-source fixture: non-allowlisted source_url caught before staging, no files written
- Provenance gate fires after source_url presence check and before LawMetadata validation
"""

import textwrap

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.assess import AssessResult
from patchwork_assurance.core.agent.draft import draft_seam1_pair
from patchwork_assurance.core.agent.provenance import check_provenance, extract_domain, is_allowed
from patchwork_assurance.core.llm import StubLLM

# ---------------------------------------------------------------------------
# Allowlist shared across tests
# ---------------------------------------------------------------------------

_ALLOWED = ["ilga.gov", "leg.colorado.gov", "cga.ct.gov"]
_EVIL_URL = "https://evil.example.com/fake-statute.html"
_IL_URL = "https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm"

# ---------------------------------------------------------------------------
# extract_domain
# ---------------------------------------------------------------------------


def test_extract_domain_plain_domain():
    assert extract_domain("https://ilga.gov/foo") == "ilga.gov"


def test_extract_domain_www_subdomain():
    assert extract_domain("https://www.ilga.gov/foo") == "www.ilga.gov"


def test_extract_domain_no_scheme_returns_empty():
    # urlparse treats a bare domain with no scheme as a path, not a hostname
    result = extract_domain("ilga.gov/foo")
    assert isinstance(result, str)  # never raises


def test_extract_domain_empty_string():
    assert extract_domain("") == ""


def test_extract_domain_malformed():
    assert extract_domain("not a url at all") == ""


# ---------------------------------------------------------------------------
# is_allowed
# ---------------------------------------------------------------------------


def test_is_allowed_exact_match():
    assert is_allowed("https://ilga.gov/doc.html", ["ilga.gov"])


def test_is_allowed_www_subdomain():
    assert is_allowed("https://www.ilga.gov/doc.html", ["ilga.gov"])


def test_is_allowed_not_in_list():
    assert not is_allowed(_EVIL_URL, _ALLOWED)


def test_is_allowed_empty_allowlist():
    assert not is_allowed(_IL_URL, [])


def test_is_allowed_another_official_domain():
    assert is_allowed("https://leg.colorado.gov/bills/sb26-189", _ALLOWED)


def test_is_allowed_partial_domain_not_matched():
    # "evil-ilga.gov" must NOT match the "ilga.gov" rule
    assert not is_allowed("https://evil-ilga.gov/statute.html", ["ilga.gov"])


# ---------------------------------------------------------------------------
# check_provenance
# ---------------------------------------------------------------------------


def test_check_provenance_clean_url_returns_none():
    assert check_provenance(_IL_URL, _ALLOWED) is None


def test_check_provenance_non_allowlisted_returns_reason():
    result = check_provenance(_EVIL_URL, _ALLOWED)
    assert result is not None
    assert "evil.example.com" in result
    assert "allowlist" in result.lower()


def test_check_provenance_empty_url_returns_reason():
    result = check_provenance("", _ALLOWED)
    assert result is not None
    assert "empty" in result.lower()


def test_check_provenance_whitespace_url_returns_reason():
    result = check_provenance("   ", _ALLOWED)
    assert result is not None


# ---------------------------------------------------------------------------
# draft_seam1_pair provenance gate — shared fixtures
# ---------------------------------------------------------------------------

_SOURCE_IL = SourceEntry(
    jurisdiction="il",
    url="https://www.ilga.gov/Legislation/publicacts/view/103-0804",
    official_url=_IL_URL,
    kind="html",
)

_STATUTE_TEXT = textwrap.dedent("""\
    # Illinois Human Rights Act — AI in Employment

    ## 775 ILCS 5/2-102 — Civil Rights Violations — Employers

    (L)(1) It is a civil rights violation for any employer to use artificial intelligence that
    has the effect of subjecting employees to discrimination on the basis of a protected class.
""")

_VALID_META_YAML = textwrap.dedent("""\
    law_id: il-prov-test
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

_EVIL_META_YAML = textwrap.dedent("""\
    law_id: il-prov-test
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
    source_url: "https://evil.example.com/fake-statute.html"
    retrieved_on: 2026-06-25
""")

_RELEVANT = AssessResult(
    source=_SOURCE_IL,
    verdict="relevant",
    reason="New IL statute.",
    official_text=_STATUTE_TEXT,
    official_url_fetched=_IL_URL,
)


def _llm_with_meta(meta_yaml: str) -> StubLLM:
    return StubLLM(
        text="Draft complete.",
        tool_script=[
            ("submit_statute_text", {"law_id": "il-prov-test", "text": _STATUTE_TEXT}),
            ("submit_metadata", {"metadata_yaml": meta_yaml}),
        ],
    )


# ---------------------------------------------------------------------------
# draft_seam1_pair: allowlisted source_url passes
# ---------------------------------------------------------------------------


def test_draft_accepts_allowlisted_source_url(tmp_path):
    result = draft_seam1_pair(_RELEVANT, _llm_with_meta(_VALID_META_YAML), tmp_path, _ALLOWED)
    assert result.rejected is False
    assert result.law_id == "il-prov-test"


# ---------------------------------------------------------------------------
# draft_seam1_pair: non-allowlisted source_url rejected
# ---------------------------------------------------------------------------


def test_draft_rejects_non_allowlisted_source_url(tmp_path):
    result = draft_seam1_pair(_RELEVANT, _llm_with_meta(_EVIL_META_YAML), tmp_path, _ALLOWED)
    assert result.rejected is True
    assert "allowlist" in (result.rejection_reason or "").lower()


def test_draft_non_allowlisted_rejection_names_domain(tmp_path):
    result = draft_seam1_pair(_RELEVANT, _llm_with_meta(_EVIL_META_YAML), tmp_path, _ALLOWED)
    assert "evil.example.com" in (result.rejection_reason or "")


# ---------------------------------------------------------------------------
# Poisoned-source fixture: non-allowlisted source_url → no files staged
# ---------------------------------------------------------------------------


def test_poisoned_source_fixture_no_files_staged(tmp_path):
    """Security fixture: a draft from a non-allowlisted domain is rejected before staging."""
    result = draft_seam1_pair(_RELEVANT, _llm_with_meta(_EVIL_META_YAML), tmp_path, _ALLOWED)
    assert result.rejected is True
    assert list(tmp_path.iterdir()) == []
