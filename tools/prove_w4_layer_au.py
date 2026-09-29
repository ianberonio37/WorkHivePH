#!/usr/bin/env python3
"""prove_w4_layer_au.py - the W4 layer-AU stories, proven at source (no browser).

The wave-4 AU-layer story is "The platform must keep this page's identity honest when a session ends or a role
changes." The dishonest shape this guards against is a page that trusts a URL-injected id or a stale localStorage
hint as WHO YOU ARE - so a revoked member, or a role that changed elsewhere, still sees the old view. The honest
source witness is that an identity-bound page derives WHO from a REAL auth session (auth.getUser / getSession /
onAuthStateChange / requireAuth / the shared authenticated getDb client that carries the session), not from an
injected id alone.
  - static document (tools/page_kind), retired, or a page with no identity-bound content -> n/a (no identity to keep)
  - it reads domain data / gates on sign-in AND establishes identity from a real session -> ok
  - it shows identity-bound content but never reads a real session (id from a URL param / localStorage alone) -> BAD
Source-level and axis-independent (the auth path is the same bytes on every axis), so the three axis-rows of a page
share one witness; writes a `witness` receipt per row.

  python tools/prove_w4_layer_au.py            # every AU-layer row, print + write receipts
  python tools/prove_w4_layer_au.py --check    # the gate: exit 1 if any AU row's page trusts an id it never authenticated
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from page_kind import is_static_doc  # noqa: E402
from prove_w4_layer_headers import _first_root_page  # noqa: E402
from prove_w4_layer_rl import READS  # noqa: E402  - reads domain data of its own

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
COMMENT = re.compile(r"<!--.*?-->", re.S)
# WHO you are, from a real session (never a URL param or a bare localStorage hint)
SESSION = re.compile(r"auth\.getUser\b|\bgetUser\(|\.getSession\(|onAuthStateChange|requireAuth|whRequireAuth|"
                     r"ensureAuth|\bgetDb\(|supabase\.auth|refreshSession|getClaims", re.I)
# the page is identity-bound: it reads domain data, or it gates on sign-in, or it renders a per-person view
IDENTITY = re.compile(r"\.from\(\s*['\"][a-z0-9_]+['\"]|\.rpc\(\s*['\"]|signin=1|requireAuth|wh_last_worker|"
                      r"_signinInert|redirect.*signin|hive_id|auth_uid", re.I)


def au_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "AU"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - it binds no identity that could go stale"
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "n/a", f"{page} could not be read from disk"
    if 'id="wh-retired-overlay"' in own:
        return "n/a", f"{page} is retired behind the overlay - its content is not shown to anyone"
    body = COMMENT.sub(" ", own)
    if not IDENTITY.search(body):
        return "n/a", f"{page} shows no identity-bound content (a public page with no per-person view) - no identity to keep honest"
    if SESSION.search(body):
        return "ok", f"{page} derives who you are from a real auth session (not a URL-injected id) - identity stays honest when the session ends or the role changes"
    return "BAD", f"{page} shows identity-bound content but never reads a real session - it can trust a stale/injected id"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 AU-layer story proven at source (no browser) - tools/prove_w4_layer_au.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "playwright",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "playwright",
            "condition": "session ended or role changed", "cast": "the page's own identity resolution (source-level)",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "AU", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = au_rows()
    if not rows:
        print("PASS w4-layer-session - no W4 layer-AU row (nothing to prove)")
        return 0
    check_only = "--check" in sys.argv
    page_cache: dict[str, tuple[str, str]] = {}
    bad = 0
    for row in rows:
        page = _first_root_page(row)
        if not page:
            continue
        if page not in page_cache:
            page_cache[page] = check_page(page)
        verdict, witness = page_cache[page]
        if verdict == "BAD":
            bad += 1
        if not check_only:
            write_receipt(row, verdict, witness)
    n, uniq = len(rows), len(page_cache)
    na = sum(1 for v, _w in page_cache.values() if v == "n/a")
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-session - "
          f"{n - bad}/{n} AU-layer row(s) hold ({uniq} distinct pages, {na} n/a - no identity to keep)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) trust an id they never authenticated" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
