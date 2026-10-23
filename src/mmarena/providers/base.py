"""Provider interface: one stateless text completion per call, plus shared retry logic."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from mmarena.agents.base import InfraError

T = TypeVar("T")

# Prompt input: one string, or segments sent in order. Segment boundaries mark where a static
# prefix ends (providers with prompt caching put a cache breakpoint there); other providers
# join the segments with a blank line.
UserInput = str | Sequence[str]


@dataclass
class Completion:
    """One model reply. ``usage`` keys: input_tokens, output_tokens, cache_read_tokens,
    cache_write_tokens (missing when the provider does not report them)."""

    text: str
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    model: str = ""
    latency_s: float = 0.0
    stop_reason: str | None = None
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "usage": dict(self.usage),
            "cost_usd": self.cost_usd,
            "model": self.model,
            "latency_s": self.latency_s,
            "stop_reason": self.stop_reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Completion:
        return cls(
            text=d["text"],
            usage={k: int(v) for k, v in (d.get("usage") or {}).items()},
            cost_usd=d.get("cost_usd"),
            model=d.get("model", ""),
            latency_s=float(d.get("latency_s", 0.0)),
            stop_reason=d.get("stop_reason"),
        )


@runtime_checkable
class Provider(Protocol):
    """A text-in, text-out model endpoint. Implementations must be thread-safe.

    ``name`` and ``model`` identify the endpoint; ``options`` holds every setting other than
    the prompt and ``max_tokens`` that changes the output (used as part of the cache key).
    """

    name: str
    model: str
    options: dict[str, Any]

    def complete(self, system: str, user: UserInput, *, max_tokens: int) -> Completion: ...


class TransientError(Exception):
    """A failure worth retrying (rate limit, overload, timeout, connection drop)."""


def harness_version(provider: object) -> str | None:
    """Version of the software between the benchmark and the model, if the provider reports one.

    Providers may define ``harness_version() -> str | None`` (CLI or SDK version). Wrappers that
    expose ``inner`` are looked through. Errors are swallowed: provenance must never fail a run.
    """
    seen = 0
    while provider is not None and seen < 8:
        fn = getattr(provider, "harness_version", None)
        if callable(fn):
            try:
                v = fn()
            except Exception:  # noqa: BLE001 - provenance is best effort
                return None
            return str(v) if v else None
        provider = getattr(provider, "inner", None)
        seen += 1
    return None


def package_version(dist: str) -> str | None:
    """``"<dist> <version>"`` for an installed distribution, else ``None``."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return f"{dist} {version(dist)}"
    except PackageNotFoundError:
        return None


def join_user(user: UserInput) -> str:
    return user if isinstance(user, str) else "\n\n".join(user)


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    what: str = "provider",
) -> T:
    """Call ``fn``; retry on ``TransientError`` with exponential backoff and jitter.

    ``InfraError`` and any other exception propagate at once. After ``attempts`` transient
    failures an ``InfraError`` is raised.
    """
    attempts = max(1, attempts)
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except TransientError as exc:
            last = exc
            if i + 1 < attempts:
                delay = min(max_delay, base_delay * 2**i)
                sleep(delay * (0.5 + 0.5 * random.random()))
    raise InfraError(f"{what}: gave up after {attempts} attempts: {last}") from last


def is_sdk_error(exc: BaseException) -> bool:
    """True for exceptions from the ``anthropic`` / ``openai`` SDK HTTP layer (``APIError``)."""
    return any(c.__name__ == "APIError" for c in type(exc).__mro__)


def classify_sdk_error(exc: Exception, what: str) -> Exception:
    """Map an ``anthropic`` / ``openai`` SDK exception to TransientError or InfraError.

    Both SDKs share the same shape: ``APIStatusError`` subclasses carry ``status_code``;
    ``APIConnectionError`` / ``APITimeoutError`` carry none.
    """
    status = getattr(exc, "status_code", None)
    msg = f"{what}: {type(exc).__name__}: {exc}"
    if isinstance(status, int):
        if status in (408, 409, 429) or status >= 500:
            return TransientError(msg)
        # 400 bad request, 401 auth, 403 permission, 404 unknown model: configuration or
        # account problems, not the agent's fault and not worth retrying.
        return InfraError(msg)
    if type(exc).__name__ in ("APIConnectionError", "APITimeoutError") or isinstance(
        exc, (TimeoutError, ConnectionError)
    ):
        return TransientError(msg)
    return InfraError(msg)
