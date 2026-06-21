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


settings = Settings()
