from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceEntry(BaseModel):
    """One source in the polling set. Adding a jurisdiction = adding an entry here (data, not code)."""

    jurisdiction: str
    url: str  # the status page to poll for changes
    official_url: str = (
        ""  # the document to fetch on a relevant change (source_url from corpus meta)
    )
    kind: str = "html"  # "html" | "pdf" — kind of the official document
    cadence_hours: int = 24
    # auto_draft=True: a detected change runs the full LLM assess + draft pipeline.
    # auto_draft=False: poll-only — detect change for FREE (HTML hash), never spend an LLM, never
    # auto-draft; a real change is flagged "manual_review" for a human. Use for sources the agent
    # can't faithfully auto-ingest (e.g. image-scan PDFs like CO/CT) — keeps them monitored cheaply
    # without the daily re-spend that "uncertain→retry" would cause on an unextractable PDF.
    auto_draft: bool = True


class Settings(BaseSettings):
    """Config from environment / .env. In dev the UI talks to localhost; in Phase 5
    the same code points at the deployed API by setting API_BASE_URL — no code change."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000"
    corpus_path: str = "corpus"
    chroma_path: str = ".chroma"
    llm_provider: str = "stub"  # "stub" | "anthropic" | "openrouter"
    # Two-model split (Phase 5): chat gets fast/cheap Haiku (unlimited); the memo gets Sonnet's higher
    # reasoning (rate-limited, see api memo_rate_limit). Re-verify IDs/pricing at build (standing rule).
    chat_model: str = "claude-haiku-4-5"
    memo_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str | None = None  # read from env ANTHROPIC_API_KEY; never commit
    # OpenRouter (Phase 8 interlude): one OpenAI-compatible key fronts ~315 models incl. free ones.
    # Set llm_provider=openrouter, OPENROUTER_API_KEY, and override chat/memo/judge_model with
    # OpenRouter IDs (e.g. "deepseek/deepseek-chat:free", "anthropic/claude-haiku-4-5"). Key never commits.
    openrouter_api_key: str | None = None  # read from env OPENROUTER_API_KEY
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    top_k: int = 5
    max_tokens: int = 16000
    # Retrieval strategy (Phase 8). The eval sweep picks the production default; `filtered` is the
    # conservative placeholder (== Phase 1/2 behavior) until the scorecard justifies hybrid/routed.
    # `routed` and the agentic router arrive in Phase 8 batch 4. enable_lexical builds the BM25 index.
    retrieval_mode: str = "filtered"  # semantic | filtered | hybrid | routed
    router: str = "rules"  # rules | agentic
    enable_lexical: bool = True
    memo_daily_limit_per_ip: int = 2  # Sonnet cost cap; 0 = unlimited
    cors_allow_origins: list[str] = ["http://localhost:8501"]
    # Eval LLM-as-judge (Phase 6 Tier B). Judge model must differ from the judged model: the memo
    # is Sonnet, so the judge is Opus (don't let a model grade its own blind spots). Off by default
    # so `make eval` stays free; the judged tier spends tokens and is opt-in via --judge.
    judge_model: str = "claude-opus-4-8"
    eval_use_judge: bool = False
    # Hard cap (circuit breaker): a single judged eval run may not generate more than this many
    # memos, no matter how it was invoked. Raise it deliberately if the gold set grows past it.
    eval_max_judged_cases: int = 50
    # Observability (Phase 7). Structured JSON logs to stdout; metadata only, never user content.
    log_level: str = "INFO"
    enable_tracing: bool = True
    # Phase 9 monitoring agent. source_set drives the poll loop generically — adding a jurisdiction
    # is adding an entry here (data, not code). hash_store_path is the flat JSON last-seen store;
    # staging_path is where the agent drafts file pairs before the human-gate PR.
    source_set: list[SourceEntry] = [
        # CO/CT official text is image-scan PDF — the agent can't faithfully auto-extract it, so
        # these are poll-only: their HTML status pages are monitored for free, and a real change is
        # flagged for manual review rather than auto-drafted (and never re-spends an LLM call).
        SourceEntry(
            jurisdiction="co",
            url="https://leg.colorado.gov/bills/sb26-189",
            official_url="https://leg.colorado.gov/bill_files/116489/download",
            kind="pdf",
            auto_draft=False,
        ),
        SourceEntry(
            jurisdiction="ct",
            url="https://www.cga.ct.gov/asp/cgabillstatus/cgabillstatus.asp?selBillType=Bill&bill_num=SB05&which_year=2026",
            official_url="https://www.cga.ct.gov/2026/act/pa/pdf/2026PA-00015-R00SB-00005-PA.pdf",
            kind="pdf",
            auto_draft=False,
        ),
        SourceEntry(
            jurisdiction="il",
            url="https://www.ilga.gov/Legislation/publicacts/view/103-0804",
            official_url="https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm",
            kind="html",
        ),
    ]
    hash_store_path: str = ".agent_hashes.json"
    staging_path: str = "corpus/_staging"
    classify_model: str = "claude-haiku-4-5"
    draft_model: str = "claude-sonnet-4-6"
    # Provenance allowlist (Phase 9 Batch 5). The agent rejects any draft whose source_url
    # domain is not in this list. Adding a jurisdiction = adding its official domain here.
    # Env override: ALLOWED_SOURCE_DOMAINS as a JSON array of domain strings.
    allowed_source_domains: list[str] = [
        "leg.colorado.gov",
        "cga.ct.gov",
        "ilga.gov",
        "njoag.gov",
    ]


settings = Settings()
