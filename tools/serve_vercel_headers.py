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
import io
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _local_stack_pairs() -> list[tuple[bytes, bytes]]:
    """The cloud -> local Supabase URL and key, read from the local tester (test-data-seeder/app.py), which rewrites
    every page it serves the same way. One source of truth, so the two servers cannot disagree about which stack a page
    talks to."""
    try:
        src = (ROOT / "test-data-seeder" / "app.py").read_text(encoding="utf-8", errors="replace")
        g = {k: re.search(rf'^{k}\s*=\s*"([^"]+)"', src, re.M).group(1) for k in ("CLOUD_URL", "LOCAL_URL", "CLOUD_KEY", "LOCAL_KEY")}
        return [(g["CLOUD_URL"].encode(), g["LOCAL_URL"].encode()), (g["CLOUD_KEY"].encode(), g["LOCAL_KEY"].encode())]
    except (OSError, AttributeError):
        return []


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


def git_blob(ref: str, rel: str) -> bytes | None:
    """One file as it was at a commit (None when the commit has no such file)."""
    r = subprocess.run(["git", "cat-file", "blob", f"{ref}:{rel}"], cwd=ROOT, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def load_trailing(root: Path, ref: str | None = None):
    """vercel.json's trailingSlash: True (/x -> 308 /x/), False (/x/ -> 308 /x), None (no redirect either way)."""
    cfg = json.loads(git_blob(ref, "vercel.json").decode("utf-8") if ref else (root / "vercel.json").read_text(encoding="utf-8"))
    return cfg.get("trailingSlash")


def load_rules(root: Path, ref: str | None = None) -> list[tuple[re.Pattern, list[tuple[str, str]]]]:
    cfg = json.loads(git_blob(ref, "vercel.json").decode("utf-8") if ref else (root / "vercel.json").read_text(encoding="utf-8"))
    rules = []
    for rule in cfg.get("headers", []):
        rules.append((source_to_regex(rule["source"]), [(h["key"], h["value"]) for h in rule.get("headers", [])]))
    return rules


def headers_for(path: str, rules: list) -> dict[str, str]:
    """The headers the deploy sends for one request path: every matching rule, in order, later keys winning. ONE
    matcher for the server and for every prover that asks what a page will be served with (S3's CSP prover reads it
    through --resolve rather than re-deriving Vercel's matching)."""
    path = path.split("?", 1)[0].split("#", 1)[0]
    applied: dict[str, str] = {}
    for rx, headers in rules:
        if rx.match(path):
            for k, v in headers:
                applied[k] = v
    return applied


class Handler(SimpleHTTPRequestHandler):
    rules: list = []
    ref: str | None = None          # --ref: serve every file as it was at this commit (a returning device's old build)
    local_supabase = False          # --local-supabase: let the CSP reach the local stack the pages talk to
    local_stack = False             # --local-stack: also serve HTML/JS with the cloud URL+key rewritten to the local stack
    _pairs: list = []
    _blobs: dict = {}
    trailing = None                 # vercel.json trailingSlash, answered here as the edge answers it (a 308)

    def _slash_redirect(self):
        """The edge's trailing-slash 308, BEFORE any file is served (2026-10-30). true: a path with no extension and no
        trailing slash goes to the slash form (Vercel leaves /x/styles.css alone); false: a slash path goes to the bare
        form. The substitute answered neither, so a walk on it never saw the redirect production sends."""
        raw = self.path.split("?", 1)
        path, query = raw[0], ("?" + raw[1] if len(raw) > 1 else "")
        last = path.rsplit("/", 1)[-1]
        if self.trailing is True and path != "/" and not path.endswith("/") and "." not in last:
            target = path + "/"
        elif self.trailing is False and path != "/" and path.endswith("/"):
            target = path.rstrip("/")
        else:
            return False
        self.send_response(308)
        self.send_header("Location", target + query)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def send_head(self):
        if self._slash_redirect():
            return None
        # ★--local-stack: THE PAGES TALK TO THE LOCAL STACK (2026-10-16). --local-supabase only widens the CSP: every page
        # still named the PRODUCTION Supabase URL and key (the local tester on :5000 rewrites them; this server did not), so
        # a walk on this substitute signed its test cast in against production's login function (400) and every page read
        # went to production. With --local-stack, HTML and JS are served with the cloud URL and key replaced by the local
        # ones, exactly as test-data-seeder/app.py does. A separate flag, because prove_rollout.mjs serves with
        # --local-supabase and compares served bytes to the files on disk.
        if not self.ref and not self.local_stack:
            return super().send_head()
        rel = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0]).lstrip("/")
        cands = [rel or "index.html"] if not rel.endswith("/") else [rel + "index.html"]
        if rel and not rel.endswith("/"):
            cands.append(rel + "/index.html")            # trailingSlash false: /learn/x serves learn/x/index.html
        for c in cands:
            if c not in self._blobs or not self.ref:
                if self.ref:
                    self._blobs[c] = git_blob(self.ref, c)
                else:
                    p = (ROOT / c)
                    self._blobs[c] = p.read_bytes() if p.is_file() and ROOT in p.resolve().parents else None
            data = self._blobs[c]
            if data is not None and self.local_stack and c.endswith((".html", ".js", ".mjs")):
                for cloud, local in self._pairs:
                    data = data.replace(cloud, local)
            if data is not None:
                self.send_response(200)
                self.send_header("Content-Type", self.guess_type(c))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return io.BytesIO(data)
        self.send_error(404, "not in " + self.ref)
        return None

    def end_headers(self):
        applied = headers_for(self.path, self.rules)
        if self.local_supabase and "Content-Security-Policy" in applied:
            applied["Content-Security-Policy"] = applied["Content-Security-Policy"].replace(
                "connect-src", "connect-src http://127.0.0.1:54321 ws://127.0.0.1:54321", 1)
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
    ap.add_argument("--ref", help="serve every file as it was at this git commit (and that commit's vercel.json rules)")
    ap.add_argument("--local-supabase", action="store_true", help="let the CSP's connect-src reach the local stack")
    ap.add_argument("--local-stack", action="store_true",
                    help="serve HTML/JS with the production Supabase URL and key rewritten to the local stack (implies --local-supabase)")
    ap.add_argument("--resolve", nargs="+", metavar="PATH",
                    help="print, as JSON, the headers the deploy sends for each request path, and exit")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    Handler.rules = load_rules(root, a.ref)
    Handler.trailing = load_trailing(root, a.ref)
    Handler.ref, Handler.local_supabase = a.ref, a.local_supabase or a.local_stack
    Handler.local_stack, Handler._pairs = a.local_stack, (_local_stack_pairs() if a.local_stack else [])
    if a.local_stack and not Handler._pairs:
        print('--local-stack: could not read the cloud/local pairs from test-data-seeder/app.py - refusing to serve production URLs')
        return 1
    if a.resolve:
        print(json.dumps({p: headers_for(p, Handler.rules) for p in a.resolve}, ensure_ascii=False))
        return 0
    mimetypes.add_type("text/markdown", ".md")
    os.chdir(root)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"serving {('commit ' + a.ref) if a.ref else root} on http://127.0.0.1:{a.port} with {len(Handler.rules)} vercel.json header rule(s)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
