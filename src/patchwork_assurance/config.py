from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config from environment / .env. In dev the UI talks to localhost; in Phase 5
    the same code points at the deployed API by setting API_BASE_URL — no code change."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000"
    corpus_path: str = "corpus"
    chroma_path: str = ".chroma"
    llm_provider: str = "stub"  # "stub" | "anthropic"
    # Two-model split (Phase 5): chat gets fast/cheap Haiku (unlimited); the memo gets Sonnet's higher
    # reasoning (rate-limited, see api memo_rate_limit). Re-verify IDs/pricing at build (standing rule).
    chat_model: str = "claude-haiku-4-5"
    memo_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str | None = None  # read from env ANTHROPIC_API_KEY; never commit
    top_k: int = 5
    max_tokens: int = 16000
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


settings = Settings()
