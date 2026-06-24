"""Structured retrieval over the law-level metadata (Phase 8 §6).

The corpus metadata (LawMetadata, SPEC §4) is a tiny table — one row per law. Factual questions
("which laws take effect before 2027?", "what is CT's cure period?") are answered deterministically
from that table instead of by prose similarity. Two paths, both fail-closed:

  - intent_lookup  — the LLM names a field + jurisdiction; Python does a parametric lookup. Safe,
                     one cheap call, often sufficient at N=2. The measured baseline.
  - text_to_sql    — the LLM writes a SELECT; we validate it against a table/column allowlist and run
                     it on a read-only connection. The job-relevant learning rep, behind a hard guard.

Everything routes through core/ (keystone invariant); nothing here imports api/ or ui/.

COST NOTE: the table build + the guard + the lookups are deterministic and FREE. The two functions
that call the LLM (extract_intent, text_to_sql, and therefore query_metadata) spend tokens only when
LLM_PROVIDER=anthropic; with StubLLM they are free and fully unit-testable. Their activation against
the real provider — and any decision to wire them into the always-on chat path — is deferred until the
eval (Phase 8 §7) justifies it and funds allow (mirrors Phase 7's deferred-to-paid-run pattern).
"""

import re
import sqlite3
from datetime import date
from typing import get_args

from pydantic import BaseModel

from patchwork_assurance.core import obs
from patchwork_assurance.core.contracts import Msg
from patchwork_assurance.core.corpus.metadata import LawMetadata, RegulatedRole, ScopeDomain
from patchwork_assurance.core.llm import LLMError

# --- schema (mirrors the loader's flatten-to-scalars, SPEC §6) --------------------------------------

_SCALAR_COLUMNS = (
    "law_id",
    "jurisdiction",
    "short_name",
    "law_name",
    "citation",
    "status",
    "signed_date",
    "operative_standard",
    "regulated_tech_term",
    "enforcement_authority",
    "enforcement_mechanism",
    "cure_period",
    "private_right_of_action",
)
_SCOPE_COLUMNS = tuple(f"scope_{d}" for d in get_args(ScopeDomain))
_ROLE_COLUMNS = tuple(f"role_{r}" for r in get_args(RegulatedRole))
_LAW_COLUMNS = _SCALAR_COLUMNS + _SCOPE_COLUMNS + _ROLE_COLUMNS
_INT_COLUMNS = frozenset(_SCOPE_COLUMNS + _ROLE_COLUMNS + ("private_right_of_action",))

# Allowlist the guard checks every generated query against. Tables + the union of every column.
_TABLES = frozenset({"laws", "effective_dates"})
_ALL_COLUMNS = frozenset(_LAW_COLUMNS) | {"effective_date", "applies_to"}


class UnsafeSQLError(Exception):
    """A generated query failed the allowlist guard. Callers fail closed (fall back), never execute."""


# --- table build ------------------------------------------------------------------------------------


def _coltype(col: str) -> str:
    return "INTEGER" if col in _INT_COLUMNS else "TEXT"


def _law_value(law: LawMetadata, col: str):
    if col.startswith("scope_"):
        return int(col.removeprefix("scope_") in law.scope_domains)
    if col.startswith("role_"):
        return int(col.removeprefix("role_") in law.regulated_roles)
    val = getattr(law, col)
    if isinstance(val, bool):  # before date/str; bool is not a date
        return int(val)
    if isinstance(val, date):
        return val.isoformat()  # ISO strings sort chronologically, so date WHERE/ORDER works
    return val


def build_metadata_db(laws: list[LawMetadata]) -> sqlite3.Connection:
    """In-memory table from the loaded metadata, then locked read-only. The read-only connection is
    the belt; the allowlist guard (validate_sql) is the suspenders — defense in depth."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(f"CREATE TABLE laws ({', '.join(f'{c} {_coltype(c)}' for c in _LAW_COLUMNS)})")
    conn.execute("CREATE TABLE effective_dates (law_id TEXT, effective_date TEXT, applies_to TEXT)")
    placeholders = ", ".join("?" * len(_LAW_COLUMNS))
    for law in laws:
        conn.execute(
            f"INSERT INTO laws ({', '.join(_LAW_COLUMNS)}) VALUES ({placeholders})",
            [_law_value(law, c) for c in _LAW_COLUMNS],
        )
        for ed in law.effective_dates:
            conn.execute(
                "INSERT INTO effective_dates VALUES (?, ?, ?)",
                (law.law_id, ed.date.isoformat(), ed.applies_to),
            )
    conn.commit()
    conn.execute(
        "PRAGMA query_only = ON"
    )  # writes now raise; generated SQL can't flip it (no PRAGMA)
    return conn


# --- the guard --------------------------------------------------------------------------------------

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|TRIGGER|GRANT)\b",
    re.I,
)
# Keywords + functions a legitimate read query may use. Anything else that looks like an identifier
# must resolve to an allowlisted table or column, or the query is rejected.
_SQL_KEYWORDS = frozenset(
    w.upper()
    for w in (
        "select from where and or not null is as join inner left outer on using order by group "
        "having limit offset asc desc distinct in like between case when then else end exists "
        "union all count min max avg sum total coalesce lower upper length true false"
    ).split()
)


def _identifiers(sql: str) -> list[str]:
    no_str = re.sub(r"'[^']*'", " ", sql)  # drop string literals (values aren't identifiers)
    no_str = re.sub(r"\bAS\s+\w+", " ", no_str, flags=re.I)  # drop column aliases
    no_str = re.sub(r"\b\w+\.", "", no_str)  # collapse table.col -> col
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", no_str)


def validate_sql(sql: str) -> None:
    """Raise UnsafeSQLError unless `sql` is a single read-only SELECT over allowlisted identifiers."""
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise UnsafeSQLError("empty query")
    if ";" in s:
        raise UnsafeSQLError("multiple statements are not allowed")
    if not re.match(r"^\s*SELECT\b", s, re.I):
        raise UnsafeSQLError("only SELECT statements are allowed")
    if _FORBIDDEN.search(s):
        raise UnsafeSQLError("statement contains a forbidden keyword")
    for ident in _identifiers(s):
        if (
            ident.upper() in _SQL_KEYWORDS
            or ident.lower() in _TABLES
            or ident.lower() in _ALL_COLUMNS
        ):
            continue
        raise UnsafeSQLError(f"unknown identifier: {ident!r}")


def run_sql(conn: sqlite3.Connection, sql: str) -> list[dict]:
    """Validate then execute. Metadata-only log line — never the SQL string or its values (privacy)."""
    validate_sql(sql)
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    obs.log_event("metadata_query", path="sql", n_rows=len(rows))
    return rows


# --- deterministic intent lookup (the safe baseline) ------------------------------------------------


class MetadataIntent(BaseModel):
    """What the LLM extracts for the deterministic path: which field, optionally scoped to a law's
    jurisdiction. Both are validated before any query runs."""

    field: str
    jurisdiction: str | None = None


def lookup_intent(conn: sqlite3.Connection, intent: MetadataIntent) -> list[dict]:
    """Deterministic, parametric lookup. The field is allowlist-checked (so interpolating the column
    name is safe); the jurisdiction value is bound as a parameter, never interpolated."""
    if intent.field not in _ALL_COLUMNS:
        raise UnsafeSQLError(f"unknown field: {intent.field!r}")
    cols = ["law_id", "short_name", "jurisdiction"]
    if intent.field not in cols:
        cols.append(intent.field)
    sql = f"SELECT {', '.join(cols)} FROM laws"
    params: tuple = ()
    if intent.jurisdiction:
        sql += " WHERE jurisdiction = ?"
        params = (intent.jurisdiction,)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    obs.log_event("metadata_query", path="intent", n_rows=len(rows))
    return rows


# --- LLM-driven paths (COST-BEARING; activation deferred — see module docstring) --------------------

_INTENT_SYSTEM = (
    "You map a user's factual question about US AI-regulation statutes to a single metadata FIELD and, "
    "optionally, a JURISDICTION. Choose exactly one field name from this list and nothing else:\n"
    f"{', '.join(sorted(_ALL_COLUMNS))}\n"
    "If the question names a state/jurisdiction, set it; otherwise leave jurisdiction null. Do not "
    "answer the question — only identify the field and jurisdiction."
)

_SQL_SYSTEM = (
    "You translate a user's factual question into ONE read-only SQLite SELECT over this schema, and "
    "return only the SQL (no prose, no code fences, no table aliases, no semicolon):\n"
    f"  laws({', '.join(_LAW_COLUMNS)})\n"
    "  effective_dates(law_id, effective_date, applies_to)\n"
    "scope_* and role_* columns are 1/0 booleans; effective_date is an ISO 'YYYY-MM-DD' string. "
    "Reference only the tables and columns shown. Never write, alter, or attach."
)


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def extract_intent(question: str, llm) -> MetadataIntent:
    """COST-BEARING (one structured LLM call) when the provider is real. Deferred until funded."""
    return llm.complete_structured(
        _INTENT_SYSTEM, [Msg(role="user", content=question)], MetadataIntent
    )


def text_to_sql(question: str, llm) -> str:
    """COST-BEARING (one LLM completion) when the provider is real. Deferred until funded."""
    return _strip_code_fence(llm.complete(_SQL_SYSTEM, [Msg(role="user", content=question)]))


def query_metadata(
    question: str, conn: sqlite3.Connection, llm, *, mode: str = "intent"
) -> list[dict]:
    """Fail-closed structured answer. Returns rows; an empty list signals the caller to fall back to
    semantic retrieval. COST-BEARING (one LLM call); not wired into the always-on path by default —
    the eval (Phase 8 §7) decides whether it earns its keep at N=2 (see module docstring)."""
    try:
        if mode == "sql":
            return run_sql(conn, text_to_sql(question, llm))
        return lookup_intent(conn, extract_intent(question, llm))
    except (UnsafeSQLError, sqlite3.Error, LLMError):
        return []  # fail closed; caller falls back to semantic
