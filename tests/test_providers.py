"""Providers without network: fake SDK clients, canned CLI output, retry logic, cache."""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

from mmarena.agents.base import InfraError
from mmarena.cache import CachedProvider, ResponseCache
from mmarena.providers.anthropic import AnthropicProvider, estimate_cost
from mmarena.providers.base import (
    Completion,
    TransientError,
    classify_sdk_error,
    with_retries,
)
from mmarena.providers.claude_cli import ClaudeCLIProvider, parse_cli_output
from mmarena.providers.openai import OpenAIProvider
from mmarena.providers.scripted import ScriptedProvider

# ----------------------------------------------------------------------------- fake SDK errors


class APIError(Exception):
    pass


class APIStatusError(APIError):
    def __init__(self, status_code: int):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class APIConnectionError(APIError):
    pass


def test_classify():
    assert isinstance(classify_sdk_error(APIStatusError(429), "x"), TransientError)
    assert isinstance(classify_sdk_error(APIStatusError(529), "x"), TransientError)
    assert isinstance(classify_sdk_error(APIStatusError(500), "x"), TransientError)
    assert isinstance(classify_sdk_error(APIConnectionError("reset"), "x"), TransientError)
    for code in (400, 401, 403, 404):
        assert isinstance(classify_sdk_error(APIStatusError(code), "x"), InfraError)


def test_with_retries_backoff():
    sleeps: list[float] = []
    n = {"calls": 0}

    def flaky():
        n["calls"] += 1
        if n["calls"] < 3:
            raise TransientError("busy")
        return "ok"

    assert with_retries(flaky, attempts=4, base_delay=1.0, sleep=sleeps.append) == "ok"
    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] <= 1.0 and 1.0 <= sleeps[1] <= 2.0


def test_with_retries_gives_up():
    sleeps: list[float] = []

    def busy():
        raise TransientError("busy")

    with pytest.raises(InfraError, match="gave up after 3"):
        with_retries(busy, attempts=3, sleep=sleeps.append)
    assert len(sleeps) == 2


def test_with_retries_infra_is_immediate():
    calls = []

    def auth():
        calls.append(1)
        raise InfraError("bad key")

    with pytest.raises(InfraError, match="bad key"):
        with_retries(auth, attempts=4, sleep=lambda s: None)
    assert len(calls) == 1


# ----------------------------------------------------------------------------- anthropic


class _FakeMessages:
    def __init__(self, errors=()):
        self.errors = list(errors)
        self.requests: list[dict] = []

    def create(self, **req):
        self.requests.append(req)
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text='{"bid": 1, "ask": 2}'),
            ],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                cache_read_input_tokens=1000,
                cache_creation_input_tokens=0,
            ),
            model="claude-sonnet-5-5",
            stop_reason="end_turn",
        )


def test_anthropic_request_shape(monkeypatch):
    msgs = _FakeMessages()
    prov = AnthropicProvider(
        "claude-sonnet-5-5", effort="low", client=SimpleNamespace(messages=msgs)
    )
    comp = prov.complete("SYS", ["STATIC", "DYNAMIC"], max_tokens=777)
    req = msgs.requests[0]
    assert req["model"] == "claude-sonnet-5-5"
    assert req["max_tokens"] == 777
    assert req["output_config"] == {"effort": "low"}
    assert "thinking" not in req and "temperature" not in req
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    content = req["messages"][0]["content"]
    assert [b["text"] for b in content] == ["STATIC", "DYNAMIC"]
    assert "cache_control" in content[0] and "cache_control" not in content[1]
    assert comp.text == '{"bid": 1, "ask": 2}'
    assert comp.usage == {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 1000,
        "cache_write_tokens": 0,
    }
    assert comp.cost_usd == pytest.approx((100 * 2 + 50 * 10 + 1000 * 0.1) / 1e6)


def test_anthropic_no_effort_omits_output_config():
    msgs = _FakeMessages()
    AnthropicProvider("claude-opus-5-5", client=SimpleNamespace(messages=msgs)).complete(
        "S", "U", max_tokens=10
    )
    assert "output_config" not in msgs.requests[0]


def test_anthropic_retries_then_infra(monkeypatch):
    monkeypatch.setattr("mmarena.providers.base.time.sleep", lambda s: None)
    msgs = _FakeMessages(errors=[APIStatusError(529), APIStatusError(429)])
    prov = AnthropicProvider("claude-haiku-5-5", client=SimpleNamespace(messages=msgs))
    assert prov.complete("S", "U", max_tokens=10).text
    assert len(msgs.requests) == 3

    msgs = _FakeMessages(errors=[APIStatusError(401)])
    prov = AnthropicProvider("claude-haiku-5-5", client=SimpleNamespace(messages=msgs))
    with pytest.raises(InfraError):
        prov.complete("S", "U", max_tokens=10)
    assert len(msgs.requests) == 1


def test_anthropic_missing_key(monkeypatch):
    monkeypatch.delenv("MMARENA_TEST_NO_KEY", raising=False)
    prov = AnthropicProvider("claude-haiku-5-5", api_key_env="MMARENA_TEST_NO_KEY")
    with pytest.raises(InfraError):
        prov.complete("S", "U", max_tokens=10)


def test_anthropic_bad_effort():
    with pytest.raises(ValueError):
        AnthropicProvider("claude-opus-5-5", effort="extreme")


def test_estimate_cost():
    assert estimate_cost("claude-haiku-4-5-20251001", {"input_tokens": 1_000_000}) == 1.0
    assert estimate_cost("some-other-model", {"input_tokens": 5}) is None


# ----------------------------------------------------------------------------- openai


class _FakeCompletions:
    def __init__(self):
        self.requests: list[dict] = []

    def create(self, **req):
        self.requests.append(req)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"bid": 3, "ask": 4}'), finish_reason="stop"
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=20,
                completion_tokens=7,
                prompt_tokens_details=SimpleNamespace(cached_tokens=5),
                completion_tokens_details=None,
            ),
            model="llama3.1",
        )


def _openai_client(comps):
    return SimpleNamespace(chat=SimpleNamespace(completions=comps))


def test_openai_request_shape():
    comps = _FakeCompletions()
    prov = OpenAIProvider("gpt-5.1", effort="high", client=_openai_client(comps))
    comp = prov.complete("SYS", ["A", "B"], max_tokens=99)
    req = comps.requests[0]
    assert req["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "A\n\nB"},
    ]
    assert req["max_completion_tokens"] == 99
    assert req["reasoning_effort"] == "high"
    assert comp.text == '{"bid": 3, "ask": 4}'
    assert comp.usage == {"input_tokens": 20, "output_tokens": 7, "cache_read_tokens": 5}
    assert comp.stop_reason == "stop"


def test_openai_compatible_server():
    comps = _FakeCompletions()
    prov = OpenAIProvider(
        "llama3.1", base_url="http://localhost:11434/v1", client=_openai_client(comps)
    )
    prov.complete("S", "U", max_tokens=5)
    assert comps.requests[0]["max_tokens"] == 5
    assert "reasoning_effort" not in comps.requests[0]
    assert OpenAIProvider("x", base_url="https://openrouter.ai/api/v1").api_key_env == (
        "OPENROUTER_API_KEY"
    )


# ----------------------------------------------------------------------------- claude-cli


def _cli_json(**over) -> str:
    obj = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": 'ok {"bid": 1, "ask": 2}',
        "total_cost_usd": 0.0011,
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 597,
            "output_tokens": 108,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "output_tokens_details": {"thinking_tokens": 79},
        },
        "modelUsage": {"claude-haiku-4-5-20251001": {"costUSD": 0.0011}},
        "api_error_status": None,
    }
    obj.update(over)
    return json.dumps(obj)


def test_cli_parse_success():
    comp = parse_cli_output("log line\n" + _cli_json(), "", 0)
    assert comp.text == 'ok {"bid": 1, "ask": 2}'
    # List price of the tokens, not Claude Code's own figure.
    assert comp.cost_usd == pytest.approx((597 * 1.0 + 108 * 5.0) / 1e6)
    assert comp.model == "claude-haiku-4-5-20251001"
    assert comp.usage["input_tokens"] == 597
    assert comp.usage["reasoning_tokens"] == 79


@pytest.mark.parametrize(
    "stdout,stderr,code,exc",
    [
        ("", "Error: Not logged in. Please run /login", 1, InfraError),
        ("", "something odd", 1, TransientError),
        (
            _cli_json(is_error=True, api_error_status=429, result="Rate limited"),
            "",
            1,
            TransientError,
        ),
        (
            _cli_json(is_error=True, api_error_status=529, result="Overloaded"),
            "",
            1,
            TransientError,
        ),
        (
            _cli_json(is_error=True, api_error_status=401, result="Invalid API key"),
            "",
            1,
            InfraError,
        ),
        (
            _cli_json(is_error=True, api_error_status=404, result="model not found"),
            "",
            1,
            InfraError,
        ),
        (_cli_json(is_error=True, result="Invalid API key · Please run /login"), "", 1, InfraError),
    ],
)
def test_cli_parse_failures(stdout, stderr, code, exc):
    with pytest.raises(exc):
        parse_cli_output(stdout, stderr, code)


def test_cli_argv():
    prov = ClaudeCLIProvider("haiku", effort="low")
    argv = prov.argv("claude", "/tmp/sys.md")
    joined = " ".join(argv)
    for flag in (
        "-p",
        "--output-format json",
        "--model haiku",
        "--system-prompt-file /tmp/sys.md",
        "--strict-mcp-config",
        "--max-turns 1",
        "--effort low",
        "--safe-mode",
    ):
        assert flag in joined
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""


def test_cli_missing_executable():
    prov = ClaudeCLIProvider("haiku", executable="definitely-not-a-real-claude-binary")
    with pytest.raises(InfraError, match="not found"):
        prov.complete("S", "U", max_tokens=10)


# ----------------------------------------------------------------------------- cache


def test_cache_thread_safe(tmp_path):
    cache = ResponseCache(tmp_path)
    prov = CachedProvider(ScriptedProvider("same"), cache)
    out: list[Completion] = []
    lock = threading.Lock()

    def work():
        for _ in range(10):
            c = prov.complete("S", "U", max_tokens=5)
            with lock:
                out.append(c)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(out) == 80
    files = [p for p in tmp_path.rglob("*.json") if not p.name.startswith(".tmp")]
    assert len(files) == 80  # one sample per occurrence
    assert not list(tmp_path.rglob(".tmp-*"))


def test_cache_key_depends_on_options():
    k1 = ResponseCache.base_key("p", "m", {"effort": "low"}, 10, "s", "u")
    k2 = ResponseCache.base_key("p", "m", {"effort": "high"}, 10, "s", "u")
    k3 = ResponseCache.base_key("p", "m", {"effort": "low"}, 11, "s", "u")
    assert len({k1, k2, k3}) == 3


def test_cache_does_not_store_failures(tmp_path):
    class Failing:
        name, model, options = "f", "m", {}

        def complete(self, system, user, *, max_tokens):
            raise InfraError("down")

    prov = CachedProvider(Failing(), ResponseCache(tmp_path))
    with pytest.raises(InfraError):
        prov.complete("S", "U", max_tokens=5)
    assert not list(tmp_path.rglob("*.json"))


def test_cli_cost_falls_back_to_reported_for_unknown_model():
    out = _cli_json(modelUsage={"some-new-model": {"costUSD": 0.0011}})
    assert parse_cli_output(out, "", 0).cost_usd == 0.0011


def test_cli_records_one_hour_cache_writes():
    usage = {
        "input_tokens": 2,
        "output_tokens": 100,
        "cache_read_input_tokens": 500,
        "cache_creation_input_tokens": 1000,
        "cache_creation": {"ephemeral_1h_input_tokens": 1000, "ephemeral_5m_input_tokens": 0},
    }
    out = _cli_json(usage=usage, modelUsage={"claude-opus-5-5": {}})
    comp = parse_cli_output(out, "", 0)
    assert comp.usage["cache_write_1h_tokens"] == 1000
    assert comp.cost_usd == pytest.approx((2 * 4 + 100 * 20 + 500 * 0.2 + 1000 * 8) / 1e6)


def test_cli_attributes_reply_to_requested_model_not_auxiliary_call():
    # Claude Code 2.1.296 adds a small Haiku call; modelUsage lists it first.
    usage = {"input_tokens": 2, "output_tokens": 300, "cache_read_input_tokens": 1220}
    model_usage = {
        "claude-haiku-5-5": {"inputTokens": 1171, "outputTokens": 21},
        "claude-opus-5-5": {"inputTokens": 2, "outputTokens": 300, "cacheReadInputTokens": 1220},
    }
    comp = parse_cli_output(
        _cli_json(usage=usage, modelUsage=model_usage), "", 0, "claude-opus-5-5"
    )
    assert comp.model == "claude-opus-5-5"
    assert comp.usage["aux_input_tokens"] == 1171
    assert comp.usage["aux_output_tokens"] == 21
    main = (2 * 4 + 300 * 20 + 1220 * 0.2) / 1e6
    aux = (1171 * 0.1 + 21 * 0.5) / 1e6
    assert comp.cost_usd == pytest.approx(main + aux)


def test_cli_auxiliary_call_on_the_same_model_is_split_out():
    usage = {"input_tokens": 2, "output_tokens": 300}
    model_usage = {"claude-haiku-5-5": {"inputTokens": 1173, "outputTokens": 321}}
    comp = parse_cli_output(
        _cli_json(usage=usage, modelUsage=model_usage), "", 0, "claude-haiku-5-5"
    )
    assert comp.model == "claude-haiku-5-5"
    assert comp.usage["output_tokens"] == 300
    assert (comp.usage["aux_input_tokens"], comp.usage["aux_output_tokens"]) == (1171, 21)
