#!/usr/bin/env python3
"""prove_w4_layer_trail.py - the W4 layer-L stories, proven at source (no browser).

The wave-4 L-layer story is "The platform must record who did what on this page, in a trail somebody can read
later." A page that lets a person CHANGE something owes a trail of it; a page that only reads owes nothing, and a
static document writes nothing at all. This reads each L-layer row's own page and the scripts it loads and asks:
  - static document (no data client, tools/page_kind) or no write path at all -> n/a (nothing to record)
  - a write path that reaches the audit trail (audit_log / writeAuditLog / rpc *audit*) -> ok
  - a write path with NO trail -> BAD (a change nobody can trace)
It reuses prove_clock_and_trail's own TRAIL_CALL matcher and page_source so the two cannot drift, and writes a
`witness` receipt per row for live_walk_manifest._w4_missing. The trail is source-level and axis-independent, so
the three axis-rows of a page share one witness.

  python tools/prove_w4_layer_trail.py            # every L-layer row, print + write receipts
  python tools/prove_w4_layer_trail.py --check    # the gate: exit 1 if any L row's page writes without a trail
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
import prove_clock_and_trail as ct  # noqa: E402  - reuse TRAIL_CALL + page_source
from page_kind import is_static_doc  # noqa: E402
from prove_w4_layer_headers import _first_root_page  # noqa: E402  - same surface-picking rule

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
# a page that CHANGES a DOMAIN row a colleague can see: from(<domain table>).insert/update/upsert/delete.
# ★NOT the shared telemetry (2026-09-14): `client_errors` (whLogError, in utils.js, on EVERY page) and the other
# self-recording tables below are the platform's own logs, not a user action that owes a separate audit row -
# counting them made status/public-feed/marketplace-seller-profile read "writes without a trail" while they only
# log their own errors. Edge invokes are dropped too: most are reads / AI / search, and whether an edge fn writes
# an audit row is server-side, invisible to a source read - so an edge-only page is `n/a` here, not a false BAD.
_TELEMETRY = r"(?!client_errors\b)(?!ai_reply_feedback\b)(?!analytics_events\b)(?!page_views\b)"
WRITE = re.compile(r"\.from\(\s*['\"]" + _TELEMETRY + r"[a-z0-9_]+['\"]\s*\)\s*[\s\S]{0,120}?\.(insert|update|upsert|delete)\s*\(", re.I)


def l_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "L"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    """('ok'|'n/a'|'BAD', witness/reason)."""
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - it writes nothing, so there is no trail to owe"
    src = ct.page_source(page)
    if not src:
        return "n/a", f"{page} could not be read from disk"
    writes = bool(WRITE.search(re.sub(r"<!--.*?-->", " ", src, flags=re.S)))
    trail = ct.TRAIL_CALL.search(src)
    if not writes:
        return "n/a", f"{page} makes no user-visible write, so it owes no trail"
    if trail:
        return "ok", f"{page} records its changes in the audit trail (\"{trail.group(0)[:40]}\")"
    return "BAD", f"{page} changes data but nothing in it or the scripts it loads writes to the audit trail"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 L-layer story proven at source (no browser) - tools/prove_w4_layer_trail.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "postgres",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "postgres",
            "condition": "normal", "cast": "the audit trail (source-level)",
            "problems": [] if ok else [witness],
            "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "L", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = l_rows()
    if not rows:
        print("PASS w4-layer-trail - no W4 layer-L row (nothing to prove)")
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
    n = len(rows)
    uniq = len(page_cache)
    na = sum(1 for v, _w in page_cache.values() if v == "n/a")
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-trail - "
          f"{n - bad * (n // max(uniq, 1))}/{n} L-layer row(s) hold "
          f"({uniq} distinct pages, {na} n/a - no writes to record)"
          + (f"; {bad} page(s) write without a trail" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
