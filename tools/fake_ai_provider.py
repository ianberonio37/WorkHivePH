#!/usr/bin/env python3
"""fake_ai_provider.py - a LOCAL stand-in for a model provider that misbehaves on purpose (OWN dependency lens, 2026-10-26).

ai-chain.ts honours faultInject.fake only on a local runtime: the named providers' REAL request goes here instead of
being skipped by simulation, so the chain's own timeout, status and parse code meets each failure:

    POST /slow/chat/completions      waits 40 s (past the chain's 25 s ceiling), then answers
    POST /429/chat/completions       429 with Retry-After: 60
    POST /changed/chat/completions   200 with no "choices" - the shape an OpenAI-compatible API would break into
    POST /<mode>/embeddings          the same three, for an embedding provider
    ("down" needs no server: the chain is pointed at a closed port)

    python tools/fake_ai_provider.py [--port 8977]
The edge runtime reaches it as http://host.docker.internal:8977.
"""
from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Fake(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict, headers: dict | None = None):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass   # the caller gave up first - which is exactly what "slow" tests

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        mode = self.path.strip("/").split("/")[0]
        if mode == "slow":
            time.sleep(40)
            return self._send(200, {"choices": [{"message": {"content": "late"}, "finish_reason": "stop"}]})
        if mode == "429":
            return self._send(429, {"error": {"message": "Rate limit reached (fake)"}}, {"Retry-After": "60"})
        if mode == "changed":
            return self._send(200, {"output": {"text": "OK"}, "data_v2": []})
        return self._send(404, {"error": f"unknown mode {mode}"})

    def log_message(self, fmt, *args):
        print("[fake-ai]", self.command, self.path, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8977)
    a = ap.parse_args()
    print(f"fake AI provider on :{a.port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", a.port), Fake).serve_forever()


if __name__ == "__main__":
    main()
