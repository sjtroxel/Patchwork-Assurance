"""Exhaustive deterministic scope screen tests — no LLM, no network."""

from patchwork_assurance.core.contracts import Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.scope import CAUTIOUS, LENIENT, STRICT, applicable_laws


def _law(law_id, jurisdiction, short_name, roles, domains):
    """Build a minimal LawMetadata for testing (bypasses fields scope doesn't use)."""
    return LawMetadata.model_construct(
        law_id=law_id,
        jurisdiction=jurisdiction,
        short_name=short_name,
        regulated_roles=roles,
        scope_domains=domains,
    )


CO = _law(
    "co-sb-26-189",
    "CO",
    "CO AI Act",
    ["deployer", "developer"],
    ["employment", "financial_lending"],
)
CT = _law("ct-sb-5", "CT", "CT AI Act", ["deployer", "developer"], ["employment", "health_care"])
LAWS = [CO, CT]


def _sit(**kw):
    defaults = dict(ai_use="yes", jurisdictions=[], decision_domains=[], roles=[])
    return Situation(**{**defaults, **kw})


# --- ai_use="no" → all no ---
def test_no_ai_use_all_no():
    results = applicable_laws(
        _sit(
            ai_use="no",
            jurisdictions=["CO", "CT"],
            decision_domains=["employment"],
            roles=["deployer"],
        ),
        LAWS,
    )
    assert all(r.in_scope == "no" for r in results)


# --- nexus given + domain + role match ---
def test_co_employment_deployer_yes():
    results = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=["employment"], roles=["deployer"]), LAWS
    )
    by_id = {r.law_id: r for r in results}
    assert by_id["co-sb-26-189"].in_scope == "yes"
    assert by_id["ct-sb-5"].in_scope == "no"


def test_both_states_employment_both_yes():
    results = applicable_laws(
        _sit(jurisdictions=["CO", "CT"], decision_domains=["employment"], roles=["deployer"]), LAWS
    )
    assert all(r.in_scope == "yes" for r in results)


def test_co_lending_yes_ct_no():
    results = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=["financial_lending"], roles=["deployer"]), LAWS
    )
    by_id = {r.law_id: r for r in results}
    assert by_id["co-sb-26-189"].in_scope == "yes"
    assert by_id["ct-sb-5"].in_scope == "no"


def test_ct_health_care_yes_co_no():
    results = applicable_laws(
        _sit(jurisdictions=["CT"], decision_domains=["health_care"], roles=["deployer"]), LAWS
    )
    by_id = {r.law_id: r for r in results}
    assert by_id["ct-sb-5"].in_scope == "yes"
    assert by_id["co-sb-26-189"].in_scope == "no"


# --- nexus but unrelated domain AND no role → no ---
def test_nexus_unrelated_domain_no():
    # ai_companion is not in CO or CT scope_domains; no role given → both "no"
    results = applicable_laws(
        _sit(jurisdictions=["CO", "CT"], decision_domains=["ai_companion"], roles=[]), LAWS
    )
    assert all(r.in_scope == "no" for r in results)


# --- no jurisdictions given → uncertain for all ---
def test_no_jurisdictions_uncertain():
    results = applicable_laws(
        _sit(jurisdictions=[], decision_domains=["employment"], roles=["deployer"]), LAWS
    )
    assert all(r.in_scope == "uncertain" for r in results)


# --- jurisdiction given but domain/role left BLANK → uncertain, NOT a confident no (Problem B) ---
def test_nexus_only_now_uncertain():
    results = applicable_laws(_sit(jurisdictions=["CO"], decision_domains=[], roles=[]), LAWS)
    by_id = {r.law_id: r for r in results}
    # CO: nexus match but domain+role blank → uncertain (used to be a dangerous "no")
    assert by_id["co-sb-26-189"].in_scope == "uncertain"
    # CT: user named CO, not CT → jurisdiction MISMATCH → no
    assert by_id["ct-sb-5"].in_scope == "no"


# --- partial overlap → uncertain ---
def test_domain_match_no_role_uncertain():
    # Has domain overlap but no role given → uncertain
    results = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=["employment"], roles=[]), LAWS
    )
    by_id = {r.law_id: r for r in results}
    assert by_id["co-sb-26-189"].in_scope == "uncertain"


def test_role_match_no_domain_uncertain():
    # Has role overlap but no domain given → uncertain
    results = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=[], roles=["deployer"]), LAWS
    )
    by_id = {r.law_id: r for r in results}
    assert by_id["co-sb-26-189"].in_scope == "uncertain"


# --- wrong jurisdiction → no ---
def test_third_state_nexus_no():
    results = applicable_laws(
        _sit(jurisdictions=["TX"], decision_domains=["employment"], roles=["deployer"]), LAWS
    )
    assert all(r.in_scope == "no" for r in results)


# --- developer role ---
def test_developer_role_yes():
    results = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=["employment"], roles=["developer"]), LAWS
    )
    by_id = {r.law_id: r for r in results}
    assert by_id["co-sb-26-189"].in_scope == "yes"


# --- Problem A: "didn't say" (BLANK) vs "said, no match" (MISMATCH) must differ ---
def test_blank_domain_is_uncertain_but_named_wrong_domain_is_no():
    # BLANK domain → uncertain (we don't know)
    blank = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=[], roles=["deployer"]), LAWS
    )
    assert {r.law_id: r.in_scope for r in blank}["co-sb-26-189"] == "uncertain"
    # NAMED a domain CO doesn't cover → no (they told us, and it's outside)
    named = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=["health_care"], roles=["deployer"]), LAWS
    )
    co = {r.law_id: r for r in named}["co-sb-26-189"]
    assert co.in_scope == "no"
    assert "outside" in co.reason.lower()  # honest reason, not "we need more info"


# --- role MISMATCH (a law that regulates only one role) → no ---
DEPLOYER_ONLY = _law("dep-only", "CO", "Deployer-Only Act", ["deployer"], ["employment"])


def test_role_mismatch_is_no():
    # developer against a deployer-only law, everything else matching → no
    results = applicable_laws(
        _sit(jurisdictions=["CO"], decision_domains=["employment"], roles=["developer"]),
        [DEPLOYER_ONLY],
    )
    assert results[0].in_scope == "no"


# --- empty form → uncertain everywhere, never a confident no ---
def test_empty_form_all_uncertain():
    results = applicable_laws(_sit(), LAWS)  # ai_use defaults "yes"; everything else blank
    assert all(r.in_scope == "uncertain" for r in results)


# --- the strictness dial ---
def test_lenient_collapses_blanks_to_no():
    # Same nexus-only input that's uncertain under CAUTIOUS becomes "no" under LENIENT.
    sit = _sit(jurisdictions=["CO"], decision_domains=[], roles=[])
    assert {r.law_id: r.in_scope for r in applicable_laws(sit, LAWS, CAUTIOUS)}[
        "co-sb-26-189"
    ] == "uncertain"
    assert {r.law_id: r.in_scope for r in applicable_laws(sit, LAWS, LENIENT)}[
        "co-sb-26-189"
    ] == "no"


def test_strict_hedges_mismatch_to_uncertain():
    # A named-wrong domain that's "no" under CAUTIOUS becomes "uncertain" under STRICT.
    sit = _sit(jurisdictions=["CO"], decision_domains=["health_care"], roles=["deployer"])
    assert {r.law_id: r.in_scope for r in applicable_laws(sit, LAWS, CAUTIOUS)}[
        "co-sb-26-189"
    ] == "no"
    assert {r.law_id: r.in_scope for r in applicable_laws(sit, LAWS, STRICT)}[
        "co-sb-26-189"
    ] == "uncertain"


def test_default_policy_is_cautious():
    # Calling without a policy arg matches passing CAUTIOUS explicitly.
    sit = _sit(jurisdictions=["CO"], decision_domains=[], roles=[])
    default = [r.in_scope for r in applicable_laws(sit, LAWS)]
    explicit = [r.in_scope for r in applicable_laws(sit, LAWS, CAUTIOUS)]
    assert default == explicit


# --- Phase 4.6: nexus reframe, home-state auto-nexus, unsure AI use ---
def test_out_of_state_owner_with_nexus_in_scope():
    # The headline case: a Missouri business (no MO AI law) with a Colorado nexus is reached by CO.
    sit = _sit(
        home_state="MO", jurisdictions=["CO"], decision_domains=["employment"], roles=["deployer"]
    )
    co = {r.law_id: r for r in applicable_laws(sit, LAWS)}["co-sb-26-189"]
    assert co.in_scope == "yes"
    assert "nexus" in co.reason.lower()


def test_home_state_is_regulating_auto_nexus():
    # Home state CO, no nexus states named → CO still applies (home state unions into the nexus set).
    sit = _sit(
        home_state="CO", jurisdictions=[], decision_domains=["employment"], roles=["deployer"]
    )
    co = {r.law_id: r for r in applicable_laws(sit, LAWS)}["co-sb-26-189"]
    assert co.in_scope == "yes"


def test_home_state_non_regulating_creates_no_nexus():
    # Home state MO is not a regulating jurisdiction → no auto-nexus; jurisdiction stays blank.
    sit = _sit(
        home_state="MO", jurisdictions=[], decision_domains=["employment"], roles=["deployer"]
    )
    assert all(r.in_scope == "uncertain" for r in applicable_laws(sit, LAWS))


def test_unsure_ai_use_not_excluded_and_surfaced():
    sit = _sit(
        jurisdictions=["CO"], decision_domains=["employment"], roles=["deployer"], ai_use="unsure"
    )
    co = {r.law_id: r for r in applicable_laws(sit, LAWS)}["co-sb-26-189"]
    assert co.in_scope == "yes"
    assert "inventory" in co.reason.lower()
