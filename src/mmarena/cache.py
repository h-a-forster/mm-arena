"""On-disk cache of model replies, so re-running a suite is free and reproducible.

Entries are keyed by sha256 of (provider, model, options, max_tokens, system, user, salt).
The LLM agent passes ``salt = game id / episode seed / attempt``, so each episode gets its own
sample even when two episodes see an identical prompt (the first step of every seed of a game),
and a re-run or resumed run maps every request to the same entry regardless of thread order.
Without a salt, the key falls back to an occurrence count within the process.

Files are written atomically (temp file + rename); the cache is safe to share between threads.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from mmarena.providers.base import Completion, Provider, UserInput, join_user

DEFAULT_DIR = ".mmarena-cache"


class ResponseCache:
    def __init__(self, directory: str | Path = DEFAULT_DIR):
        self.dir = Path(directory)
        self._lock = threading.Lock()
        self._seen: Counter[str] = Counter()

    @staticmethod
    def base_key(
        provider: str,
        model: str,
        options: dict[str, Any],
        max_tokens: int,
        system: str,
        user: str,
    ) -> str:
        payload = json.dumps(
            [provider, model, options, max_tokens, system, user],
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def next_key(self, base: str) -> str:
        """Key for the next occurrence of ``base`` in this process."""
        with self._lock:
            n = self._seen[base]
            self._seen[base] += 1
        return base if n == 0 else hashlib.sha256(f"{base}:{n}".encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self.dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        try:
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(value, fh, ensure_ascii=False)
            for attempt in range(5):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:  # Windows: target briefly open by a reader
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class CachedProvider:
    """Wraps a provider; replies come from ``cache`` when present and are stored otherwise."""

    def __init__(self, inner: Provider, cache: ResponseCache):
        self.inner = inner
        self.cache = cache
        self.name = inner.name
        self.model = inner.model
        self.options = inner.options

    def complete(
        self, system: str, user: UserInput, *, max_tokens: int, salt: str | None = None
    ) -> Completion:
        base = ResponseCache.base_key(
            self.inner.name,
            self.inner.model,
            self.inner.options,
            max_tokens,
            system,
            join_user(user),
        )
        if salt is None:
            key = self.cache.next_key(base)
        else:
            key = hashlib.sha256(f"{base}|{salt}".encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is not None:
            comp = Completion.from_dict(hit)
            comp.cached = True
            return comp
        comp = self.inner.complete(system, user, max_tokens=max_tokens)
        self.cache.put(key, comp.to_dict())
        return comp
