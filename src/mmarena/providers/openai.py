"""OpenAI-compatible chat completions via the official ``openai`` SDK
(``pip install mm-arena[openai]``).

Covers OpenAI itself and any server with an OpenAI-compatible ``/v1/chat/completions`` endpoint
(OpenRouter, vLLM, Ollama, LM Studio) through ``base_url``. The API key is read from the
environment variable ``api_key_env``; with a custom ``base_url`` a missing key is allowed (local
servers usually ignore it). ``effort`` is sent as ``reasoning_effort`` only when set.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from mmarena.agents.base import InfraError
from mmarena.providers.base import (
    Completion,
    TransientError,
    UserInput,
    classify_sdk_error,
    is_sdk_error,
    join_user,
    with_retries,
)


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key_env: str | None = None,
        effort: str | None = None,
        timeout: float = 600.0,
        retries: int = 4,
        token_param: str | None = None,
        client: Any = None,
    ):
        self.model = model
        self.base_url = base_url
        if api_key_env is None:
            api_key_env = (
                "OPENROUTER_API_KEY"
                if base_url and "openrouter.ai" in base_url
                else "OPENAI_API_KEY"
            )
        self.api_key_env = api_key_env
        self.effort = effort
        self.timeout = timeout
        self.retries = retries
        # OpenAI's own API wants max_completion_tokens; most compatible servers take max_tokens.
        self.token_param = token_param or ("max_tokens" if base_url else "max_completion_tokens")
        self.options: dict[str, Any] = {"base_url": base_url, "effort": effort}
        self._client = client
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        with self._lock:
            if self._client is None:
                try:
                    import openai
                except ImportError as exc:
                    raise InfraError(
                        "the openai provider needs the openai SDK: pip install 'mm-arena[openai]'"
                    ) from exc
                key = os.environ.get(self.api_key_env)
                if not key:
                    if self.base_url is None:
                        raise InfraError(
                            f"openai: environment variable {self.api_key_env} is not set"
                        )
                    key = "not-needed"
                self._client = openai.OpenAI(
                    api_key=key, base_url=self.base_url, timeout=self.timeout, max_retries=0
                )
            return self._client

    def complete(self, system: str, user: UserInput, *, max_tokens: int) -> Completion:
        client = self._get_client()
        req: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": join_user(user)},
            ],
            self.token_param: max_tokens,
        }
        if self.effort is not None:
            req["reasoning_effort"] = self.effort

        def call() -> Any:
            try:
                resp = client.chat.completions.create(**req)
            except Exception as exc:
                if not is_sdk_error(exc):
                    raise
                raise classify_sdk_error(exc, "openai") from exc
            # Routers such as OpenRouter report upstream failures as HTTP 200 with
            # finish_reason "error": an outage, not the model's answer.
            choices = getattr(resp, "choices", None) or []
            if choices and getattr(choices[0], "finish_reason", None) == "error":
                raise TransientError("openai: upstream provider error (finish_reason=error)")
            return resp

        started = time.perf_counter()
        resp = with_retries(call, attempts=self.retries, what="openai")
        latency = time.perf_counter() - started
        if not getattr(resp, "choices", None):
            raise InfraError(f"openai: response without choices: {resp!r}"[:500])
        choice = resp.choices[0]
        text = getattr(choice.message, "content", None) or ""
        usage: dict[str, int] = {}
        u = getattr(resp, "usage", None)
        if u is not None:
            usage["input_tokens"] = int(getattr(u, "prompt_tokens", 0) or 0)
            usage["output_tokens"] = int(getattr(u, "completion_tokens", 0) or 0)
            details = getattr(u, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", None) if details is not None else None
            if cached:
                usage["cache_read_tokens"] = int(cached)
            out_details = getattr(u, "completion_tokens_details", None)
            reasoning = (
                getattr(out_details, "reasoning_tokens", None) if out_details is not None else None
            )
            if reasoning:
                usage["reasoning_tokens"] = int(reasoning)
            # OpenRouter reports the charge in usage.cost.
        cost = getattr(u, "cost", None) if u is not None else None
        return Completion(
            text=text,
            usage=usage,
            cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
            model=getattr(resp, "model", None) or self.model,
            latency_s=round(latency, 3),
            stop_reason=getattr(choice, "finish_reason", None),
        )
