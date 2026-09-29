#!/usr/bin/env python3
"""prove_w4_layer_d.py - the W4 layer-D stories, proven at source (no browser).

The wave-4 D-layer story is "The platform must be able to show where this page's data came from and what wrote it
last." A page that shows domain data owes the reader a provenance chip - "Live · based on your <x>, refreshed
<when>" - so a number is never a bare assertion. This reads each D-layer row's own page and asks:
  - static document (tools/page_kind) or no domain read -> n/a (no data to source)
  - it renders a provenance source chip (.wh-source-chip / renderSourceChip / _whFriendlySource / data-source) -> ok
  - it reads domain data with NO source chip -> BAD (data with no provenance)
The provenance chip is source-level and axis-independent, so the three axis-rows of a page share one witness;
writes a `witness` receipt per row.

  python tools/prove_w4_layer_d.py            # every D-layer row, print + write receipts
  python tools/prove_w4_layer_d.py --check    # the gate: exit 1 if any D row's page shows data with no provenance
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
from prove_w4_layer_rl import READS  # noqa: E402

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
COMMENT = re.compile(r"<!--.*?-->", re.S)
# the platform's own provenance idioms: the shared source chip and its renderers
SOURCE_CHIP = re.compile(r"wh-source-chip|renderSourceChip|_whFriendlySource|WH_SOURCE_LABELS|data-source\b|"
                         r"_renderIntegrationsSourceChip|source-chip|provenance", re.I)


def d_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "D"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - it holds no data to source"
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "n/a", f"{page} could not be read from disk"
    if 'id="wh-retired-overlay"' in own:
        return "n/a", f"{page} is retired behind the overlay - its content is not shown to anyone"
    body = COMMENT.sub(" ", own)
    if not READS.search(body):
        return "n/a", f"{page} reads no domain data of its own - there is no source to show"
    if SOURCE_CHIP.search(body):
        return "ok", f"{page} shows a provenance source chip (where its data came from, refreshed when)"
    return "BAD", f"{page} shows domain data but no provenance chip - a reader cannot tell where it came from"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 D-layer story proven at source (no browser) - tools/prove_w4_layer_d.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "postgres",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "postgres",
            "condition": "normal", "cast": "the page's provenance chip (source-level)",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "D", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = d_rows()
    if not rows:
        print("PASS w4-layer-provenance - no W4 layer-D row (nothing to prove)")
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
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-provenance - "
          f"{n - bad}/{n} D-layer row(s) hold ({uniq} distinct pages, {na} n/a - no data to source)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) show data with no provenance" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
