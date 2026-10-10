"""Claude Code in headless print mode (``claude -p``), using the local Claude Code login.

No API key is needed. Each call runs, in a fresh empty temporary directory::

    claude -p --output-format json --no-session-persistence --model MODEL
        --system-prompt-file SYSTEM.md --tools "" --strict-mcp-config --setting-sources ""
        --safe-mode --disable-slash-commands --max-turns 1 [--effort LEVEL]

with the user prompt on stdin. The system prompt replaces Claude Code's own; no tools, MCP
servers, settings files, hooks, plugins, skills or CLAUDE.md files are loaded. ``max_tokens``
is not supported by the CLI and is ignored. Cost is the API list price of the call's tokens
(``mmarena.pricing``), whether or not a subscription pays for it. Claude Code's own
``total_cost_usd`` is used only for models without a listed price: it has been seen to price
some new models at another model's rates.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping
from typing import Any

from mmarena.agents.base import InfraError
from mmarena.pricing import list_cost
from mmarena.providers.base import Completion, TransientError, UserInput, join_user, with_retries

EFFORTS = ("low", "medium", "high", "xhigh", "max")

# Account or login problems: retrying will not help.
_AUTH = re.compile(
    r"authentication|invalid api key|not logged in|/login|oauth token|unauthori[sz]ed"
    r"|credit balance|usage limit|quota",
    re.IGNORECASE,
)
_TAIL = 400


def _tail(text: str, n: int = _TAIL) -> str:
    return text.strip()[-n:]


def _result_object(stdout: str) -> dict[str, Any] | None:
    """The ``{"type": "result", ...}`` object in stdout (possibly after log lines)."""
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    found = None
    for line in stdout.splitlines():
        start = line.find("{")
        if start < 0:
            continue
        try:
            obj, _ = decoder.raw_decode(line, start)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "result":
            found = obj
    return found


def _int(v: Any) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def _main_model(model_usage: Mapping[str, Any], requested: str | None) -> str:
    """The ``modelUsage`` key of the model that answered.

    Recent Claude Code versions add a small auxiliary call on another model (seen: Haiku 5.5),
    so the first key is not necessarily the requested model.
    """
    keys = [k for k in model_usage if isinstance(k, str)]
    if not keys:
        return ""
    if requested:
        for k in keys:
            entry = model_usage[k] if isinstance(model_usage[k], Mapping) else {}
            if k == requested or entry.get("canonicalModel") == requested:
                return k
        for k in keys:
            if k.startswith(requested + "-"):
                return k
    if len(keys) == 1:
        return keys[0]
    out = {k: _int((model_usage[k] or {}).get("outputTokens")) for k in keys}
    return max(keys, key=lambda k: out[k])


def _aux_usage(
    model_usage: Mapping[str, Any], main: str, usage: Mapping[str, int]
) -> tuple[int, int, float | None]:
    """Input tokens, output tokens and list-price USD of calls other than the main reply.

    ``modelUsage`` totals every call per model; the top-level ``usage`` is the main reply only.
    """
    aux_in = aux_out = 0
    cost: float | None = 0.0
    for k, entry in model_usage.items():
        if not isinstance(entry, Mapping):
            continue
        tok = {
            "input_tokens": _int(entry.get("inputTokens")),
            "output_tokens": _int(entry.get("outputTokens")),
            "cache_read_tokens": _int(entry.get("cacheReadInputTokens")),
            "cache_write_tokens": _int(entry.get("cacheCreationInputTokens")),
        }
        if k == main:
            tok = {key: max(0, v - _int(usage.get(key))) for key, v in tok.items()}
        if not any(tok.values()):
            continue
        aux_in += tok["input_tokens"] + tok["cache_read_tokens"] + tok["cache_write_tokens"]
        aux_out += tok["output_tokens"]
        c = list_cost(k, tok, default_write_ttl="1h")
        cost = None if c is None or cost is None else cost + c
    return aux_in, aux_out, cost


def parse_cli_output(
    stdout: str, stderr: str, exit_code: int | None, requested_model: str | None = None
) -> Completion:
    """Turn ``claude -p --output-format json`` output into a Completion.

    ``usage`` and ``model`` describe the main reply. Tokens of auxiliary calls Claude Code makes
    on its own are recorded as ``aux_input_tokens`` / ``aux_output_tokens``; their list price is
    included in ``cost_usd`` but not in costs recomputed from ``usage``.

    Raises InfraError for login/account failures and TransientError for rate limits,
    overloads, network errors and unexplained failures.
    """
    obj = _result_object(stdout)
    if obj is None:
        detail = _tail(stderr) or _tail(stdout) or "no output"
        if _AUTH.search(detail):
            raise InfraError(f"claude-cli: {detail}")
        raise TransientError(f"claude-cli: exit code {exit_code} without a JSON result: {detail}")

    text = obj.get("result") if isinstance(obj.get("result"), str) else ""
    if obj.get("is_error") is True or obj.get("subtype") not in (None, "success"):
        status = obj.get("api_error_status")
        detail = f"{obj.get('subtype')}: {_tail(text) or _tail(stderr)}"
        if status in (401, 403) or _AUTH.search(detail):
            raise InfraError(f"claude-cli: {detail}")
        if status == 404:
            raise InfraError(f"claude-cli: unknown model or endpoint (404): {detail}")
        raise TransientError(f"claude-cli: API error {status}: {detail}")

    tokens = obj.get("usage") if isinstance(obj.get("usage"), Mapping) else {}
    usage = {
        "input_tokens": _int(tokens.get("input_tokens")),
        "output_tokens": _int(tokens.get("output_tokens")),
        "cache_read_tokens": _int(tokens.get("cache_read_input_tokens")),
        "cache_write_tokens": _int(tokens.get("cache_creation_input_tokens")),
    }
    creation = tokens.get("cache_creation")
    if isinstance(creation, Mapping) and "ephemeral_1h_input_tokens" in creation:
        usage["cache_write_1h_tokens"] = _int(creation.get("ephemeral_1h_input_tokens"))
    details = tokens.get("output_tokens_details")
    if isinstance(details, Mapping) and _int(details.get("thinking_tokens")):
        usage["reasoning_tokens"] = _int(details.get("thinking_tokens"))
    cost = obj.get("total_cost_usd")
    model_usage = obj.get("modelUsage")
    model_usage = model_usage if isinstance(model_usage, Mapping) else {}
    model = _main_model(model_usage, requested_model)
    reported = float(cost) if isinstance(cost, (int, float)) and cost >= 0 else None
    listed = list_cost(model, usage, default_write_ttl="1h")
    aux_in, aux_out, aux_cost = _aux_usage(model_usage, model, usage)
    if aux_in or aux_out:
        usage["aux_input_tokens"] = aux_in
        usage["aux_output_tokens"] = aux_out
        if listed is not None:
            listed = None if aux_cost is None else listed + aux_cost
    return Completion(
        text=text,
        usage=usage,
        cost_usd=listed if listed is not None else reported,
        model=model,
        stop_reason=obj.get("stop_reason"),
    )


class ClaudeCLIProvider:
    name = "claude-cli"

    def __init__(
        self,
        model: str,
        *,
        effort: str | None = None,
        executable: str = "claude",
        timeout: float = 600.0,
        retries: int = 4,
        extra_args: tuple[str, ...] = (),
    ):
        if effort is not None and effort not in EFFORTS:
            raise ValueError(f"effort must be one of {', '.join(EFFORTS)}, got {effort!r}")
        self.model = model
        self.effort = effort
        self.executable = executable
        self.timeout = timeout
        self.retries = retries
        self.extra_args = tuple(extra_args)
        self.options: dict[str, Any] = {"effort": effort, "extra_args": list(self.extra_args)}

    def argv(self, exe: str, system_file: str) -> list[str]:
        argv = [
            exe,
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--model",
            self.model,
            "--system-prompt-file",
            system_file,
            "--tools",
            "",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--safe-mode",
            "--disable-slash-commands",
            "--max-turns",
            "1",
        ]
        if self.effort:
            argv += ["--effort", self.effort]
        return argv + list(self.extra_args)

    def _run_once(self, exe: str, system: str, user: str) -> Completion:
        with tempfile.TemporaryDirectory(prefix="mmarena-cli-", ignore_cleanup_errors=True) as tmp:
            # The system prompt goes through a file: multi-line arguments are fragile on Windows.
            system_file = os.path.join(tmp, "system.md")
            with open(system_file, "w", encoding="utf-8", newline="") as fh:
                fh.write(system)
            work = os.path.join(tmp, "work")
            os.mkdir(work)
            started = time.perf_counter()
            try:
                proc = subprocess.run(
                    self.argv(exe, system_file),
                    input=user,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=work,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise TransientError(f"claude-cli: timed out after {self.timeout}s") from exc
            except OSError as exc:
                raise InfraError(f"claude-cli: could not start {exe}: {exc}") from exc
            latency = time.perf_counter() - started
        comp = parse_cli_output(proc.stdout or "", proc.stderr or "", proc.returncode, self.model)
        comp.latency_s = round(latency, 3)
        comp.model = comp.model or self.model
        return comp

    def complete(self, system: str, user: UserInput, *, max_tokens: int) -> Completion:
        exe = shutil.which(self.executable)
        if exe is None:
            raise InfraError(f"claude-cli: executable {self.executable!r} not found on PATH")
        text = join_user(user)
        return with_retries(
            lambda: self._run_once(exe, system, text), attempts=self.retries, what="claude-cli"
        )
