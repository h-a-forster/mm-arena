"""Anthropic Messages API via the official ``anthropic`` SDK (``pip install mm-arena[anthropic]``).

The API key is read from the environment (``ANTHROPIC_API_KEY`` by default) and never stored.
No sampling parameters are sent (current models reject them). Thinking is left at the model
default (adaptive where supported); ``effort`` is sent as ``output_config.effort`` only when set.
The system prompt and every user segment except the last carry ``cache_control``, so the static
part of the prompt is read from the prompt cache on later steps of the same game. Prefixes below
the model's minimum cacheable length are simply not cached.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from mmarena.agents.base import InfraError
from mmarena.pricing import list_cost
from mmarena.providers.base import (
    Completion,
    UserInput,
    classify_sdk_error,
    is_sdk_error,
    package_version,
    with_retries,
)

EFFORTS = ("low", "medium", "high", "xhigh", "max")


def estimate_cost(model: str, usage: dict[str, int]) -> float | None:
    """List-price cost of one call; the SDK path writes the cache with the default 5-minute TTL."""
    return list_cost(model, usage)


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        model: str,
        *,
        effort: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        timeout: float = 600.0,
        retries: int = 4,
        cache_prompt: bool = True,
        client: Any = None,
    ):
        if effort is not None and effort not in EFFORTS:
            raise ValueError(f"effort must be one of {', '.join(EFFORTS)}, got {effort!r}")
        self.model = model
        self.effort = effort
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.retries = retries
        self.cache_prompt = cache_prompt
        self.options: dict[str, Any] = {"effort": effort}
        self._client = client
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        with self._lock:
            if self._client is None:
                try:
                    import anthropic
                except ImportError as exc:
                    raise InfraError(
                        "the anthropic provider needs the anthropic SDK: "
                        "pip install 'mm-arena[anthropic]'"
                    ) from exc
                key = os.environ.get(self.api_key_env)
                if not key:
                    raise InfraError(
                        f"anthropic: environment variable {self.api_key_env} is not set"
                    )
                # Retries are handled here (with_retries), not by the SDK.
                self._client = anthropic.Anthropic(api_key=key, timeout=self.timeout, max_retries=0)
            return self._client

    def _request(self, system: str, user: UserInput, max_tokens: int) -> dict[str, Any]:
        segments = [user] if isinstance(user, str) else list(user)
        cc = {"cache_control": {"type": "ephemeral"}} if self.cache_prompt else {}
        content = [
            {"type": "text", "text": s, **(cc if i < len(segments) - 1 else {})}
            for i, s in enumerate(segments)
        ]
        req: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, **cc}],
            "messages": [{"role": "user", "content": content}],
        }
        if self.effort is not None:
            req["output_config"] = {"effort": self.effort}
        return req

    def harness_version(self) -> str | None:
        """Installed ``anthropic`` SDK version, recorded in each trace's provenance."""
        return package_version("anthropic")

    def complete(self, system: str, user: UserInput, *, max_tokens: int) -> Completion:
        client = self._get_client()
        req = self._request(system, user, max_tokens)

        def call() -> Any:
            try:
                return client.messages.create(**req)
            except Exception as exc:
                if not is_sdk_error(exc):
                    raise
                raise classify_sdk_error(exc, "anthropic") from exc

        started = time.perf_counter()
        resp = with_retries(call, attempts=self.retries, what="anthropic")
        latency = time.perf_counter() - started
        text = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )
        u = resp.usage
        usage = {
            "input_tokens": int(getattr(u, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(u, "output_tokens", 0) or 0),
            "cache_read_tokens": int(getattr(u, "cache_read_input_tokens", 0) or 0),
            "cache_write_tokens": int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        }
        model = getattr(resp, "model", None) or self.model
        return Completion(
            text=text,
            usage=usage,
            cost_usd=estimate_cost(model, usage),
            model=model,
            latency_s=round(latency, 3),
            stop_reason=getattr(resp, "stop_reason", None),
        )
