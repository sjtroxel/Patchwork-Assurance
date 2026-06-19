from collections.abc import Iterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

from patchwork_assurance.core.contracts import Msg

T = TypeVar("T", bound=BaseModel)


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

        self._model = model
        self._client = anthropic.Anthropic(api_key=api_key)  # api_key=None → reads env

    def _dump(self, messages: list[Msg]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def complete(self, system, messages, max_tokens=16000) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=self._dump(messages),
        )
        return next((b.text for b in resp.content if b.type == "text"), "")

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        resp = self._client.messages.parse(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=self._dump(messages),
            output_format=schema,
        )
        return resp.parsed_output

    def stream(self, system, messages, max_tokens=16000):
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=self._dump(messages),
        ) as s:
            yield from s.text_stream


class StubLLM:
    """Deterministic, offline, schema-valid output for tests/dev."""

    def __init__(self, text: str = "(stub)", structured: BaseModel | None = None) -> None:
        self._text = text
        self._structured = structured

    def complete(self, system, messages, max_tokens=16000) -> str:
        return self._text

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        return self._structured if self._structured is not None else _minimal(schema)

    def stream(self, system, messages, max_tokens=16000):
        yield from self._text.split()


def _minimal(schema):
    """Best-effort minimal valid instance. For ComplianceMemo, pass explicit structured= instead."""
    return schema.model_construct()


def build_llm(settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(settings.generation_model, settings.anthropic_api_key)
    return StubLLM()
