#!/usr/bin/env python3
"""validate_sw_proxy_within_csp.py - every host the service worker fetches for a page must be one sw.js's OWN CSP lets
it reach (2026-10-16).

Found by the 2026-10-16 post-deploy smoke, the first one run with the worker allowed: on every page the worker
controlled, the Poppins stylesheet answered **503, served by the worker** (about, feedback, privacy, learn, hive, the
sign-in page). sw.js passed Google Fonts through `e.respondWith(fetch(e.request).catch(() => 503))`. A worker's
fetch() is governed by the Content-Security-Policy sent WITH sw.js - its connect-src - not by the page's policy, and
the policy vercel.json sends for /sw.js names neither fonts.googleapis.com nor fonts.gstatic.com. So the fetch was
refused every time and every returning visitor, every installed phone, read the platform in the fallback font. The
page's own style-src / font-src always allowed the fonts; no gate looked at the worker's policy, because nothing
treated the worker as a client with a policy of its own.

The rule: for every `e.respondWith(fetch(...))` branch in sw.js, each host its condition names
(`url.includes('<host>')`) must be allowed by the connect-src (or default-src) that vercel.json's header rules send for
/sw.js - matched the way Vercel matches them (tools/serve_vercel_headers.py's own matcher, not a re-derivation). A
branch that `return`s without respondWith is not a proxy: the browser fetches under the page's policy.

    python tools/validate_sw_proxy_within_csp.py              # the gate
    python tools/validate_sw_proxy_within_csp.py --self-test  # fixtures + teeth on sw.js as shipped in 44bedbdd
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import serve_vercel_headers as svh  # noqa: E402

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_LINE = re.compile(r"(?m)(?<![:\"'`\\/])//[^\n]*$")
_BRANCH = re.compile(r"if\s*\(([^{};]*)\)\s*\{\s*e\.respondWith\(\s*fetch\(")
_HOST = re.compile(r"""\.(?:includes|startsWith)\(\s*['"]([^'"/][^'"]*\.[^'"]*)['"]\s*\)""")


def proxied_hosts(sw_text: str) -> list[str]:
    """Hosts named in the condition of every branch that answers with a straight network fetch()."""
    text = _LINE.sub("", _BLOCK.sub(" ", sw_text))
    hosts: list[str] = []
    for m in _BRANCH.finditer(text):
        for h in _HOST.findall(m.group(1)):
            if h not in hosts:
                hosts.append(h)
    return hosts


# ★THE CATCH-ALL WAS A PROXY TOO (2026-10-26, the first signed-in production smoke). The rule above looked only at
# branches that answer with a straight fetch(); the cache-first branch at the bottom also fetches whatever reaches it,
# and cross-origin library scripts (Chart.js, html2pdf, Mermaid from cdn.jsdelivr.net / cdnjs.cloudflare.com) did -
# 503 on every returning visit. So: sw.js must leave a cross-origin request to the browser unless its host is in
# WORKER_REACHABLE, and every host in that list is a host the worker proxies, held to the same connect-src.
_REACHABLE = re.compile(r"const\s+WORKER_REACHABLE\s*=\s*\[([^\]]*)\]")
_GUARD = re.compile(r"origin\s*!==\s*self\.location\.origin\s*&&\s*!WORKER_REACHABLE\.some\(")


def reachable_hosts(sw_text: str) -> list[str]:
    text = _LINE.sub("", _BLOCK.sub(" ", sw_text))
    m = _REACHABLE.search(text)
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if m else []


def catchall_guarded(sw_text: str) -> bool:
    return _GUARD.search(_LINE.sub("", _BLOCK.sub(" ", sw_text))) is not None


def worker_connect_sources(ref: str | None = None) -> list[str]:
    """The connect-src (falling back to default-src) production sends with /sw.js."""
    rules = svh.load_rules(ROOT, ref)
    csp = ""
    for k, v in svh.headers_for("/sw.js", rules).items():
        if k.lower() == "content-security-policy":
            csp = v
    directives = {d.strip().split(" ", 1)[0]: d.strip().split()[1:] for d in csp.split(";") if d.strip()}
    return directives.get("connect-src", directives.get("default-src", []))


def misses(hosts: list[str], sources: list[str]) -> list[str]:
    return [h for h in hosts if not any(h in s for s in sources)]


def check() -> int:
    sw = io.open(ROOT / "sw.js", encoding="utf-8").read()
    hosts = proxied_hosts(sw) + [h for h in reachable_hosts(sw) if h not in proxied_hosts(sw)]
    if not catchall_guarded(sw):
        print("FAIL sw-proxy-within-csp: sw.js lets a cross-origin request reach its cache-first fetch() without the "
              "WORKER_REACHABLE guard - a library from a CDN the worker's own connect-src does not name answers 503 "
              "(2026-10-26: Chart.js, html2pdf, Mermaid). Leave cross-origin requests to the browser unless reachable.")
        return 1
    sources = worker_connect_sources()
    if not sources:
        print("FAIL sw-proxy-within-csp: vercel.json sends no connect-src or default-src with /sw.js - cannot judge")
        return 1
    bad = misses(hosts, sources)
    for h in bad:
        print(f"FAIL sw-proxy-within-csp: sw.js answers requests to '{h}' with its own fetch(), but the CSP production "
              f"sends with /sw.js does not allow it in connect-src - the worker's fetch is refused and the page gets "
              f"the worker's fallback (503). Stop intercepting it, or allow it in that policy.")
    if bad:
        return 1
    print(f"PASS sw-proxy-within-csp - the worker proxies {len(hosts)} host(s) ({', '.join(hosts) or 'none'}), "
          f"each allowed by the connect-src sent with /sw.js")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    two = ("self.addEventListener('fetch', e => { const url = e.request.url;\n"
           "  if (url.includes('supabase.co') || url.includes('fonts.goog')) {\n"
           "    e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 }))); return; } });")
    t("a pass-through branch's hosts are read", proxied_hosts(two) == ["supabase.co", "fonts.goog"])
    skip = ("self.addEventListener('fetch', e => { const url = e.request.url;\n"
            "  if (url.includes('fonts.googleapis.com')) return;\n"
            "  if (url.includes('supabase.co')) { e.respondWith(fetch(e.request)); return; } });")
    t("a host the worker returns on is not a proxy", proxied_hosts(skip) == ["supabase.co"])
    t("a commented-out branch is not read",
      proxied_hosts("/* if (url.includes('x.com')) { e.respondWith(fetch(e.request)) } */") == [])
    src = ["'self'", "https://abc.supabase.co", "wss://abc.supabase.co"]
    t("a host inside connect-src passes; one outside it is named", misses(["supabase.co", "fonts.goog"], src) == ["fonts.goog"])
    t("the real vercel.json sends /sw.js a connect-src that allows the project's Supabase",
      any("supabase.co" in s for s in worker_connect_sources()))
    # teeth: sw.js as it shipped in 44bedbdd proxied the font hosts under a policy that refused them
    old = subprocess.run(["git", "show", "44bedbdd:sw.js"], cwd=ROOT, capture_output=True)
    t("teeth: sw.js as shipped in 44bedbdd is caught on both font hosts",
      old.returncode == 0 and misses(proxied_hosts(old.stdout.decode("utf-8", "replace")),
                                     worker_connect_sources("44bedbdd")) == ["fonts.goog", "fonts.gstatic"])
    # teeth: sw.js as it shipped in release 27733934 let CDN library scripts reach the catch-all fetch
    rel = subprocess.run(["git", "show", "27733934:sw.js"], cwd=ROOT, capture_output=True)
    t("teeth: sw.js as shipped in 27733934 has no cross-origin guard before its catch-all fetch",
      rel.returncode == 0 and not catchall_guarded(rel.stdout.decode("utf-8", "replace")))
    t("a guarded catch-all is read as guarded, and its reachable hosts are read",
      catchall_guarded("if (new URL(url).origin !== self.location.origin && !WORKER_REACHABLE.some((h) => url.includes(h))) return;")
      and reachable_hosts("const WORKER_REACHABLE = ['a.example', \"b.example\"];") == ["a.example", "b.example"])
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else check())
