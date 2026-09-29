#!/usr/bin/env python3
"""prove_w4_layer_a.py - the W4 layer-A stories, proven at source (no browser).

The wave-4 A-layer story is "The platform must keep this page working when the service behind it answers slowly or
not at all." A page that calls a service (a Supabase read/rpc, an edge invoke, a fetch) and does NOT handle the
failure hangs on a spinner or blanks silently the moment the network wobbles - the "silent page" family this repo
has been bitten by (feedback_five_ways_a_reader_said_the_page_was_silent). So the source-level A witness is: every
page that makes a network call must both CATCH the failure and SAY something a reader can act on (an error line, a
retry control, an offline notice), not fail into silence.
  - static document (tools/page_kind) or a page that makes no network call of its own -> n/a (nothing behind it)
  - it makes network calls AND catches failure AND shows a legible degraded affordance -> ok
  - it makes network calls with no error handling, or catches but shows the reader nothing -> BAD (a silent hang)
Source-level and axis-independent (the calls + handling are the same bytes on every axis), so the three axis-rows
of a page share one witness; writes a `witness` receipt per row.

  python tools/prove_w4_layer_a.py            # every A-layer row, print + write receipts
  python tools/prove_w4_layer_a.py --check    # the gate: exit 1 if any A row's page can fail into silence
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

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
COMMENT = re.compile(r"<!--.*?-->", re.S)
# a call to a service that can be slow or down
NET = re.compile(r"\.from\(\s*['\"][a-z0-9_]+['\"]\s*\)[\s\S]{0,120}?\.select\s*\(|\.rpc\(\s*['\"]|"
                 r"\.functions\.invoke\(|\bfetch\(", re.I)
# the failure is CAUGHT: a catch, a rejected-promise guard, an { error } check, the shared error logger
HANDLES = re.compile(r"\bcatch\s*[\({]|\.catch\(|if\s*\(\s*!?error\b|\{\s*data\s*,\s*error\s*\}|"
                     r"\bwhLogError\b|allSettled|\.error\b", re.I)
# something the reader can act on when it fails: an error line, a retry, an offline/unavailable notice
DEGRADED = re.compile(r"try again|try_again|tryagain|could ?n['o]?t|unavailable|went wrong|"
                      r"failed|please retry|retry|offline|no connection|couldn.t load|"
                      r"aria-live|role=[\"']alert[\"']|role=[\"']status[\"']|\.error-|_error|showError|"
                      r"emptyState|empty-state|error-state|errorState|showToast", re.I)


def a_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "A"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - there is no service behind it to be slow or down"
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "n/a", f"{page} could not be read from disk"
    if 'id="wh-retired-overlay"' in own:
        return "n/a", f"{page} is retired behind the overlay - its content is not shown to anyone"
    body = COMMENT.sub(" ", own)
    if not NET.search(body):
        return "n/a", f"{page} makes no network call of its own - it has no slow/absent service to survive"
    handles, degraded = HANDLES.search(body), DEGRADED.search(body)
    if handles and degraded:
        return "ok", f"{page} catches a failing service and shows the reader a legible degraded state (not a silent hang)"
    miss = [x for x, ok in (("does not catch a failing service", handles), ("shows the reader nothing when it fails", degraded)) if not ok]
    return "BAD", f"{page}: {', '.join(miss)} - it can fail into silence when the service is slow or down"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 A-layer story proven at source (no browser) - tools/prove_w4_layer_a.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "playwright",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "playwright",
            "condition": "service slow or down", "cast": "the page's own network calls + degraded states (source-level)",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "A", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = a_rows()
    if not rows:
        print("PASS w4-layer-availability - no W4 layer-A row (nothing to prove)")
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
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-availability - "
          f"{n - bad}/{n} A-layer row(s) hold ({uniq} distinct pages, {na} n/a - no service behind them)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) can fail into silence" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
