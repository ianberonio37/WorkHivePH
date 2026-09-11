#!/usr/bin/env python3
"""serve_vercel_headers.py - the LOCAL substitute for the Vercel edge's header layer (2026-09-07).

Thirty-eight trajectories sat at `fixing` with one sentence in their basis: "only Ian's deploy can make the
claim true." Their claim is that the ORIGIN sends the headers vercel.json declares - Permissions-Policy for the
microphone and camera, Cache-Control on assets, a CSP, X-Robots-Tag on ledgers. A production deploy is Ian's gate;
the CONFIG is not. This server serves the repository through vercel.json's own `headers` rules, matched the way
Vercel matches them (path-to-regexp `source` patterns, every matching rule applied in order, later keys winning),
so a prover can walk each page and each asset and read the exact response headers the deploy will ship.

    python tools/serve_vercel_headers.py [--port 5077] [--root .]

D3 local-substitute discipline: this proves the contract the deploy carries, and says so - it does not claim prod.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def source_to_regex(source: str) -> re.Pattern:
    """Vercel `source` is a path-to-regexp string: literal characters outside parentheses, regex inside them.
    A bare `.` outside a group is a literal dot (`/(.*).(js|css)` means "ends with .js or .css")."""
    out, i = [], 0
    while i < len(source):
        c = source[i]
        if c == "(":
            depth, j = 1, i + 1
            while j < len(source) and depth:
                if source[j] == "(": depth += 1
                elif source[j] == ")": depth -= 1
                j += 1
            out.append(source[i:j])          # the group, verbatim regex
            i = j
        elif c == ":":                       # :param -> one path segment
            j = i + 1
            while j < len(source) and (source[j].isalnum() or source[j] == "_"): j += 1
            out.append(r"([^/]+)"); i = j
        else:
            out.append(re.escape(c)); i += 1
    return re.compile("^" + "".join(out) + "$")


def load_rules(root: Path) -> list[tuple[re.Pattern, list[tuple[str, str]]]]:
    cfg = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
    rules = []
    for rule in cfg.get("headers", []):
        rules.append((source_to_regex(rule["source"]), [(h["key"], h["value"]) for h in rule.get("headers", [])]))
    return rules


class Handler(SimpleHTTPRequestHandler):
    rules: list = []

    def end_headers(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        applied = {}
        for rx, headers in self.rules:
            if rx.match(path):
                for k, v in headers:
                    applied[k] = v
        for k, v in applied.items():
            if k.lower() == "content-type":
                # vercel.json can override the type (markdown twins): replace the guessed one
                self._headers_buffer = [b for b in self._headers_buffer if not b.lower().startswith(b"content-type:")]
            self.send_header(k, v)
        self.send_header("X-Served-By", "serve_vercel_headers.py (local substitute for the Vercel edge)")
        super().end_headers()

    def log_message(self, fmt, *args):  # quiet
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5077)
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args()
    root = Path(a.root).resolve()
    Handler.rules = load_rules(root)
    mimetypes.add_type("text/markdown", ".md")
    os.chdir(root)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"serving {root} on http://127.0.0.1:{a.port} with {len(Handler.rules)} vercel.json header rule(s)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
