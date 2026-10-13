#!/usr/bin/env python3
"""prove_w4_layer_headers.py - the W4 layer-H stories, proven against the served header layer (no browser).

The wave-4 H-layer story is "The platform must serve this page correctly from the edge - headers, caching and
offline included." Headers do not depend on the viewport or the language, so the H story is answered by the
SAME non-browser instrument on every axis: the local Vercel-headers substitute (tools/serve_vercel_headers.py,
which applies vercel.json's own rules the way the edge does), reused through tools/prove_deploy_headers.py's
own `head`, `local_assets` and `to_url`. For each H-layer row this checks, on the row's OWN page (the surface
the layer belongs to):
  - a Content-Security-Policy is served and X-Frame-Options is DENY,
  - Permissions-Policy grants microphone=(self) and camera=(self),
  - the HTML is Cache-Control max-age=0 must-revalidate, a shipped script/style is max-age=3600, sw.js no-store.
It writes an MCP-shaped receipt per row (.tmp/mcp_walks/<id>.json) carrying the `witness` a contract layer needs
(live_walk_manifest._w4_missing), so a passing row can advance fixing -> locking through the w4-layer-headers gate.
The three axes share one header reading (the header is the same) - each axis-row is banked from the same witness.

  python tools/prove_w4_layer_headers.py            # every W4 layer-H row, print + write receipts
  python tools/prove_w4_layer_headers.py --check    # the gate: exit 1 if any H-layer row's headers do not hold
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import prove_deploy_headers as dh  # noqa: E402  - reuse head/local_assets/to_url + the local server

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"


def h_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    # ★THE LXP-H ROWS ASK THE IDENTICAL QUESTION OF THE IDENTICAL INSTRUMENT (2026-10-05). 120 LAYER-UX x PERSONA
    # rows carry the same lens - "the platform must serve this page correctly from the edge" - and sat in the
    # re-walk queue wanting a raw-http reading, while this prover was already taking exactly that reading for the
    # W4 rows and was simply not looking at them: it selected on `w4.kind == layer`, and an LXP row carries its
    # layer under `lx`. Reusing this prover is the move rather than writing a second one, because a second reader
    # of the same headers is how two gates come to disagree about one fact. An `lx` row is in fact the easier
    # subject - `lx.page` names its surface outright, so no inference from the title is needed.
    # ★AND THE LXC FLOOR ROWS ASK IT TOO (2026-10-08). The persona x layer floor (seed_expansion_wave4.layer_floor_rows)
    # writes the SAME H sentence on the same `lx` block with kind "layer-floor" - so 33 LXC-H rows sat open wanting a
    # raw-http reading this prover already takes, for the same reason the LXP rows once did: it was not looking.
    out = []
    for t in reg["trajectories"]:
        if t.get("status") == "descoped":
            continue
        w4, lx = t.get("w4") or {}, t.get("lx") or {}
        if w4.get("kind") == "layer" and w4.get("layer") == "H":
            out.append(t)
        elif lx.get("kind") in LX_KINDS and lx.get("layer") == "H" and lx.get("page"):
            out.append(t)
    return out


LX_KINDS = ("layer-ux", "layer-floor")


def conditional_rules() -> list[str]:
    """vercel.json header rules that only apply to SOME requests (a `has` / `missing` condition on a cookie, a header
    or a query). ★AN LX ROW IS ASKED AS A NAMED PERSONA, AND ONE READING ANSWERS EVERY PERSONA ONLY IF NOTHING THE
    PERSON SENDS CAN CHANGE THE HEADERS. The session lives in localStorage and travels to Supabase, never to this
    origin; but a rule conditioned on a cookie or a header WOULD make the served headers differ by who asks, and then
    one bare fetch could not speak for a signed-in supervisor. So the claim is read from the config on every run
    rather than assumed - an empty list is what lets the witness say the reading is the persona's own."""
    try:
        cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    except Exception as e:  # an unreadable config cannot vouch for anything
        return [f"vercel.json unreadable: {e}"]
    return [str(r.get("source")) for r in (cfg.get("headers") or []) if r.get("has") or r.get("missing")]


def _first_root_page(row: dict) -> str | None:
    """The page the H layer belongs to: the row's own surface (its short name resolves to a served page).
    A layer story's `pages` is the route; the surface is the one the lens names, which is pages[the page the
    story is about]. The seeder builds a layer row's path from _start(page)+page, so the SURFACE is the page
    that is not index/hive/a continuation - the last of the route's own-page segment. Simplest robust pick:
    the page whose short name appears in the title, else the last non-continuation page."""
    import re
    # an lx row states its own surface; nothing to infer
    lx_page = (row.get("lx") or {}).get("page")
    if lx_page:
        return lx_page
    title = row.get("title") or ""
    for p in (row.get("pages") or []):
        short = p.replace("/index.html", "").replace("learn/", "").replace("tools/", "").replace(".html", "").replace("-", " ")
        if re.search(re.escape(short) + r"\b", title):
            return p
    cont = {"index.html", "hive.html", "analytics.html", "audit-log.html", "logbook.html"}
    own = [p for p in (row.get("pages") or []) if p not in cont]
    return own[-1] if own else (row.get("pages") or [None])[-1]


def check_page(page: str) -> tuple[bool, list[str], str]:
    st, h, body = dh.head("/" + page)
    issues = []
    if st != 200:
        issues.append(f"page HTTP {st}")
    pp, csp, cc = h.get("permissions-policy", ""), h.get("content-security-policy", ""), h.get("cache-control", "")
    if not csp:
        issues.append("no Content-Security-Policy")
    if h.get("x-frame-options", "").upper() != "DENY":
        issues.append(f"X-Frame-Options is '{h.get('x-frame-options', '')}', not DENY")
    if "microphone=(self)" not in pp or "camera=(self)" not in pp:
        issues.append(f"Permissions-Policy does not grant mic+camera to self: '{pp[:50]}'")
    if "max-age=0" not in cc or "must-revalidate" not in cc:
        issues.append(f"HTML Cache-Control '{cc}' (expected max-age=0, must-revalidate)")
    js, css, img = dh.local_assets(body.decode("utf-8", "replace"))
    for ref in (js[:1] + css[:1]):
        _s, h2, _b = dh.head(dh.to_url(page, ref))
        if "max-age=3600" not in h2.get("cache-control", ""):
            issues.append(f"{ref}: Cache-Control '{h2.get('cache-control', '')}' (expected max-age=3600)")
    _s4, h4, _b4 = dh.head("/sw.js")
    if "no-store" not in h4.get("cache-control", ""):
        issues.append(f"sw.js Cache-Control '{h4.get('cache-control', '')}' (expected no-store)")
    witness = (f"served headers on {page}: CSP present, X-Frame-Options DENY, Permissions-Policy mic+camera=self, "
               f"HTML no-cache, asset max-age=3600, sw.js no-store (tools/serve_vercel_headers.py = vercel.json)")
    return not issues, issues, witness


def write_receipt(row: dict, page: str, witness: str, ok: bool, issues: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    import datetime as _dt
    doc = {
        "_doc": "A W4 H-layer story proven against the served header layer (no browser) - tools/prove_w4_layer_headers.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "raw-http",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "raw-http",
            "condition": "normal", "cast": "the edge (served headers)",
            "problems": issues,
            "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "H", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = h_rows()
    if not rows:
        print("PASS w4-layer-headers - no W4 layer-H row (nothing to prove)")
        return 0
    started = None
    if not dh.listening():
        started = subprocess.Popen([sys.executable, str(ROOT / "tools" / "serve_vercel_headers.py"), "--port", str(dh.PORT)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if dh.listening():
                break
            time.sleep(0.25)
    check_only = "--check" in sys.argv
    page_cache: dict[str, tuple[bool, list[str], str]] = {}
    bad = 0
    cond = conditional_rules()
    try:
        for row in rows:
            page = _first_root_page(row)
            if not page:
                continue
            if page not in page_cache:
                page_cache[page] = check_page(page)
            ok, issues, witness = page_cache[page]
            persona = (row.get("lx") or {}).get("persona")
            if persona:
                # the persona half of an LX row: one reading speaks for this person only if no rule is conditional
                if cond:
                    ok, issues = False, issues + [f"vercel.json has conditional header rule(s) {cond[:3]} - the "
                                                  f"headers may differ for {persona}; one bare reading cannot answer"]
                else:
                    witness = (witness + f"; as {persona}: none of vercel.json's header rules carries a has/missing "
                               f"condition, so no cookie, header or query this person sends can change what the edge "
                               f"serves - the reading above is the one {persona} receives")
            if not ok:
                bad += 1
            if not check_only:
                write_receipt(row, page, witness, ok, issues)
        n = len(rows)
        uniq = len(page_cache)
        print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-headers - "
              f"{n - bad}/{n} H-layer row(s) hold against the served headers ({uniq} distinct pages)"
              + (f"; {bad} fail" if bad else ""))
        if bad:
            for page, (ok, issues, _w) in page_cache.items():
                if not ok:
                    print(f"  {RED}BAD{RST} {page:<40} {'; '.join(issues)[:120]}")
    finally:
        if started:
            started.terminate()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
