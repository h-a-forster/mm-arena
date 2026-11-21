"""Open-weight arm: a local GGUF model behind llama.cpp's OpenAI-compatible server on a suite.

    uv run python scripts/open_weight.py --gguf PATH/Qwen3-14B-Q4_K_M.gguf \
        --server PATH/llama-server [--suite core-v1] [--out results/core-v1-open-weight]

Refuses to start if more than 2 GiB of GPU memory is already in use (llama-server needs the
card to itself) or if the GGUF's SHA-256 is not the pinned one. Then it starts ``llama-server``
with the pinned flags (log under ``tmp/``), runs ``bayes`` (the edge reference) and the model on
the suite in a resume loop (``--attempts``; traces append per episode and reruns skip finished
ones), writes ``harness.json`` (llama.cpp build, flags, GGUF hash) beside the traces, stops the
server and runs ``mm-arena report`` on the output directory.

The output directory is separate from ``results/core-v1`` on purpose: adding an agent there
would change the Holm families and so published p-values. ``--base-url`` skips the GGUF check
and the server start and uses a server that is already up (a dry run against a stub).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from mmarena.cli import main as mm_arena

MODEL = "qwen3-14b-q4km"
GGUF_SHA256 = "500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0"
PORT = 8094
# Qwen3's recommended thinking-mode sampling; set server-side, the client sends none.
SERVER_FLAGS = [
    "--alias", MODEL,
    "--n-gpu-layers", "99",
    "--ctx-size", "32768",
    "--kv-unified",
    "--parallel", "2",
    "--flash-attn", "on",
    "--reasoning-budget", "8192",  # a token budget (N > 0) in build 10698's --help
    "--reasoning-format", "deepseek",
    "--temp", "0.6",
    "--top-p", "0.95",
    "--top-k", "20",
    "--jinja",
    "--host", "127.0.0.1",
    "--port", str(PORT),
]  # fmt: skip
WORKERS = 2  # = --parallel
# Thinking is capped at 8192 tokens by the server; this leaves room for the answer after it.
# Real use per slot is prompt (under 1k tokens) + 8192 + a short answer, so two slots fit the
# 32768-token shared context even though 2 x MAX_TOKENS alone would not.
MAX_TOKENS = 16384


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 24):
            h.update(chunk)
    return h.hexdigest()


def gpu_busy(limit_mib: int = 2048) -> list[str]:
    """GPUs with more than ``limit_mib`` MiB in use (empty if none or no nvidia-smi).

    Memory, not the compute-app list: on a Windows desktop that list holds every graphics app
    (dwm.exe, explorer.exe) with no per-process memory, so it is never empty.
    """
    smi = shutil.which("nvidia-smi")
    if smi is None:
        return []
    out = subprocess.run(
        [smi, "--query-gpu=index,name,memory.used", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = [[c.strip() for c in ln.split(",")] for ln in out.splitlines() if ln.strip()]
    return [f"GPU {i} {name}: {used} MiB used" for i, name, used in rows if int(used) > limit_mib]


def wait_healthy(base_url: str, proc: subprocess.Popen | None, timeout: float = 600) -> None:
    url = base_url.removesuffix("/v1") + "/health"
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if proc is not None and proc.poll() is not None:
            raise SystemExit(f"llama-server exited with code {proc.returncode}; see its log")
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise SystemExit(f"{url} not healthy after {timeout:.0f}s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gguf", type=Path, help="model file (checked against the pinned SHA-256)")
    ap.add_argument("--server", default="llama-server", help="llama-server executable")
    ap.add_argument("--base-url", help="use this running server instead of starting one")
    ap.add_argument("--suite", default="core-v1")
    ap.add_argument("--out", type=Path, help="default results/core-v1-open-weight")
    ap.add_argument("--attempts", type=int, default=4)
    ap.add_argument("--log-dir", type=Path, default=Path("tmp"))
    args = ap.parse_args()
    if args.out is None:
        if args.base_url:
            raise SystemExit("--base-url (a dry run) needs an explicit --out")
        args.out = Path("results/core-v1-open-weight")

    harness: dict[str, object] = {"model": MODEL, "max_tokens": MAX_TOKENS, "workers": WORKERS}
    proc = None
    base_url = args.base_url
    if base_url is None:
        if args.gguf is None:
            raise SystemExit("--gguf is required unless --base-url is given")
        if busy := gpu_busy():
            raise SystemExit(f"GPU in use, not starting llama-server: {busy}")
        exe = shutil.which(args.server) or args.server
        version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120)
        print(f"checking SHA-256 of {args.gguf} ...", file=sys.stderr)
        digest = sha256(args.gguf)
        if digest != GGUF_SHA256:
            raise SystemExit(f"{args.gguf}: SHA-256 {digest}, expected {GGUF_SHA256}")
        harness |= {
            "gguf": args.gguf.name,
            "gguf_sha256": digest,
            "llama_cpp": " ".join((version.stdout + version.stderr).split()),
            "server_flags": SERVER_FLAGS,
        }
        args.log_dir.mkdir(parents=True, exist_ok=True)
        log = (args.log_dir / "llama-server.log").open("a", encoding="utf-8")
        proc = subprocess.Popen(
            [exe, "--model", str(args.gguf), *SERVER_FLAGS], stdout=log, stderr=subprocess.STDOUT
        )
        base_url = f"http://127.0.0.1:{PORT}/v1"
    try:
        wait_healthy(base_url, proc)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "harness.json").write_text(
            json.dumps(harness, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        common = ["--suite", args.suite, "--out", str(args.out)]
        if mm_arena(["run", "--agent", "bayes", *common]) != 0:
            raise SystemExit("bayes reference run failed")
        llm = [
            "run",
            "--agent", f"openai:{MODEL}@{base_url}",
            "--name", f"openai:{MODEL}",
            "--workers", str(WORKERS),
            "--max-tokens", str(MAX_TOKENS),
            *common,
        ]  # fmt: skip
        for attempt in range(1, args.attempts + 1):
            status = mm_arena(llm)  # resumes: finished episodes are skipped
            print(f"attempt {attempt}: exit {status}", file=sys.stderr)
            if status == 0:
                break
            wait_healthy(base_url, proc)
        else:
            raise SystemExit(f"episodes still failing after {args.attempts} attempts")
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=60)
    return mm_arena(["report", str(args.out), "--quiet"])


if __name__ == "__main__":
    raise SystemExit(main())
