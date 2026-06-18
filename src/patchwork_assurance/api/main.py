from fastapi import FastAPI
from pydantic import BaseModel

from patchwork_assurance.core.health import core_status


class HealthResponse(BaseModel):
    """Typed response contract. Overkill for a health check on purpose — it sets the
    pattern that every endpoint declares its shape (Pydantic), which the memo and the
    streaming chat lean on in Phase 3."""

    api: str
    core: dict


app = FastAPI(title="Patchwork Assurance API")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # The API imports core. core never imports the API. The arrow points one way.
    return HealthResponse(api="ok", core=core_status())
