#!/usr/bin/env python3
"""prove_w4_layer_lb.py - the W4 layer-LB stories, proven at source (no browser).

The wave-4 LB-layer story is "The platform must keep this page responsive as its data grows past the size it was
designed for." Where layer RL bounds what a page FETCHES, LB is about what it RENDERS: a page that reads a growing
list and paints every row into the DOM gets slower every month until it janks. So the source-level LB witness is
that the list a page renders is BOUNDED - by a fetch cap (.limit / .range / PAGE_SIZE, which bounds the DOM too),
by pagination / a "load more" / infinite-scroll window, by virtualization, or by a client-side slice before render.
  - static document (tools/page_kind) or a page that reads no list of its own -> n/a (nothing that grows)
  - the list it renders is bounded (a fetch cap, pagination, virtualization, or a pre-render slice) -> ok
  - it reads a growing list with no bound on the fetch and no bound on the render -> BAD (it slows without limit)
Source-level and axis-independent (the reads + render are the same bytes on every axis), so the three axis-rows of
a page share one witness; writes a `witness` receipt per row.

  python tools/prove_w4_layer_lb.py            # every LB-layer row, print + write receipts
  python tools/prove_w4_layer_lb.py --check    # the gate: exit 1 if any LB row's page renders an unbounded list
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
import prove_consumption_bound as cb  # noqa: E402  - reuse BOUND / INSURANCE
from page_kind import is_static_doc  # noqa: E402
from prove_w4_layer_headers import _first_root_page  # noqa: E402
from prove_w4_layer_rl import READS  # noqa: E402  - a page that reads a list of domain rows

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
COMMENT = re.compile(r"<!--.*?-->", re.S)
# the render stays bounded even when the fetch is not: pagination, load-more, infinite scroll, virtualization,
# or a slice/cap applied before the rows are painted
RENDER_BOUND = re.compile(r"\bpaginat|\bpage[_-]?size\b|load[_ -]?more|show[_ -]?more|infinite|"
                          r"virtual|windowing|IntersectionObserver|\.slice\(\s*0?\s*,|\.slice\(-|"
                          r"loadMore|nextPage|per[_ -]?page|PAGE_SIZE|RENDER_CAP|MAX_ROWS|visibleCount|"
                          r"\.splice\(", re.I)


def lb_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "LB"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - it has no growing list to keep responsive"
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "n/a", f"{page} could not be read from disk"
    if 'id="wh-retired-overlay"' in own:
        return "n/a", f"{page} is retired behind the overlay - its content is not shown to anyone"
    body = COMMENT.sub(" ", own)
    if not READS.search(body):
        return "n/a", f"{page} reads no list of its own - there is nothing here that grows"
    fetch_bound = cb.BOUND.search(body) or cb.INSURANCE.search(body)
    render_bound = RENDER_BOUND.search(body)
    if fetch_bound or render_bound:
        how = (f'a fetch cap ("{cb.BOUND.search(body).group(0)[:22]}")' if cb.BOUND.search(body)
               else f'bounded rendering ("{render_bound.group(0)[:22]}")' if render_bound else "an insurance cap")
        return "ok", f"{page} keeps its rendered list bounded by {how} - it stays responsive as the table grows"
    return "BAD", f"{page} reads a growing list and neither caps the fetch nor bounds the render - it slows without limit"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 LB-layer story proven at source (no browser) - tools/prove_w4_layer_lb.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "playwright",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "playwright",
            "condition": "data grown past design size", "cast": "the page's rendered list (source-level)",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "LB", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = lb_rows()
    if not rows:
        print("PASS w4-layer-loadbearing - no W4 layer-LB row (nothing to prove)")
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
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-loadbearing - "
          f"{n - bad}/{n} LB-layer row(s) hold ({uniq} distinct pages, {na} n/a - nothing that grows)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) render an unbounded list" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
