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
