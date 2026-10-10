"""API list prices, used to cost runs from recorded token counts.

Costs in reports are computed from each step's token usage at these prices, not taken from the
provider's own figure, so runs through different providers (and old traces) are costed the same
way. Models not listed fall back to the cost the provider reported, if any.

Prices are USD per million tokens, from https://platform.claude.com/docs/en/about-claude/pricing
as of ``PRICES_AS_OF``. Claude Haiku 5.5 has higher prices for prompts over 100,000 tokens; mm-arena
prompts are a few thousand tokens, so only the base rates are listed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

PRICES_AS_OF = "2026-10-10"


class Price(NamedTuple):
    input: float
    output: float
    cache_read: float
    cache_write_5m: float
    cache_write_1h: float


PRICES: dict[str, Price] = {
    "claude-fable-5-1": Price(10.0, 50.0, 0.25, 12.5, 20.0),
    "claude-fable-5": Price(10.0, 50.0, 1.0, 12.5, 20.0),
    "claude-opus-5-5": Price(4.0, 20.0, 0.20, 5.0, 8.0),
    "claude-opus-5": Price(5.0, 25.0, 0.50, 6.25, 10.0),
    "claude-opus-4-8": Price(5.0, 25.0, 0.50, 6.25, 10.0),
    "claude-opus-4-7": Price(5.0, 25.0, 0.50, 6.25, 10.0),
    "claude-opus-4-6": Price(5.0, 25.0, 0.50, 6.25, 10.0),
    "claude-sonnet-5-5": Price(2.0, 10.0, 0.10, 2.5, 4.0),
    "claude-sonnet-5": Price(2.0, 10.0, 0.20, 2.5, 4.0),
    "claude-sonnet-4-6": Price(3.0, 15.0, 0.30, 3.75, 6.0),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.01, 0.125, 0.20),
    "claude-haiku-4-5": Price(1.0, 5.0, 0.10, 1.25, 2.0),
}


def price_for(model: str | None) -> Price | None:
    """Price of a model id; dated snapshot ids (claude-haiku-4-5-20251001) map to their base id."""
    if not model:
        return None
    if model in PRICES:
        return PRICES[model]
    # Longest base id first, so claude-opus-5-5-... is not matched by claude-opus-5.
    for base in sorted(PRICES, key=len, reverse=True):
        if model.startswith(base + "-"):
            return PRICES[base]
    return None


def list_cost(
    model: str | None, usage: Mapping[str, Any], default_write_ttl: str = "5m"
) -> float | None:
    """USD cost of one call at list prices, or None for an unknown model.

    ``cache_write_tokens`` counts all cache writes. The 1-hour part is ``cache_write_1h_tokens``
    when the provider reports it; otherwise every write is priced at ``default_write_ttl``.
    """
    price = price_for(model)
    if price is None:
        return None

    def n(key: str) -> float:
        v = usage.get(key)
        return float(v) if isinstance(v, (int, float)) else 0.0

    writes = n("cache_write_tokens")
    if "cache_write_1h_tokens" in usage:
        writes_1h = min(n("cache_write_1h_tokens"), writes)
    else:
        writes_1h = writes if default_write_ttl == "1h" else 0.0
    return (
        n("input_tokens") * price.input
        + n("output_tokens") * price.output
        + n("cache_read_tokens") * price.cache_read
        + (writes - writes_1h) * price.cache_write_5m
        + writes_1h * price.cache_write_1h
    ) / 1e6
