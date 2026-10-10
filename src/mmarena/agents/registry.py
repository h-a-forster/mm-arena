"""Build agents from short spec strings.

Spec grammar::

    SPEC := BASELINE | PROVIDER ":" MODEL ["@" BASE_URL] ["@" EFFORT]

- ``BASELINE``: one of ``bayes``, ``bayes-noflow``, ``bayes-mean``, ``bayes-lookahead``,
  ``glosten-milgrom``, ``static``, ``random``.
- ``anthropic:MODEL`` - Anthropic API (``ANTHROPIC_API_KEY``), e.g. ``anthropic:claude-sonnet-5-5``.
- ``openai:MODEL`` - OpenAI API (``OPENAI_API_KEY``), e.g. ``openai:gpt-5.1``.
- ``openai:MODEL@BASE_URL`` - any OpenAI-compatible server, e.g.
  ``openai:llama3.1@http://localhost:11434/v1`` (Ollama). OpenRouter URLs read
  ``OPENROUTER_API_KEY``; set ``api_key_env`` to use another variable.
- ``claude-cli:MODEL`` - Claude Code in print mode with the local login, e.g. ``claude-cli:haiku``.
- ``scripted:TEXT`` - offline fake model that always replies ``TEXT``, e.g.
  ``scripted:{"bid": 10, "ask": 12}``. No effort suffix is parsed.
- A trailing ``@EFFORT`` (``low``, ``medium``, ``high``, ``xhigh``, ``max``) sets reasoning effort,
  e.g. ``claude-cli:sonnet@low`` or ``openai:qwen3@http://localhost:8000/v1@high``. The
  ``effort`` option does the same.

The agent name defaults to the canonical spec: ``PROVIDER:MODEL[@BASE_URL][@EFFORT]``, so an
effort set through options shows up in the name as it would in the spec. ``name`` overrides it.

Options (keyword arguments of ``make_agent_factory``; LLM options are ignored for baselines):
``max_tokens`` (default 8192; not supported by claude-cli), ``effort``, ``cache`` (True/False or a
directory; default True, ``.mmarena-cache/``), ``name``, ``repair_attempts`` (default 1),
``timeout`` (seconds per call, default 600), ``retries`` (attempts on transient errors,
default 4), ``api_key_env`` and ``base_url`` (anthropic/openai), ``executable`` (claude-cli).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mmarena.agents.base import Agent
from mmarena.agents.baselines import BASELINES
from mmarena.agents.llm import LLMAgent
from mmarena.cache import DEFAULT_DIR, CachedProvider, ResponseCache
from mmarena.providers.base import Provider

EFFORTS = ("low", "medium", "high", "xhigh", "max")
PROVIDERS = ("anthropic", "openai", "claude-cli", "scripted")
_COMMON = {"max_tokens", "effort", "cache", "name", "repair_attempts", "timeout", "retries"}
_EXTRA = {
    "anthropic": {"api_key_env"},
    "openai": {"api_key_env", "base_url"},
    "claude-cli": {"executable"},
    "scripted": set(),
}


def list_agent_kinds() -> list[tuple[str, str]]:
    """(spec pattern, description) pairs for help text."""
    return [
        *((name, "reference baseline") for name in BASELINES),
        ("anthropic:MODEL", "Anthropic API, key from ANTHROPIC_API_KEY"),
        ("openai:MODEL", "OpenAI API, key from OPENAI_API_KEY"),
        ("openai:MODEL@BASE_URL", "OpenAI-compatible server (OpenRouter, vLLM, Ollama, LM Studio)"),
        ("claude-cli:MODEL", "Claude Code headless (claude -p), local login, no API key"),
        ("scripted:TEXT", "offline fake model that always replies TEXT"),
        ("...@EFFORT", f"suffix: reasoning effort ({', '.join(EFFORTS)})"),
    ]


def parse_spec(spec: str) -> dict[str, Any]:
    """Split a spec into kind, model, base_url and effort. Raises ValueError."""
    spec = spec.strip()
    if spec in BASELINES:
        return {"kind": "baseline", "model": spec, "base_url": None, "effort": None}
    kind, sep, rest = spec.partition(":")
    if not sep or kind not in PROVIDERS:
        known = ", ".join([*BASELINES, *(f"{p}:MODEL" for p in PROVIDERS)])
        raise ValueError(f"unknown agent spec {spec!r}; expected one of {known}")
    if kind == "scripted":
        return {"kind": kind, "model": rest, "base_url": None, "effort": None}
    effort = None
    head, at, tail = rest.rpartition("@")
    if at and tail in EFFORTS:
        rest, effort = head, tail
    base_url = None
    for scheme in ("@http://", "@https://"):
        if scheme in rest:
            rest, _, url = rest.partition("@")
            base_url = url
            break
    if base_url is not None and kind != "openai":
        raise ValueError(f"{spec!r}: a base URL is only supported for openai:MODEL@BASE_URL")
    if not rest:
        raise ValueError(f"{spec!r}: missing model name")
    return {"kind": kind, "model": rest, "base_url": base_url, "effort": effort}


def _canonical(kind: str, model: str, base_url: str | None, effort: str | None) -> str:
    name = f"{kind}:{model}"
    if base_url:
        name += f"@{base_url}"
    if effort:
        name += f"@{effort}"
    return name


def make_provider(
    kind: str, model: str, base_url: str | None, effort: str | None, opts: dict[str, Any]
) -> Provider:
    common: dict[str, Any] = {}
    if opts.get("timeout") is not None:
        common["timeout"] = float(opts["timeout"])
    if opts.get("retries") is not None:
        common["retries"] = int(opts["retries"])
    if kind == "anthropic":
        from mmarena.providers.anthropic import AnthropicProvider

        extra = {k: opts[k] for k in ("api_key_env",) if opts.get(k) is not None}
        return AnthropicProvider(model, effort=effort, **common, **extra)
    if kind == "openai":
        from mmarena.providers.openai import OpenAIProvider

        extra = {k: opts[k] for k in ("api_key_env",) if opts.get(k) is not None}
        return OpenAIProvider(model, base_url=base_url, effort=effort, **common, **extra)
    if kind == "claude-cli":
        from mmarena.providers.claude_cli import ClaudeCLIProvider

        extra = {k: opts[k] for k in ("executable",) if opts.get(k) is not None}
        return ClaudeCLIProvider(model, effort=effort, **common, **extra)
    if kind == "scripted":
        from mmarena.providers.scripted import ScriptedProvider

        return ScriptedProvider(model)
    raise ValueError(f"unknown provider {kind!r}")


def make_agent_factory(spec: str, **options: Any) -> Callable[[], Agent]:
    """A zero-argument factory that builds a fresh agent per episode.

    One provider (and one response cache) is shared by all agents from the factory; both are
    thread-safe. Building an agent makes no network call.
    """
    parsed = parse_spec(spec)
    kind = parsed["kind"]
    opts = {k: v for k, v in options.items() if v is not None}
    name = opts.pop("name", None)

    if kind == "baseline":
        base = BASELINES[parsed["model"]]
        if name is None:
            return base

        def make_baseline() -> Agent:
            agent = base()
            agent.name = name
            return agent

        return make_baseline

    unknown = set(opts) - _COMMON - _EXTRA[kind]
    if unknown:
        raise ValueError(f"{spec!r}: unknown option(s) {', '.join(sorted(unknown))}")
    effort = parsed["effort"]
    if opts.get("effort") is not None:
        if effort is not None and opts["effort"] != effort:
            raise ValueError(f"{spec!r}: effort {opts['effort']!r} conflicts with the spec")
        effort = opts["effort"]
    if effort is not None and effort not in EFFORTS:
        raise ValueError(f"effort must be one of {', '.join(EFFORTS)}, got {effort!r}")
    if kind == "scripted" and effort is not None:
        raise ValueError("scripted agents take no effort")
    base_url = opts.get("base_url", parsed["base_url"])
    model = parsed["model"]

    provider: Provider = make_provider(kind, model, base_url, effort, opts)
    cache_opt = opts.get("cache", True)
    if cache_opt and kind != "scripted":
        directory = DEFAULT_DIR if cache_opt is True else Path(cache_opt)
        provider = CachedProvider(provider, ResponseCache(directory))

    agent_name = name or (spec if kind == "scripted" else _canonical(kind, model, base_url, effort))
    max_tokens = int(opts.get("max_tokens", 8192))
    repair_attempts = int(opts.get("repair_attempts", 1))

    def make_llm() -> Agent:
        return LLMAgent(
            provider, name=agent_name, max_tokens=max_tokens, repair_attempts=repair_attempts
        )

    return make_llm
