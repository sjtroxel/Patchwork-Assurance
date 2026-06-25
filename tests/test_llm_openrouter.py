"""core.llm.OpenRouterLLM — the OpenAI-compatible provider (Phase 8 interlude).

All offline: a fake OpenAI client is injected, so no network and no key. Proves the WIRING
(message shaping, JSON-object structured parsing, streaming, error wrapping, usage adaptation).
Whether a real free model returns good output is the live check, run against OpenRouter by hand."""

from types import SimpleNamespace

import openai
import pytest
from pydantic import BaseModel

from patchwork_assurance.config import Settings
from patchwork_assurance.core.contracts import Msg
from patchwork_assurance.core.llm import LLMError, OpenRouterLLM, build_llm


class _FakeCompletions:
    def __init__(self, content="(ok)", usage=None, stream_chunks=None, error=None):
        self._content = content
        self._usage = usage or SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        self._stream_chunks = stream_chunks or []
        self._error = error

    def create(self, **kwargs):
        if self._error is not None:
            raise self._error
        if kwargs.get("stream"):
            return iter(self._stream_chunks)
        msg = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=self._usage)


def _client(**kw):
    return SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions(**kw)))


def _chunk(text=None, usage=None):
    choices = [SimpleNamespace(delta=SimpleNamespace(content=text))] if text is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


class _SeqCompletions:
    """A create() that walks a list of actions, one per call: a str is returned as message content,
    an Exception is raised. The last action repeats if called past the end. Records the call count."""

    def __init__(self, actions, usage=None):
        self._actions = list(actions)
        self._usage = usage or SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        self.calls = 0

    def create(self, **kwargs):
        action = self._actions[min(self.calls, len(self._actions) - 1)]
        self.calls += 1
        if isinstance(action, Exception):
            raise action
        msg = SimpleNamespace(content=action)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=self._usage)


class _RateLimited(openai.OpenAIError):
    """An OpenAIError that _is_rate_limit() recognizes as a 429 (without constructing the SDK's
    RateLimitError, which needs an httpx response)."""

    status_code = 429


def _seq_llm(actions, max_retries=2):
    """An OpenRouterLLM over a scripted client, with backoff sleeps recorded instead of slept."""
    sleeps = []
    comp = _SeqCompletions(actions)
    client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    llm = OpenRouterLLM("m:free", client=client, max_retries=max_retries, sleep=sleeps.append)
    return llm, comp, sleeps


class _Mini(BaseModel):
    name: str
    n: int


def _llm(**kw):
    return OpenRouterLLM("deepseek/deepseek-chat:free", client=_client(**kw))


# --- complete --------------------------------------------------------------------------------------


def test_complete_returns_text():
    llm = _llm(content="hi there")
    assert llm.complete("sys", [Msg(role="user", content="q")]) == "hi there"


def test_complete_wraps_provider_error():
    llm = _llm(error=openai.OpenAIError("boom"))
    with pytest.raises(LLMError):
        llm.complete("sys", [Msg(role="user", content="q")])


# --- complete_structured ---------------------------------------------------------------------------


def test_structured_parses_json_object():
    llm = _llm(content='{"name": "x", "n": 3}')
    out = llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert out.name == "x" and out.n == 3


def test_structured_strips_code_fence():
    llm = _llm(content='```json\n{"name": "y", "n": 7}\n```')
    out = llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert out.n == 7


def test_structured_invalid_json_raises_llmerror():
    llm = _llm(content="this is not json")
    with pytest.raises(LLMError):
        llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)


def test_structured_tolerates_literal_control_chars_in_strings():
    # Weak free models emit raw (unescaped) newlines INSIDE string values, which Pydantic's strict
    # JSON parser rejects ("control character found while parsing a string"). The lenient parse path
    # must accept it and preserve the newline as content. Regression for the Phase 8 judged-tier bug.
    llm = _llm(content='{"name": "line one\nline two", "n": 3}')
    out = llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert out.name == "line one\nline two" and out.n == 3


# --- complete_structured: retry loop ---------------------------------------------------------------


def test_structured_retries_after_malformed_then_succeeds():
    # A free model's first body is malformed (mismatched quotes, as seen live); the retry is valid.
    good = '{"name": "ok", "n": 2}'
    llm, comp, sleeps = _seq_llm(['{"name\': "x", "n\': 1}', good])
    out = llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert out.name == "ok" and out.n == 2
    assert comp.calls == 2  # regenerated once
    assert sleeps == []  # no backoff for a parse failure, only for a rate limit


def test_structured_backs_off_and_retries_on_rate_limit():
    good = '{"name": "ok", "n": 5}'
    llm, comp, sleeps = _seq_llm([_RateLimited("429 busy"), good])
    out = llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert out.n == 5
    assert comp.calls == 2
    assert sleeps == [2.0]  # one backoff before the retry


def test_structured_raises_after_exhausting_retries():
    llm, comp, sleeps = _seq_llm(["still not json"], max_retries=2)
    with pytest.raises(LLMError):
        llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert comp.calls == 3  # 1 initial + 2 retries


def test_structured_non_rate_limit_error_does_not_retry():
    # A non-429 provider error (e.g. auth) is not retry-fixable — surface it on the first attempt.
    llm, comp, sleeps = _seq_llm([openai.OpenAIError("bad key")])
    with pytest.raises(LLMError):
        llm.complete_structured("sys", [Msg(role="user", content="q")], _Mini)
    assert comp.calls == 1 and sleeps == []


# --- run_tools: the agentic tool-use loop (Phase 8 batch 4) ----------------------------------------


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class _ToolLoopCompletions:
    """create() returns a tool-call message on the first call, then a plain answer on the second —
    driving run_tools through one tool round-trip."""

    def __init__(self, steps):
        self._steps = steps
        self.calls = 0

    def create(self, **kwargs):
        msg = self._steps[min(self.calls, len(self._steps) - 1)]
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg)],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
        )


def test_run_tools_executes_tool_then_answers():
    steps = [
        SimpleNamespace(  # turn 1: model asks for a tool
            content=None,
            tool_calls=[_tool_call("c1", "search_corpus", '{"query": "notice"}')],
        ),
        SimpleNamespace(content="grounded answer", tool_calls=None),  # turn 2: final answer
    ]
    comp = _ToolLoopCompletions(steps)
    client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    llm = OpenRouterLLM("m:free", client=client)

    dispatched = []

    def dispatch(name, args):
        dispatched.append((name, args))
        return "tool output"

    tools = [{"name": "search_corpus", "description": "d", "input_schema": {"type": "object"}}]
    result = llm.run_tools("sys", [Msg(role="user", content="q")], tools, dispatch)

    assert result.text == "grounded answer"
    assert result.tools_called == ["search_corpus"]
    assert dispatched == [("search_corpus", {"query": "notice"})]
    assert comp.calls == 2


def test_run_tools_answers_directly_when_no_tool_call():
    steps = [SimpleNamespace(content="direct", tool_calls=None)]
    comp = _ToolLoopCompletions(steps)
    client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    llm = OpenRouterLLM("m:free", client=client)
    result = llm.run_tools("sys", [Msg(role="user", content="q")], [], lambda n, a: "")
    assert result.text == "direct" and result.tools_called == [] and comp.calls == 1


# --- stream ----------------------------------------------------------------------------------------


def test_stream_yields_text_and_ignores_usage_chunk():
    chunks = [
        _chunk("Hello "),
        _chunk("world"),
        _chunk(usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2)),  # final usage chunk
    ]
    llm = _llm(stream_chunks=chunks)
    assert "".join(llm.stream("sys", [Msg(role="user", content="q")])) == "Hello world"


# --- build_llm routing -----------------------------------------------------------------------------


def test_build_llm_routes_to_openrouter():
    s = Settings(llm_provider="openrouter", openrouter_api_key="x")
    assert isinstance(build_llm(s, "deepseek/deepseek-chat:free"), OpenRouterLLM)
