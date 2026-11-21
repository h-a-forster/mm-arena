"""The openai provider against a local stub shaped like llama.cpp's OpenAI-compatible server.

Offline: the stub listens on 127.0.0.1. It returns the reasoning in ``reasoning_content`` (as
``--reasoning-format deepseek`` does) with a decoy quote in it, so a quote read from the
reasoning instead of the answer shows up as the wrong number.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mmarena.agents.registry import make_agent_factory
from mmarena.engine import run_episode
from mmarena.games import make_game

pytest.importorskip("openai")


def _stub(reply: dict, requests: list[dict]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            data = json.dumps(
                {
                    "id": "x",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body["model"],
                    "choices": [{"index": 0, **reply}],
                    "usage": {
                        "prompt_tokens": 900,
                        "completion_tokens": 1200,
                        "total_tokens": 2100,
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _play(reply: dict) -> tuple[dict, list[dict]]:
    requests: list[dict] = []
    server = _stub(reply, requests)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1"
        factory = make_agent_factory(
            f"openai:qwen3-14b-q4km@{url}", cache=False, max_tokens=16384, retries=1
        )
        trace = run_episode(make_game("dice", 0, "classic"), factory(), seed=0)
    finally:
        server.shutdown()
    return trace, requests


def test_answer_is_read_from_content_not_reasoning():
    trace, requests = _play(
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": 'Wide quote. {"bid": 3, "ask": 18}',
                "reasoning_content": 'Draft: {"bid": 10, "ask": 11}. Too tight.',
            },
        }
    )
    assert trace["status"] == "ok"
    assert {(s["bid"], s["ask"]) for s in trace["steps"]} == {(3.0, 18.0)}
    assert all(s["invalid"] is None for s in trace["steps"])
    assert all(s["info"]["usage"]["output_tokens"] == 1200 for s in trace["steps"])
    # max_tokens (not max_completion_tokens) for a compatible server; no sampling sent
    assert requests[0]["max_tokens"] == 16384
    assert "temperature" not in requests[0]


def test_thinking_cut_off_is_an_invalid_quote_not_a_crash():
    trace, requests = _play(
        {
            "finish_reason": "length",
            "message": {"role": "assistant", "content": "", "reasoning_content": "Let me think"},
        }
    )
    assert trace["status"] == "ok"
    steps = trace["steps"]
    assert all(s["invalid"] == "format" and s["bid"] is None for s in steps)
    assert all(s["info"]["stop_reason"] == "length" for s in steps)
    assert len(requests) == 2 * len(steps)  # one repair attempt per step
