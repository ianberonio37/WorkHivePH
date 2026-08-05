#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BANK ROWS FROM A LIVE MCP WALK — the only instrument allowed to produce `live-walk` evidence
═══════════════════════════════════════════════════════════════════════════════════════════════════

Ian's anti-drift rule, stated 2026-08-04 and restated 2026-08-05: **live-MCP only for `live-walk`;
headless may triage, never bank.** A headless spec and a live MCP walk are not interchangeable
evidence — the headless run is a gate that locks behaviour in CI, while the walk is a person driving
the real browser and reading the real screen. The bank's `live-walk` rows claim the latter.

So this reads readings captured during an actual MCP browser session — `.tmp/live_walk.json`, a list
of

    {"category": "...", "state": "...", "surface": "...", "url": "...",
     "ok": true, "checked": ["...", "..."], "notes": ""}

— and writes them, with the gate's own classify() run before each row is kept, exactly as the other
bankers do. Anything the gate would call invalid goes back.

A reading with "ok": false is written OWED, carrying its notes. A state with no reading is untouched.

Run:  python tools/bank_live_walk.py            # dry run
      python tools/bank_live_walk.py --apply
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READINGS = os.path.join(ROOT, ".tmp", "live_walk.json")
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

PAGES = {
    "market": "marketplace.html", "market_svc": "marketplace.html",
    "seller": "marketplace-seller.html", "admin": "platform-actions.html",
    "profile": "marketplace-seller-profile.html", "community": "community.html",
    "public-feed": "public-feed.html",
}


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    if not os.path.exists(READINGS):
        print(f"  {RED}FAIL{RST} — {READINGS} not found. Capture the walk first.")
        return 1
    readings = json.load(open(READINGS, encoding="utf-8"))
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    today = date.today().isoformat()

    # A reading may name a specific category, or "*" for "whatever category holds this (state,
    # surface) cell". The lens walk produces the latter: `populated` on the seller surface is claimed
    # by several families at once, and the lens settled the property, not one family's copy of it.
    index, wild = {}, {}
    for r in readings:
        if r["category"] == "*":
            wild[(r["state"], r["surface"])] = r
        else:
            index[(r["category"], r["state"], r["surface"])] = r

    banked = failed = unmatched = 0
    misses = []
    for row in rows:
        key = (row.get("category"), row.get("state"), row.get("surface"))
        rd = index.get(key) or wild.get((row.get("state"), row.get("surface")))
        if rd is None:
            continue
        if not rd.get("ok"):
            row["status"] = "owed"
            row["findings"] = [f"live MCP walk {today} — {rd.get('url','')}: {rd.get('notes') or 'failed'}"]
            failed += 1
            misses.append((key, (rd.get("notes") or "")[:100]))
            continue
        page = PAGES.get(row.get("surface"))
        deps = sorted({page, "utils.js"}) if page else ["utils.js"]
        before = (row.get("status"), row.get("evidence"), row.get("findings"))
        row["status"] = "green"
        row["findings"] = []
        ev = {
            "kind": "live-walk",
            "ref": f"live MCP session {today} · {rd.get('url')} ({rd.get('state')})",
            "asserts": row.get("oracle") or "",
            "checked": "; ".join(rd.get("checked") or []),
            "depends_on": deps,
            "sha": V.sha_of(deps),
            "walked_at": today,
        }
        # R6's escape hatch, and it is NOT a blanket one. A reading may declare `value_checked` only
        # when the walk compared a VALUE against an independent source rather than observing that the
        # page rendered. `source_chip_true` qualifies: the chip's phrase is compared against the
        # friendly name of the relations the page ACTUALLY requested, read from the browser's own
        # resource timings — two measured values, not a rendering. A reading that merely looked at the
        # screen must never set this, or R6 stops being the rule that caught the false 343.
        if rd.get("value_checked"):
            ev["value_checked"] = rd["value_checked"]
        row["evidence"] = ev
        st, why = V.classify(row, gates, urls)
        if st == "invalid":
            row["status"], row["evidence"], row["findings"] = before
            row["findings"] = [f"the live walk passed but the gate rejects the evidence: {why}"]
            failed += 1
        else:
            banked += 1

    seen_keys = {(r.get("category"), r.get("state"), r.get("surface")) for r in rows}
    seen_wild = {(r.get("state"), r.get("surface")) for r in rows}
    unmatched = (sum(1 for k in index if k not in seen_keys)
                 + sum(1 for k in wild if k not in seen_wild))

    print(f"{BOLD}Banking from the live MCP walk{RST}")
    print(f"  {GREEN}{banked} banked green{RST} · {RED}{failed} owed{RST}"
          + (f" · {DIM}{unmatched} reading(s) matched no row{RST}" if unmatched else ""))
    for k, why in misses[:6]:
        print(f"    {RED}✗{RST} {k[0]} {k[1]} @ {k[2]}\n      {DIM}{why}{RST}")
    if not a.apply:
        print(f"\n  {YEL}dry run — pass --apply to write{RST}")
        return 0
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    os.replace(tmp, REGISTRY)
    print(f"\n  {GREEN}written{RST} — {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
