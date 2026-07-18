#!/usr/bin/env python3
"""embed_server.py - self-host bge-small-en-v1.5 embedding server (NO rate limit).

The durable capacity fix (Ian, 2026-06-13): free embedding APIs (Voyage 3 RPM w/o card,
Gemini free-tier 429 on a burst) cannot serve many concurrent users. A self-hosted
embedding model has NO per-request cap. This serves the SAME model the ingest tool uses
(fastembed `BAAI/bge-small-en-v1.5`, 384-dim, L2-normalized) so ingest and the edge query
land in ONE vector space.

The Deno edge calls this over the docker network (host.docker.internal / a host IP):
  POST /embed  {"texts": ["..."]}  -> {"embeddings": [[384 floats], ...], "model": "...", "dim": 384}
  GET  /health                     -> {"ok": true, ...}

Run:  python tools/embed_server.py            # port 8901
      python tools/embed_server.py 8901
Needs: pip install fastembed   (ONNX, no torch). First run downloads the model (~130MB).
"""
from __future__ import annotations
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8901
MODEL_NAME = "BAAI/bge-small-en-v1.5"
_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from fastembed import TextEmbedding  # type: ignore
        _MODEL = TextEmbedding(model_name=MODEL_NAME)
    return _MODEL


def _l2(vec: list[float]) -> list[float]:
    n = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / n for x in vec]


def embed(texts: list[str]) -> list[list[float]]:
    return [_l2([float(x) for x in vec]) for vec in _model().embed([t[:8000] for t in texts])]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "model": "bge-small-en-v1.5", "dim": 384})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/embed":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            texts = data.get("texts")
            if not texts and data.get("text"):
                texts = [data["text"]]
            if not texts:
                return self._send(400, {"error": "no texts"})
            embs = embed([str(t) for t in texts])
            self._send(200, {"embeddings": embs, "model": "bge-small-en-v1.5",
                             "dim": len(embs[0]) if embs else 0})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})

    def log_message(self, *args) -> None:  # keep it quiet
        return


def _self_heal_loop(interval_min: int) -> None:
    """Hands-free self-healing: periodically run the idempotent dirty-row re-embed sweep so any row
    embedded in a foreign space during a past outage re-heals into bge-local space. Decoupled via a
    subprocess (no import coupling); a cheap no-op when the corpus is already in lockstep. Opt-in via
    env WH_EMBED_SELFHEAL_MIN so the pure embedding server stays pure by default."""
    import subprocess
    from pathlib import Path
    sweep = str(Path(__file__).with_name("reembed_dirty_knowledge.py"))
    while True:
        time.sleep(interval_min * 60)
        try:
            out = subprocess.run([sys.executable, sweep], capture_output=True, text=True, timeout=600)
            tail = (out.stdout or out.stderr or "").strip().splitlines()
            if tail:
                print(f"[self-heal] {tail[-1].strip()}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[self-heal] sweep error: {type(e).__name__}: {e}", flush=True)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    print(f"warming {MODEL_NAME} ...", flush=True)
    _model()  # download + load once at startup
    # Hands-free self-heal (OWN-EMBEDDER): WH_EMBED_SELFHEAL_MIN=15 makes THIS one process the complete
    # self-healing embedder - serves embeddings AND re-heals dirty corpus rows on a timer. Off by default.
    heal_min = int(os.environ.get("WH_EMBED_SELFHEAL_MIN", "0") or "0")
    if heal_min > 0:
        threading.Thread(target=_self_heal_loop, args=(heal_min,), daemon=True).start()
        print(f"[self-heal] enabled - dirty-row re-embed sweep every {heal_min} min (idempotent no-op when clean)", flush=True)
    print(f"embed_server listening on 0.0.0.0:{port} (bge-small-en-v1.5, 384d, no rate limit)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
