"""core.metadata_query — structured retrieval over law metadata (Phase 8 §6).

All offline: the table build, the SQL guard, and the deterministic lookup are free; the LLM-driven
paths are exercised with StubLLM (zero tokens). The stub proves the WIRING; whether the real model
writes good SQL / extracts the right field is the deferred live check (Phase 8 §7)."""

import sqlite3
from pathlib import Path

import pytest
import yaml

from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.llm import StubLLM
from patchwork_assurance.core.metadata_query import (
    MetadataIntent,
    UnsafeSQLError,
    build_metadata_db,
    extract_intent,
    lookup_intent,
    query_metadata,
    run_sql,
    text_to_sql,
    validate_sql,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _laws() -> list[LawMetadata]:
    """Two laws so jurisdiction filtering is meaningful: the fixture (Testland) + a second."""
    base = yaml.safe_load((FIXTURES / "fake-law.meta.yaml").read_text())
    other = dict(base)
    other.update(
        law_id="fake-law-2",
        jurisdiction="Otherland",
        short_name="Fake Law 2",
        scope_domains=["insurance"],
        cure_period=None,
        effective_dates=[{"date": "2027-10-01", "applies_to": "act generally"}],
    )
    return [LawMetadata(**base), LawMetadata(**other)]


@pytest.fixture
def conn():
    return build_metadata_db(_laws())


# --- table build -----------------------------------------------------------------------------------


def test_build_populates_rows_and_flattened_booleans(conn):
    rows = run_sql(
        conn,
        "SELECT law_id, scope_employment, scope_insurance, role_deployer, role_developer FROM laws",
    )
    by_id = {r["law_id"]: r for r in rows}
    assert by_id["fake-law"]["scope_employment"] == 1
    assert by_id["fake-law"]["scope_insurance"] == 0
    assert by_id["fake-law-2"]["scope_insurance"] == 1
    assert by_id["fake-law"]["role_deployer"] == 1
    assert by_id["fake-law"]["role_developer"] == 0


def test_effective_dates_child_table(conn):
    rows = run_sql(conn, "SELECT law_id FROM effective_dates WHERE effective_date < '2027-01-01'")
    assert [r["law_id"] for r in rows] == ["fake-law"]  # Testland 2026-07-01; Otherland 2027-10-01


def test_connection_is_read_only(conn):
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("UPDATE laws SET cure_period = 'hacked'")


# --- the guard -------------------------------------------------------------------------------------


def test_guard_allows_clean_select():
    validate_sql("SELECT short_name, cure_period FROM laws WHERE jurisdiction = 'Testland'")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM laws",
        "UPDATE laws SET cure_period = 'x'",
        "DROP TABLE laws",
        "SELECT 1; DROP TABLE laws",
        "SELECT short_name FROM users",  # disallowed table
        "SELECT secret_column FROM laws",  # disallowed column
        "PRAGMA query_only = OFF",
        "ATTACH DATABASE 'x' AS y",
    ],
)
def test_guard_rejects_unsafe(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)


def test_run_sql_rejects_before_executing(conn):
    with pytest.raises(UnsafeSQLError):
        run_sql(conn, "SELECT evil FROM laws")


# --- deterministic intent lookup -------------------------------------------------------------------


def test_lookup_intent_filters_by_jurisdiction(conn):
    rows = lookup_intent(conn, MetadataIntent(field="cure_period", jurisdiction="Testland"))
    assert len(rows) == 1
    assert rows[0]["cure_period"] == "30 days"


def test_lookup_intent_unscoped_returns_all(conn):
    rows = lookup_intent(conn, MetadataIntent(field="enforcement_authority"))
    assert len(rows) == 2


def test_lookup_intent_unknown_field_raises(conn):
    with pytest.raises(UnsafeSQLError):
        lookup_intent(conn, MetadataIntent(field="password"))


# --- LLM-driven paths via StubLLM (wiring only) ----------------------------------------------------


def test_text_to_sql_strips_code_fence():
    llm = StubLLM(text="```sql\nSELECT short_name FROM laws\n```")
    assert text_to_sql("anything", llm) == "SELECT short_name FROM laws"


def test_extract_intent_returns_structured():
    llm = StubLLM(structured=MetadataIntent(field="cure_period", jurisdiction="Testland"))
    assert extract_intent("what is the cure period?", llm).field == "cure_period"


def test_query_metadata_sql_mode_with_stub(conn):
    llm = StubLLM(text="SELECT short_name, cure_period FROM laws WHERE jurisdiction = 'Testland'")
    rows = query_metadata("q", conn, llm, mode="sql")
    assert [r["short_name"] for r in rows] == ["Fake Law 1"]


def test_query_metadata_intent_mode_with_stub(conn):
    llm = StubLLM(structured=MetadataIntent(field="cure_period"))
    rows = query_metadata("q", conn, llm, mode="intent")
    assert len(rows) == 2


def test_query_metadata_fails_closed_on_unsafe_sql(conn):
    llm = StubLLM(text="DROP TABLE laws")
    assert query_metadata("q", conn, llm, mode="sql") == []  # guard caught it; no rows, no raise
