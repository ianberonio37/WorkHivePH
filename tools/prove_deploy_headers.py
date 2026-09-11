#!/usr/bin/env python3
"""prove_deploy_headers.py - the 38 deploy-gated rows, walked against the header layer the deploy will ship.

Rows (LX-H + P-E, all `fixing` with "only Ian's deploy can make the claim true"):
  "_headers is prod-only - <page>"            the header CONTRACT on the page: CSP, Permissions-Policy, X-Frame-Options,
                                              Cache-Control for HTML (max-age=0, must-revalidate)
  "A feature that works locally is dead in production because the origin sends no header for ..."
                                              Permissions-Policy names microphone=(self) and camera=(self) on the page
  "An asset is re-downloaded every visit because the deployed origin never told the browser ..."
                                              Cache-Control on a script/stylesheet the page ships (max-age=3600) and on an
                                              image/icon (max-age=31536000, immutable); sw.js is no-store

Served by tools/serve_vercel_headers.py, which applies vercel.json's own rules the way the Vercel edge does. This
proves the CONTRACT the deploy carries (the local-substitute half); the production half is the deploy itself.

    python tools/prove_deploy_headers.py            # starts the local server if :5077 is not listening
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 5077
BASE = f"http://127.0.0.1:{PORT}"
REPORT = ROOT / "deploy_headers_report.json"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"


def listening() -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def head(path: str):
    req = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read(200_000)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, b""
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)[:120]}, b""


def rows():
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    out = []
    for t in reg["trajectories"]:
        title = t.get("title") or ""
        page = (t.get("pages") or [None])[0]
        if not page:
            continue
        if title.startswith("_headers is prod-only"):
            out.append((t["id"], page, "contract"))
        elif title.startswith("A feature that works locally is dead in production"):
            out.append((t["id"], page, "permissions"))
        elif title.startswith("An asset is re-downloaded every visit"):
            out.append((t["id"], page, "cache"))
    return out


def local_assets(html: str):
    js = re.findall(r"""<script[^>]+src=["']([^"'?#]+\.js)""", html)
    css = re.findall(r"""<link[^>]+href=["']([^"'?#]+\.css)""", html)
    img = re.findall(r"""(?:src|href)=["']([^"'?#]+\.(?:png|svg|ico|webp|jpg|jpeg))""", html)
    keep = lambda xs: [x for x in xs if not x.startswith(("http://", "https://", "//"))]
    return keep(js), keep(css), keep(img)


def to_url(page: str, ref: str) -> str:
    if ref.startswith("/"):
        return ref
    base = "/" + page.rsplit("/", 1)[0] + "/" if "/" in page else "/"
    return (base + ref).replace("//", "/")


def main() -> int:
    started = None
    if not listening():
        started = subprocess.Popen([sys.executable, str(ROOT / "tools" / "serve_vercel_headers.py"), "--port", str(PORT)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if listening():
                break
            time.sleep(0.25)
    results, bad = [], 0
    try:
        for rid, page, lens in rows():
            st, h, body = head("/" + page)
            issues = []
            if st != 200:
                issues.append(f"page HTTP {st}")
            pp = h.get("permissions-policy", "")
            csp = h.get("content-security-policy", "")
            cc = h.get("cache-control", "")
            if lens in ("contract", "permissions"):
                if "microphone=(self)" not in pp or "camera=(self)" not in pp:
                    issues.append(f"Permissions-Policy does not grant mic+camera to self: '{pp[:60]}'")
            if lens == "contract":
                if not csp:
                    issues.append("no Content-Security-Policy")
                if h.get("x-frame-options", "").upper() != "DENY":
                    issues.append("X-Frame-Options is not DENY")
                if "max-age=0" not in cc or "must-revalidate" not in cc:
                    issues.append(f"HTML Cache-Control is '{cc}' (expected max-age=0, must-revalidate)")
            if lens == "cache":
                js, css, img = local_assets(body.decode("utf-8", "replace"))
                if not (js or css):
                    issues.append("the page ships no local script or stylesheet to check")
                for ref in (js[:1] + css[:1]):
                    s2, h2, _ = head(to_url(page, ref))
                    c2 = h2.get("cache-control", "")
                    if "max-age=3600" not in c2:
                        issues.append(f"{ref}: Cache-Control '{c2}' (expected max-age=3600, must-revalidate)")
                for ref in img[:1]:
                    s3, h3, _ = head(to_url(page, ref))
                    c3 = h3.get("cache-control", "")
                    if "max-age=31536000" not in c3 or "immutable" not in c3:
                        issues.append(f"{ref}: Cache-Control '{c3}' (expected a year, immutable)")
                s4, h4, _ = head("/sw.js")
                if "no-store" not in h4.get("cache-control", ""):
                    issues.append(f"sw.js Cache-Control '{h4.get('cache-control', '')}' (expected no-store)")
            ok = not issues
            bad += 0 if ok else 1
            results.append({"id": rid, "page": page, "lens": lens, "ok": ok, "issues": issues})
            print(f"  {GREEN + 'ok ' if ok else RED + 'BAD'}{RST} {rid:<6} {lens:<12} {page:<36} {'; '.join(issues)[:110]}")
    finally:
        if started:
            started.terminate()
    n = len(results)
    REPORT.write_text(json.dumps({"served_by": "tools/serve_vercel_headers.py (vercel.json applied locally)", "rows": results}, indent=1), encoding="utf-8")
    print(f"{GREEN + 'PASS' if not bad else RED + 'FAIL'}{RST} deploy-headers-local - {n - bad}/{n} deploy-gated row(s) hold against the header layer vercel.json ships "
          f"(the local substitute for the Vercel edge; production is the deploy itself)")
    return 1 if bad or n == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
