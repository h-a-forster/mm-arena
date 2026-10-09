"""Market maker backed by a language model."""

from __future__ import annotations

from typing import Any

from mmarena.agents.base import AgentError, Observation, Quote
from mmarena.agents.prompt import parse_quote, render_prompt_parts, render_repair
from mmarena.cache import CachedProvider
from mmarena.games.base import Game
from mmarena.providers.base import Completion, Provider

RAW_LIMIT = 2000
USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)


def _truncate(text: str, limit: int = RAW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...[{len(text) - limit} chars cut]...\n{text[-half:]}"


class LLMAgent:
    """Renders the full state each step, asks the provider, parses ``{"bid", "ask"}``.

    A reply that cannot be parsed gets up to ``repair_attempts`` follow-up calls that show the
    model its reply and the problem. If none parses, ``AgentError`` is raised with the raw
    replies in ``exc.info`` (the engine records it as an invalid quote).
    """

    def __init__(
        self,
        provider: Provider,
        name: str | None = None,
        max_tokens: int = 8192,
        repair_attempts: int = 1,
    ):
        self.provider = provider
        self.name = name or f"{provider.name}:{provider.model}"
        self.max_tokens = max_tokens
        self.repair_attempts = max(0, repair_attempts)

    def reset(self, game: Game) -> None:
        pass

    def act(self, obs: Observation) -> Quote:
        system, parts = render_prompt_parts(obs)
        user = list(parts)
        calls: list[Completion] = []
        raws: list[str] = []
        problem = ""
        for attempt in range(self.repair_attempts + 1):
            extra: dict[str, Any] = {}
            if isinstance(self.provider, CachedProvider):
                extra["salt"] = f"{obs.game.id}/{obs.episode_seed}/{attempt}"
            comp = self.provider.complete(system, user, max_tokens=self.max_tokens, **extra)
            calls.append(comp)
            raws.append(comp.text)
            if comp.stop_reason == "refusal":
                problem = "the model refused to answer"
                break
            try:
                bid, ask = parse_quote(comp.text)
            except AgentError as exc:
                problem = str(exc)
                if comp.stop_reason in ("max_tokens", "length"):
                    problem += " (the reply hit the output token limit)"
                if attempt < self.repair_attempts:
                    # Keep the static segment first so the prompt cache still applies.
                    user = [*parts[:-1], render_repair(parts[-1], comp.text, problem)]
                continue
            return Quote(bid, ask, self._info(calls, raws))
        err = AgentError(problem)
        err.info = {**self._info(calls, raws), "parse_error": problem}  # type: ignore[attr-defined]
        raise err

    def _info(self, calls: list[Completion], raws: list[str]) -> dict[str, Any]:
        usage = {k: sum(c.usage.get(k, 0) for c in calls) for k in USAGE_KEYS}
        usage = {k: v for k, v in usage.items() if v or k in ("input_tokens", "output_tokens")}
        costs = [c.cost_usd for c in calls]
        last = calls[-1]
        info: dict[str, Any] = {
            "raw": _truncate(raws[-1]),
            "usage": usage,
            "cost_usd": None if any(c is None for c in costs) else round(sum(costs), 8),
            "model": last.model,
            "provider_latency_s": round(sum(c.latency_s for c in calls), 3),
            "repairs": len(calls) - 1,
            "cached": all(c.cached for c in calls),
        }
        if len(raws) > 1:
            info["raw_rejected"] = [_truncate(r, RAW_LIMIT // 2) for r in raws[:-1]]
        if last.stop_reason is not None:
            info["stop_reason"] = last.stop_reason
        return info
