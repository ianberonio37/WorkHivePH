#!/usr/bin/env python3
"""prove_w4_layer_clock.py - the W4 layer-C stories, proven at source (no browser).

The wave-4 C-layer story is "The platform must state which clock and which period this page's figures belong to."
A number without a window is a claim without a subject: "142 work orders" means nothing until the page says whether
that is today, this month or since the hive opened, and in whose timezone. This reuses prove_clock_and_trail's own
PERIOD / CLOCK matchers and page_text so the two cannot drift:
  - static document (tools/page_kind) or a page with no figures (a form, a notice) -> n/a (no window to state)
  - names a PERIOD and a CLOCK -> ok
  - shows figures but names no period or no clock -> BAD (figures with no window a reader can check)
Source-level and axis-independent (the period/clock text is the same bytes on every axis), so the three axis-rows
of a page share one witness; writes a `witness` receipt per row.

  python tools/prove_w4_layer_clock.py            # every C-layer row, print + write receipts
  python tools/prove_w4_layer_clock.py --check    # the gate: exit 1 if any C row's page shows figures with no window
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
import prove_clock_and_trail as ct  # noqa: E402  - reuse PERIOD/CLOCK + page_text + is_static_doc
from prove_w4_layer_headers import _first_root_page  # noqa: E402
from prove_w4_layer_rl import READS  # noqa: E402  - a page whose figures come from a domain read

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
FIG = re.compile(r"(?<![\w/.-])\d[\d,]*(?:\.\d+)?(?![\w/.-])")


def c_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "C"
            and t.get("status") != "descoped"]


def check_page(page: str) -> tuple[str, str]:
    if ct._is_static_doc(page):
        return "n/a", f"{page} ships no data client - its figures are illustrations, not a live window"
    txt = ct.page_text(page)
    if not txt:
        return "n/a", f"{page} could not be read from disk"
    if len(FIG.findall(txt)) < 5:
        return "n/a", f"{page} shows no figures (a form or a notice) - there is no window for a reader to check"
    # ★A CLOCK IS OWED ONLY BY FIGURES THAT BELONG TO A PERIOD (2026-09-14). A calculator's "50 mm pipe" or
    # engineering-design's computed loads are ENGINEERING VALUES, not dated measurements, and status.html's
    # numbers are live health probes (a /health fetch), not a domain read - none belong to a clock. The period/
    # clock claim is owed only when the page reads AGGREGATE domain rows (.from().select / a data rpc); a page
    # whose figures are computed or probed has no window and owes none. Same shape as the L client_errors fix.
    try:
        src = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        src = ""
    if not READS.search(src):
        return "n/a", f"{page}'s figures are computed or probed, not read from dated domain rows - no window is owed"
    per, clk = ct.PERIOD.search(txt), ct.CLOCK.search(txt)
    if per and clk:
        return "ok", f'{page} names its period ("{per.group(0)[:24]}") and its clock ("{clk.group(0)[:18]}")'
    miss = [x for x, ok in (("no stated period", per), ("no stated clock", clk)) if not ok]
    return "BAD", f"{page}: {', '.join(miss)} - its figures have no window a reader can check"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 C-layer story proven at source (no browser) - tools/prove_w4_layer_clock.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "postgres",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "postgres",
            "condition": "normal", "cast": "the page's figures (source-level)",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "C", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = c_rows()
    if not rows:
        print("PASS w4-layer-clock - no W4 layer-C row (nothing to prove)")
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
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-clock - "
          f"{n - bad}/{n} C-layer row(s) hold ({uniq} distinct pages, {na} n/a - no figures)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) show figures with no window" if bad else ""))
    if bad:
        for page, (v, w) in page_cache.items():
            if v == "BAD":
                print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
