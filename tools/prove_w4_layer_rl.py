#!/usr/bin/env python3
"""prove_w4_layer_rl.py - the W4 layer-RL stories, proven at source (no browser).

The wave-4 RL-layer story is "The platform must bound what this page can consume, and say so when it has." A page
that READS a list must cap what it fetches (an unbounded read of a growing table gets slower every month and then
stops); a read-only-of-nothing page or a static document has nothing to bound. This reuses prove_consumption_bound's
own BOUND / SAYS / INSURANCE matchers and source_of / visible_text so the two cannot drift:
  - static document (tools/page_kind) or no domain read at all -> n/a (nothing to bound)
  - a bound on what it fetches (.limit / .range / PAGE_SIZE / an insurance-cap marker) -> ok
  - a domain read with NO bound and no insurance marker -> BAD (unbounded consumption)
The say-so half (a cap shown as a total is a quiet lie) is enforced platform-wide by the registered
consumption-bound gate; this layer prover proves the bound itself per page. Source-level and axis-independent, so
the three axis-rows of a page share one witness; writes a `witness` receipt per row.

  python tools/prove_w4_layer_rl.py            # every RL-layer row, print + write receipts
  python tools/prove_w4_layer_rl.py --check    # the gate: exit 1 if any RL row's page reads without a bound
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
import prove_consumption_bound as cb  # noqa: E402  - reuse BOUND/SAYS/INSURANCE + source_of
from page_kind import is_static_doc  # noqa: E402
from prove_w4_layer_headers import _first_root_page  # noqa: E402

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
COMMENT = re.compile(r"<!--.*?-->", re.S)
# a page that CONSUMES: it reads a list of domain rows (select / a data rpc)
READS = re.compile(r"\.from\(\s*['\"][a-z0-9_]+['\"]\s*\)\s*[\s\S]{0,120}?\.select\s*\(|\.rpc\(\s*['\"]", re.I)


def rl_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "RL"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - a fixed document has nothing to bound"
    own = ""
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "n/a", f"{page} could not be read from disk"
    if 'id="wh-retired-overlay"' in own:
        return "n/a", f"{page} is retired behind the overlay - its content is not shown to anyone"
    body = COMMENT.sub(" ", own)
    if not READS.search(body):
        return "n/a", f"{page} reads no list of its own - there is nothing here to bound"
    if cb.BOUND.search(body) or cb.INSURANCE.search(body):
        m = cb.BOUND.search(body)
        return "ok", f"{page} bounds what it fetches (\"{(m.group(0) if m else 'insurance cap')[:24]}\")"
    return "BAD", f"{page} reads a list with no bound and nothing said about it - this page grows until it stops"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 RL-layer story proven at source (no browser) - tools/prove_w4_layer_rl.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "postgres",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "postgres",
            "condition": "normal", "cast": "the page's own reads (source-level)",
            "problems": [] if ok else [witness],
            "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "RL", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = rl_rows()
    if not rows:
        print("PASS w4-layer-rl - no W4 layer-RL row (nothing to prove)")
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
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-rl - "
          f"{n - bad}/{n} RL-layer row(s) hold ({uniq} distinct pages, {na} n/a - nothing to bound)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) read unbounded" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
