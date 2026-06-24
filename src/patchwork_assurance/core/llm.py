import json
import re
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from patchwork_assurance.core import obs
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
        start = time.perf_counter()
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=self._dump(messages),
            )
        except self._anthropic.AnthropicError as e:
            obs.log_llm_call(
                self._model, None, (time.perf_counter() - start) * 1000, surface="complete:error"
            )
            raise LLMError(str(e)) from e
        obs.log_llm_call(
            self._model, resp.usage, (time.perf_counter() - start) * 1000, surface="complete"
        )
        return next((b.text for b in resp.content if b.type == "text"), "")

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        start = time.perf_counter()
        try:
            resp = self._client.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=self._dump(messages),
                output_format=schema,
            )
        except self._anthropic.AnthropicError as e:
            obs.log_llm_call(
                self._model,
                None,
                (time.perf_counter() - start) * 1000,
                surface="complete_structured:error",
            )
            raise LLMError(str(e)) from e
        obs.log_llm_call(
            self._model,
            resp.usage,
            (time.perf_counter() - start) * 1000,
            surface="complete_structured",
        )
        return resp.parsed_output

    def stream(self, system, messages, max_tokens=16000):
        # Wraps setup AND mid-stream errors into LLMError. Note: for the SSE /chat route the
        # response has already started by the time tokens are pulled, so a mid-stream LLMError
        # cannot become a clean 502; the API generator catches it and ends the stream.
        start = time.perf_counter()
        final = None
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=self._dump(messages),
            ) as s:
                yield from s.text_stream
                final = s.get_final_message()  # usage is on the final message
        except self._anthropic.AnthropicError as e:
            obs.log_llm_call(
                self._model, None, (time.perf_counter() - start) * 1000, surface="stream:error"
            )
            raise LLMError(str(e)) from e
        finally:
            if final is not None:
                obs.log_llm_call(
                    self._model, final.usage, (time.perf_counter() - start) * 1000, surface="stream"
                )


class StubLLM:
    """Deterministic, offline, schema-valid output for tests/dev."""

    def __init__(self, text: str = "(stub)", structured: BaseModel | None = None) -> None:
        self._text = text
        self._structured = structured

    def complete(self, system, messages, max_tokens=16000) -> str:
        obs.log_llm_call("stub", None, 0.0, surface="complete")
        return self._text

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        obs.log_llm_call("stub", None, 0.0, surface="complete_structured")
        if self._structured is not None:
            return self._structured
        if schema is ComplianceMemo:
            # Default offline output must be a VALID, chrome-complete memo (invariant #4: the
            # disclaimer rides on every surface) so `make dev` renders a faithful memo with no key.
            return _default_memo()
        return _minimal(schema)

    def stream(self, system, messages, max_tokens=16000):
        obs.log_llm_call("stub", None, 0.0, surface="stream")
        yield from self._text.split()


def _openai_usage(usage) -> SimpleNamespace | None:
    """Adapt an OpenAI-shaped usage (prompt_tokens/completion_tokens) to the Anthropic-shaped
    attributes obs.log_llm_call reads. Cache fields are absent on OpenRouter, so they default to 0."""
    if usage is None:
        return None
    return SimpleNamespace(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


class OpenRouterLLM:
    """OpenAI-compatible provider via OpenRouter (Phase 8 interlude). Lets the app run on free / penny
    models without an Anthropic key — the budget play and the multi-provider-gateway learning rep.
    Seam 4: only this class and AnthropicLLM import a vendor SDK; both satisfy the same LLMClient
    Protocol, so the API/UI/eval call the same path regardless of provider.

    Cost note: pricing.RATES only knows the Anthropic models, so OpenRouter calls log `known_rate:false`
    and est_cost 0 — accurate for `:free` models. (A future add could map OpenRouter prices; not needed
    while we're on the free tier.)"""

    def __init__(
        self, model: str, api_key: str | None = None, base_url: str = "", client=None
    ) -> None:
        import openai  # dep; imported here so stub/anthropic users don't need it (lazy like AnthropicLLM)

        self._openai = openai  # for the SDK exception base when wrapping into LLMError
        self._model = model
        # `client` injection keeps the unit tests offline; production passes None and builds the real one.
        self._client = client or openai.OpenAI(
            api_key=api_key,
            base_url=base_url or "https://openrouter.ai/api/v1",
            default_headers={"X-Title": "Patchwork Assurance"},
        )

    def _msgs(self, system: str, messages: list[Msg]) -> list[dict]:
        return [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]

    def complete(self, system, messages, max_tokens=16000) -> str:
        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self._model, max_tokens=max_tokens, messages=self._msgs(system, messages)
            )
        except self._openai.OpenAIError as e:
            obs.log_llm_call(
                self._model, None, (time.perf_counter() - start) * 1000, surface="complete:error"
            )
            raise LLMError(str(e)) from e
        obs.log_llm_call(
            self._model,
            _openai_usage(resp.usage),
            (time.perf_counter() - start) * 1000,
            surface="complete",
        )
        return resp.choices[0].message.content or ""

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        # JSON-object mode + the schema in the system prompt + client-side validation — the broadest
        # path across OpenRouter's free models (strict json_schema needs additionalProperties:false /
        # all-required, which Pydantic schemas don't satisfy by default; a future upgrade).
        sys_with_schema = (
            f"{system}\n\nReturn ONLY a JSON object matching this schema "
            f"(no prose, no code fences):\n{json.dumps(schema.model_json_schema())}"
        )
        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=self._msgs(sys_with_schema, messages),
                response_format={"type": "json_object"},
            )
        except self._openai.OpenAIError as e:
            obs.log_llm_call(
                self._model,
                None,
                (time.perf_counter() - start) * 1000,
                surface="complete_structured:error",
            )
            raise LLMError(str(e)) from e
        obs.log_llm_call(
            self._model,
            _openai_usage(resp.usage),
            (time.perf_counter() - start) * 1000,
            surface="complete_structured",
        )
        content = resp.choices[0].message.content or ""
        try:
            return schema.model_validate_json(_strip_json_fence(content))
        except ValidationError as e:
            # A weak free model can return malformed/incomplete JSON — surface it as an LLMError
            # (the web layer maps to 502) rather than a raw ValidationError.
            raise LLMError(f"structured output did not match {schema.__name__}: {e}") from e

    def stream(self, system, messages, max_tokens=16000):
        start = time.perf_counter()
        final_usage = None
        errored = False
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=self._msgs(system, messages),
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                if getattr(chunk, "usage", None):  # final usage chunk (empty choices)
                    final_usage = chunk.usage
        except self._openai.OpenAIError as e:
            errored = True
            obs.log_llm_call(
                self._model, None, (time.perf_counter() - start) * 1000, surface="stream:error"
            )
            raise LLMError(str(e)) from e
        finally:
            if not errored:
                obs.log_llm_call(
                    self._model,
                    _openai_usage(final_usage),
                    (time.perf_counter() - start) * 1000,
                    surface="stream",
                )


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
    if settings.llm_provider == "openrouter":
        return OpenRouterLLM(model, settings.openrouter_api_key, settings.openrouter_base_url)
    return StubLLM()
