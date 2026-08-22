#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-affirm STALE declared-na rows whose ABSENCE basis still holds in the page's current footprint.

A declared-na row's evidence is REASONING anchored on file shas: "this view performs no write, so
there is no landing to confirm." When the page is edited the sha moves and the row goes stale —
correctly, because an edit COULD have added the write that makes the claim applicable. This tool
re-checks the basis instead of rubber-stamping:

  · rows whose asserts state a WRITE-shaped absence ("no write", "no committing control", "no second
    press", "no half-applied", "no input a person can get wrong", "no action") re-affirm ONLY when
    the whole page's current footprint (derive_page_matrix) has ZERO db writes and ZERO rpcs — a
    page that cannot write anywhere trivially cannot write in any view;
  · rows stating an EDGE-shaped absence ("invokes no edge function", "no primary for an outage")
    re-affirm only when the footprint has ZERO edge invokes;
  · every other declared-na row is LEFT STALE — its basis is view-scoped or bespoke, and a
    footprint-level check cannot honestly settle it (those need the browser or a human read).

Every re-affirmed row re-classifies through the gate's own classify() or is reverted.

USAGE  python tools/bank_na_reaffirm.py [--apply]
"""
import argparse
import glob
import importlib.util
import io
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from derive_page_matrix import build  # the same footprint parser the bughunt scoreboard trusts

WRITE_ABSENCE = re.compile(
    r"no (write|committing control|second press|half-applied|landing|input a person can get wrong|"
    r"action, so it has no aftermath|action)", re.I)
EDGE_ABSENCE = re.compile(r"(invokes no edge function|no primary for an outage|served fallback)", re.I)


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
    today = date.today().isoformat()

    foot = {}
    def footprint(page):
        if page not in foot:
            try:
                m, err = build(page)
                foot[page] = m["footprint"] if m and not err else None
            except Exception:
                foot[page] = None
        return foot[page]

    tot_aff = tot_left = 0
    for bank_path in sorted(glob.glob(os.path.join(ROOT, "banks", "*_live_mcp_bank.json"))):
        reg = json.load(open(bank_path, encoding="utf-8"))
        rows = reg.get("scenarios") if isinstance(reg, dict) else reg
        if not rows:
            continue
        gates, urls = V.gate_ids(), V.surface_urls(reg)
        aff = 0
        for row in rows:
            ev = row.get("evidence")
            if not isinstance(ev, dict) or ev.get("kind") != "declared-na":
                continue
            state, why = V.classify(row, gates, urls)
            if state != "stale":
                continue
            fp = footprint(row.get("page"))
            if not fp:
                tot_left += 1
                continue
            asserts = str(ev.get("asserts") or "")
            basis_holds = False
            if WRITE_ABSENCE.search(asserts):
                basis_holds = not fp.get("db_writes") and not fp.get("rpcs")
            elif EDGE_ABSENCE.search(asserts):
                basis_holds = not fp.get("edge")
            if not basis_holds:
                tot_left += 1
                continue
            before = (ev.get("sha"), ev.get("fn_digests"), ev.get("reaffirmed_at"))
            deps = ev.get("depends_on") or []
            ev["sha"] = V.sha_of(deps)
            ev["fn_digests"] = V.fn_digests(deps)
            ev["reaffirmed_at"] = (f"{today} — the absence this reasoning rests on still holds in the "
                                   f"page's CURRENT footprint (derive_page_matrix: no writes/rpcs or "
                                   f"no edge invokes, matching the stated basis); sha re-anchored, "
                                   f"reasoning unchanged")
            st2, _ = V.classify(row, gates, urls)
            if st2 != "green":
                ev["sha"], ev["fn_digests"], _old = before
                if before[2] is None:
                    ev.pop("reaffirmed_at", None)
                tot_left += 1
                continue
            aff += 1
        if aff and a.apply:
            json.dump(reg, open(bank_path, "w", encoding="utf-8"), indent=1)
        if aff:
            print(f"  {os.path.basename(bank_path):44s} {GREEN}{aff} re-affirmed{RST}")
        tot_aff += aff

    print(f"\n  {GREEN}{tot_aff} re-affirmed{RST} · {DIM}{tot_left} left stale (basis view-scoped/"
          f"bespoke, or the page NOW has the capability — those need a real re-look){RST}"
          + ("" if a.apply else f"   {YEL}dry run — pass --apply to write{RST}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
