import json
import re
import threading
import time
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from patchwork_assurance.core import obs
from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    LawFinding,
    MemoObligation,
    Msg,
    ToolRunResult,
)
from patchwork_assurance.core.judge import JudgeVerdict
from patchwork_assurance.core.prompts import DISCLAIMER

T = TypeVar("T", bound=BaseModel)

# Bound on the agentic tool-use loop (§6) so a model that keeps calling tools can't spin forever.
_MAX_TOOL_ITERS = 6

# A tool dispatcher: given a tool name and its parsed input, run it and return a string result the
# model reads back. The retrieval tools live in core/router.py; this module stays provider-only.
ToolDispatch = Callable[[str, dict], str]


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
    def run_tools(
        self,
        system: str,
        messages: list[Msg],
        tools: list[dict],
        dispatch: ToolDispatch,
        max_tokens: int = 16000,
    ) -> ToolRunResult: ...


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

    def run_tools(self, system, messages, tools, dispatch, max_tokens=16000):
        # Manual agentic loop (Phase 8 §0): the intermediate turns carry content *blocks* (tool_use /
        # tool_result), which Msg/_dump can't model — so the loop manages raw message dicts here, inside
        # the provider. Public input is still system + list[Msg] + tools + a dispatcher. tool_choice
        # stays "auto" (forcing a tool would defeat measuring the model's routing judgment).
        convo: list[dict] = self._dump(messages)
        called: list[str] = []
        for _ in range(_MAX_TOOL_ITERS):
            start = time.perf_counter()
            try:
                resp = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=convo,
                    tools=tools,
                    tool_choice={"type": "auto"},
                )
            except self._anthropic.AnthropicError as e:
                obs.log_llm_call(
                    self._model,
                    None,
                    (time.perf_counter() - start) * 1000,
                    surface="run_tools:error",
                )
                raise LLMError(str(e)) from e
            obs.log_llm_call(
                self._model, resp.usage, (time.perf_counter() - start) * 1000, surface="run_tools"
            )
            if resp.stop_reason != "tool_use":
                text = next((b.text for b in resp.content if b.type == "text"), "")
                return ToolRunResult(text=text, tools_called=called)
            convo.append({"role": "assistant", "content": resp.content})
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    called.append(b.name)
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": b.id,
                            "content": dispatch(b.name, b.input),
                        }
                    )
            convo.append({"role": "user", "content": results})
        # Iteration budget spent without a final answer — surface what was called, no fabricated text.
        return ToolRunResult(text="", tools_called=called)


class StubLLM:
    """Deterministic, offline, schema-valid output for tests/dev."""

    def __init__(
        self,
        text: str = "(stub)",
        structured: BaseModel | None = None,
        tool_script: list | None = None,
        structured_by_schema: dict[type, object] | None = None,
    ) -> None:
        self._text = text
        self._structured = structured
        # Phase 12: drive a multi-call pipeline (N analysts -> LawFinding, reviewer -> JudgeVerdict)
        # deterministically offline. Maps a schema type to either a fixed instance (returned for every
        # call with that schema) or a list drained FIFO per call. Keyed by schema so interleaved
        # analyst/reviewer calls don't consume each other's scripted values. Falls back to `structured`
        # then the schema default, so existing single-value stubs are unchanged.
        self._structured_by_schema = structured_by_schema or {}
        self._lock = threading.Lock()  # analysts drain the queues from parallel threads
        # A scripted tool program for run_tools: a list of steps, each either a bare tool name or a
        # (name, input_dict) tuple. The stub "calls" each via dispatch (exercising the wiring) and
        # returns `text` as the final answer — deterministic, zero tokens. (Phase 8 §6.)
        self._tool_script = tool_script or []

    def complete(self, system, messages, max_tokens=16000) -> str:
        obs.log_llm_call("stub", None, 0.0, surface="complete")
        return self._text

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        obs.log_llm_call("stub", None, 0.0, surface="complete_structured")
        if schema in self._structured_by_schema:
            entry = self._structured_by_schema[schema]
            if isinstance(entry, list):
                with self._lock:  # parallel analysts drain the same queue
                    return entry.pop(0)
            # Return a COPY of a fixed value: parallel analysts mutate their finding in place
            # (analyze_law stamps ids), so handing them one shared instance would race. A real LLM
            # returns a fresh object per call, so this matches production.
            return entry.model_copy(deep=True) if isinstance(entry, BaseModel) else entry
        if self._structured is not None:
            return self._structured
        if schema is ComplianceMemo:
            # Default offline output must be a VALID, chrome-complete memo (invariant #4: the
            # disclaimer rides on every surface) so `make dev` renders a faithful memo with no key.
            return _default_memo()
        # Phase 12: valid defaults for the multi-agent schemas so the whole analyst->reviewer pipeline
        # runs offline on a bare stub too (the same `make dev`-with-no-key parity the memo has).
        if schema is LawFinding:
            return _default_finding()
        if schema is JudgeVerdict:
            return JudgeVerdict(grounded="yes", reason="(stub)")
        if schema is MemoObligation:
            return MemoObligation(
                text="(stub) A deployer provides the consumer notice that ADMT is in use.",
                citation="Colorado § 6-1-1704",
            )
        return _minimal(schema)

    def stream(self, system, messages, max_tokens=16000):
        obs.log_llm_call("stub", None, 0.0, surface="stream")
        yield from self._text.split()

    def run_tools(self, system, messages, tools, dispatch, max_tokens=16000):
        obs.log_llm_call("stub", None, 0.0, surface="run_tools")
        called: list[str] = []
        for step in self._tool_script:
            name, args = step if isinstance(step, tuple) else (step, {})
            dispatch(name, args)  # drive the real dispatcher so the wiring is what gets tested
            called.append(name)
        return ToolRunResult(text=self._text, tools_called=called)


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
    # Weak/free models sometimes emit stray control chars inside the JSON, which break strict parsing.
    # Drop them (keep \t \n \r, which JSON allows in formatting).
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return s.strip()


def _retry_backoff(attempt: int) -> float:
    """Exponential backoff in seconds (2, 4, 8, ... capped at 30) for rate-limited retries."""
    return min(2.0 * (2**attempt), 30.0)


class OpenRouterLLM:
    """OpenAI-compatible provider via OpenRouter (Phase 8 interlude). Lets the app run on free / penny
    models without an Anthropic key — the budget play and the multi-provider-gateway learning rep.
    Seam 4: only this class and AnthropicLLM import a vendor SDK; both satisfy the same LLMClient
    Protocol, so the API/UI/eval call the same path regardless of provider.

    Cost note: pricing.RATES only knows the Anthropic models, so OpenRouter calls log `known_rate:false`
    and est_cost 0 — accurate for `:free` models. (A future add could map OpenRouter prices; not needed
    while we're on the free tier.)"""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "",
        client=None,
        max_retries: int = 2,
        sleep=time.sleep,
    ) -> None:
        import openai  # dep; imported here so stub/anthropic users don't need it (lazy like AnthropicLLM)

        self._openai = openai  # for the SDK exception base when wrapping into LLMError
        self._model = model
        # Free models are flaky for structured output; complete_structured retries up to this many
        # times. `sleep` is injectable so tests exercise the backoff without real delay.
        self._max_retries = max_retries
        self._sleep = sleep
        # `client` injection keeps the unit tests offline; production passes None and builds the real one.
        self._client = client or openai.OpenAI(
            api_key=api_key,
            base_url=base_url or "https://openrouter.ai/api/v1",
            default_headers={"X-Title": "Patchwork Assurance"},
        )

    def _is_rate_limit(self, e: Exception) -> bool:
        """True for an upstream 429. Free models on OpenRouter return these under load; a bounded
        backoff-retry recovers from the transient ones."""
        return isinstance(e, self._openai.RateLimitError) or getattr(e, "status_code", None) == 429

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
        #
        # Free models are unreliable here: they intermittently emit empty, truncated, or malformed
        # JSON (json_object mode is not always grammar-enforced upstream) or 429 under load. So make
        # a bounded number of attempts — regenerate on a parse/validation failure, back off on a
        # rate limit — and only surface the last error once the budget is spent.
        sys_with_schema = (
            f"{system}\n\nReturn ONLY a JSON object matching this schema "
            f"(no prose, no code fences):\n{json.dumps(schema.model_json_schema())}"
        )
        msgs = self._msgs(sys_with_schema, messages)
        last_err: LLMError | None = None
        for attempt in range(self._max_retries + 1):
            start = time.perf_counter()
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=msgs,
                    response_format={"type": "json_object"},
                )
            except self._openai.OpenAIError as e:
                obs.log_llm_call(
                    self._model,
                    None,
                    (time.perf_counter() - start) * 1000,
                    surface="complete_structured:error",
                )
                last_err = LLMError(str(e))
                # Back off and retry a transient rate limit; any other provider error is not
                # something a retry fixes, so surface it immediately.
                if self._is_rate_limit(e) and attempt < self._max_retries:
                    self._sleep(_retry_backoff(attempt))
                    continue
                raise last_err from e
            obs.log_llm_call(
                self._model,
                _openai_usage(resp.usage),
                (time.perf_counter() - start) * 1000,
                surface="complete_structured",
            )
            content = resp.choices[0].message.content or ""
            try:
                # json.loads(strict=False) tolerates literal control chars (e.g. unescaped newlines)
                # INSIDE string values — weak free models emit those constantly, and Pydantic's
                # strict JSON parser rejects them ("control character found while parsing a string").
                # Parse leniently, then validate the dict. (Strong models hit the same parser; this
                # is a parser fix, not a model-quality fix.)
                data = json.loads(_strip_json_fence(content), strict=False)
                return schema.model_validate(data)
            except (ValidationError, json.JSONDecodeError) as e:
                # Empty / truncated / malformed JSON — a weak free model often succeeds on a fresh
                # attempt, so regenerate. The final failure surfaces as LLMError (web layer → 502).
                last_err = LLMError(f"structured output did not match {schema.__name__}: {e}")
                if attempt < self._max_retries:
                    continue
                raise last_err from e
        raise last_err  # pragma: no cover — the loop always returns or raises above

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

    def run_tools(self, system, messages, tools, dispatch, max_tokens=16000):
        # Same manual loop as AnthropicLLM, in OpenAI/OpenRouter shape: tools and tool-call/tool-result
        # messages use the OpenAI schema, so the Anthropic-shaped `tools` are converted once up front.
        convo: list[dict] = self._msgs(system, messages)
        oa_tools = [_to_openai_tool(t) for t in tools]
        called: list[str] = []
        for _ in range(_MAX_TOOL_ITERS):
            start = time.perf_counter()
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=convo,
                    tools=oa_tools,
                    tool_choice="auto",
                )
            except self._openai.OpenAIError as e:
                obs.log_llm_call(
                    self._model,
                    None,
                    (time.perf_counter() - start) * 1000,
                    surface="run_tools:error",
                )
                raise LLMError(str(e)) from e
            obs.log_llm_call(
                self._model,
                _openai_usage(resp.usage),
                (time.perf_counter() - start) * 1000,
                surface="run_tools",
            )
            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None)
            if not tool_calls:
                return ToolRunResult(text=msg.content or "", tools_called=called)
            convo.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                called.append(tc.function.name)
                args = json.loads(tc.function.arguments or "{}")
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": dispatch(tc.function.name, args),
                    }
                )
        return ToolRunResult(text="", tools_called=called)


def _to_openai_tool(tool: dict) -> dict:
    """Anthropic tool shape ({name, description, input_schema}) → OpenAI function-tool shape."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


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


def _default_finding() -> LawFinding:
    """A valid stub LawFinding (flagged as stub) so the Phase 12 analyst runs offline with no key."""
    return LawFinding(
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
    )


def _minimal(schema):
    """Last-resort minimal instance for schemas other than the ones defaulted above."""
    return schema.model_construct()


def build_llm(settings, model: str) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(model, settings.anthropic_api_key)
    if settings.llm_provider == "openrouter":
        return OpenRouterLLM(model, settings.openrouter_api_key, settings.openrouter_base_url)
    return StubLLM()
