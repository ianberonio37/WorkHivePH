#!/usr/bin/env python3
"""resend_capture_sink.py — a local stand-in for api.resend.com, so the send PATH can be walked.

WHY (W3-FN, 2026-09-09). `send-report-email` refuses to do anything without RESEND_API_KEY, and the key
that exists is the PRODUCTION one: setting it here would make every probe run send real, unrecallable
mail to whatever address the payload carried. Two separate sessions recorded that as a ceiling and
declined to cross it -- correctly. This is the local substitute the doctrine asks for instead: the
function now reads RESEND_BASE_URL (defaulting to https://api.resend.com, so production is untouched),
and pointing it here runs every branch below the config gate exactly as production does -- the ok path,
the !ok path, the circuit breaker, the automation_log write, and whatever the function persists --
against something that cannot deliver to a human being.

It answers in Resend's shape ({"id": "..."} on 200) and KEEPS what it was sent, so a walk can assert on
the actual recipient, subject and body rather than trusting a 200.

    python tools/resend_capture_sink.py &                 # listens on 0.0.0.0:5055
    curl -s http://127.0.0.1:5055/captured                 # what has been "sent"
    curl -s -X POST http://127.0.0.1:5055/captured/clear   # reset between walks

Binds 0.0.0.0 because the caller is the edge-runtime CONTAINER, which reaches the host as
host.docker.internal -- 127.0.0.1 inside that container is the container itself. It holds no secret,
stores only what a local probe sent it, and is meant to be killed when the walk ends.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5055
CAPTURED: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
        if self.path.rstrip("/") == "/captured/clear":
            CAPTURED.clear()
            self._send(200, {"cleared": True})
            return
        try:
            sent = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            sent = {"unparsed": raw.decode("utf-8", "replace")[:2000]}
        # Resend's own idempotency header is part of what the function claims to do, so keep it.
        record = {
            "path": self.path,
            "idempotency_key": self.headers.get("Idempotency-Key"),
            "authorization_present": bool(self.headers.get("Authorization")),
            "to": sent.get("to"),
            "from": sent.get("from"),
            "subject": sent.get("subject"),
            "html_len": len(sent.get("html") or ""),
        }
        CAPTURED.append(record)
        self._send(200, {"id": f"local-capture-{len(CAPTURED):04d}"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/captured":
            self._send(200, {"count": len(CAPTURED), "captured": CAPTURED})
        else:
            self._send(200, {"ok": True, "note": "resend capture sink", "captured": len(CAPTURED)})

    def log_message(self, *_args) -> None:
        return  # quiet: the walk's own output is the record that matters


if __name__ == "__main__":
    print(f"resend capture sink listening on 0.0.0.0:{PORT} (nothing it receives can reach a person)")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
