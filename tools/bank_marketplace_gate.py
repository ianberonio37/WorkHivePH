#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert MARKETPLACE registry rows to gate-backed evidence, on the page-bank rails.

WHY THIS EXISTS. The marketplace bank went from 752 green to 11 in one release: 741 rows expired
because the files they name changed. utils.js alone is cited by 664 of its 877 rows and moved by
+318 lines, so a live re-walk restores evidence that the NEXT shared-file edit expires again. A
gate-backed row does not expire that way -- it is re-earned by RUNNING the gate. Converting the
shapes a registered gate already settles turns a recurring re-walk bill into a one-time move, which
is exactly what the page banks did today (905 rows, 0 refusals).

WHY A SEPARATE TOOL AND NOT A --bank FLAG ON bank_page_walk.py. The schemas differ:
    page bank            scenarios[] keyed by oracle_key + subject.key
    marketplace registry scenarios[] keyed by category + state + surface  (the bank_live_walk shape)
A flag would have to fork the row-matching AND the evidence build, which is two implementations
wearing one name. This reuses the RAILS -- the gate's own classify(), gate_ids(), surface_urls(),
fn_digests() -- and only the matching differs.

IT CANNOT BANK SOMETHING THE GATE WOULD REJECT: every candidate goes through V.classify() before it
is kept, exactly as bank_page_walk does, so a row that would read invalid is refused here rather
than discovered by the gate later.

  python tools/bank_marketplace_gate.py --category <cat> --gate <gate-id> --src <prover> \
      --text <file> [--state <s>] [--surface <s>] [--apply]

--text is the same 3-section format the page conversions use: asserts / checked / value_checked,
separated by a line containing only ---
"""
import argparse
import importlib.util
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--src", required=True, help="the prover/gate script the rows will name")
    ap.add_argument("--text", required=True)
    ap.add_argument("--state")
    ap.add_argument("--surface")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    bank = json.load(io.open(REGISTRY, encoding="utf-8"))
    rows = bank.get("scenarios") or []
    gates, urls = V.gate_ids(), V.surface_urls(bank)

    if a.gate not in gates:
        print(f"  {RED}REFUSING{RST}: gate id {a.gate!r} is not registered in run_platform_checks - "
              f"rail R2 would reject every row citing it")
        return 2

    parts = io.open(a.text, encoding="utf-8").read().split("\n---\n")
    if len(parts) != 3:
        print(f"  {RED}REFUSING{RST}: --text needs exactly 3 sections "
              f"(asserts / checked / value_checked) separated by a line of ---; got {len(parts)}")
        return 2
    asserts, checked, value = (p.strip() for p in parts)

    picked = [r for r in rows
              if r.get("category") == a.category
              and (not a.state or r.get("state") == a.state)
              and (not a.surface or r.get("surface") == a.surface)]
    if not picked:
        print(f"  {YEL}no rows{RST} match category={a.category!r} "
              f"state={a.state!r} surface={a.surface!r}")
        return 0

    deps = sorted({a.src} | {r["surface"] for r in picked if r.get("surface")})
    banked = refused = 0
    for row in picked:
        ev = {"kind": "gate", "ref": f"gate:{a.gate}", "asserts": asserts, "checked": checked,
              "value_checked": value + " | depends_on: " + ", ".join(deps),
              "depends_on": deps, "sha": V.sha_of(deps) if hasattr(V, "sha_of") else None,
              "replay": f"python run_platform_checks.py --only {a.gate}"}
        candidate = dict(row)
        candidate["status"] = "green"
        candidate["evidence"] = ev
        state, why = V.classify(candidate, gates, urls)
        if state != "green":
            refused += 1
            print(f"  {YEL}REFUSED{RST} {row['id']}\n          {DIM}{why or state}{RST}")
            continue
        ev["fn_digests"] = V.fn_digests(deps)
        row["status"] = "green"
        row["evidence"] = ev
        banked += 1

    print(f"\n  banked {GREEN}{banked}{RST} · refused {refused}  "
          f"({'APPLIED' if a.apply else 'dry run'})")
    if a.apply and banked:
        tmp = REGISTRY + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(bank, indent=1, ensure_ascii=False))
        os.replace(tmp, REGISTRY)          # atomic: open(w) truncates before the write lands
        print(f"  wrote {REGISTRY}")
    return 0


sys.exit(main(sys.argv[1:]))
