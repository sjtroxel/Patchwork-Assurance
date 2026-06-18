from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config from environment / .env. In dev the UI talks to localhost; in Phase 5
    the same code points at the deployed API by setting API_BASE_URL — no code change."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000"
    corpus_path: str = "corpus"
    chroma_path: str = ".chroma"


settings = Settings()
