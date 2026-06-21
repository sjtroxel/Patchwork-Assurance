from collections.abc import Iterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    LawFinding,
    MemoObligation,
    Msg,
)
from patchwork_assurance.core.prompts import DISCLAIMER

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Provider-agnostic LLM failure. The web layer maps this to a 502 without importing any
    vendor SDK — Seam 4 keeps all provider knowledge inside this module."""


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[Msg], max_tokens: int = 16000) -> str: ...
    def complete_structured(
        self, system: str, messages: list[Msg], schema: type[T], max_tokens: int = 16000
    ) -> T: ...
    def stream(
        self, system: str, messages: list[Msg], max_tokens: int = 16000
    ) -> Iterator[str]: ...


class AnthropicLLM:
    """Wraps the official `anthropic` SDK. Seam 4 — only this file imports anthropic."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        import anthropic

        self._anthropic = anthropic  # kept to reference the SDK's exception types when wrapping
        self._model = model
        self._client = anthropic.Anthropic(api_key=api_key)  # api_key=None → reads env

    def _dump(self, messages: list[Msg]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def complete(self, system, messages, max_tokens=16000) -> str:
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=self._dump(messages),
            )
        except self._anthropic.AnthropicError as e:
            raise LLMError(str(e)) from e
        return next((b.text for b in resp.content if b.type == "text"), "")

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        try:
            resp = self._client.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=self._dump(messages),
                output_format=schema,
            )
        except self._anthropic.AnthropicError as e:
            raise LLMError(str(e)) from e
        return resp.parsed_output

    def stream(self, system, messages, max_tokens=16000):
        # Wraps setup AND mid-stream errors into LLMError. Note: for the SSE /chat route the
        # response has already started by the time tokens are pulled, so a mid-stream LLMError
        # cannot become a clean 502; the API generator catches it and ends the stream.
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=self._dump(messages),
            ) as s:
                yield from s.text_stream
        except self._anthropic.AnthropicError as e:
            raise LLMError(str(e)) from e


class StubLLM:
    """Deterministic, offline, schema-valid output for tests/dev."""

    def __init__(self, text: str = "(stub)", structured: BaseModel | None = None) -> None:
        self._text = text
        self._structured = structured

    def complete(self, system, messages, max_tokens=16000) -> str:
        return self._text

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        if self._structured is not None:
            return self._structured
        if schema is ComplianceMemo:
            # Default offline output must be a VALID, chrome-complete memo (invariant #4: the
            # disclaimer rides on every surface) so `make dev` renders a faithful memo with no key.
            return _default_memo()
        return _minimal(schema)

    def stream(self, system, messages, max_tokens=16000):
        yield from self._text.split()


def _default_memo() -> ComplianceMemo:
    """A realistic, valid stub memo: flagged as stub output, carrying the real disclaimer."""
    return ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co-sb26-189",
                short_name="CO SB 26-189",
                in_scope="uncertain",
                why="Stub response. Set LLM_PROVIDER=anthropic for a grounded, retrieved analysis.",
                obligations=[
                    MemoObligation(
                        text="(stub) A deployer provides the consumer notice that ADMT is in use.",
                        citation="Colorado § 6-1-1704",
                    )
                ],
                effective_dates=["2027-01-01"],
            )
        ],
        disclaimer=DISCLAIMER,
    )


def _minimal(schema):
    """Last-resort minimal instance for schemas other than ComplianceMemo (none exist in v1)."""
    return schema.model_construct()


def build_llm(settings, model: str) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(model, settings.anthropic_api_key)
    return StubLLM()
