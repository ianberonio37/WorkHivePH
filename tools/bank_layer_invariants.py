#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BANK THE LAYER AND SEAM ROWS FROM THE HARNESS, WITH HONEST DEPENDENCIES
═══════════════════════════════════════════════════════════════════════════════════════════════════

136 rows in the live-MCP bank assert layer and seam invariants. Every one of them was declared to
depend on `marketplace.html` + `utils.js` — the page that happened to be open when someone walked
them by hand. That is wrong in both directions:

  noisy   a page edit expired 124 claims the page cannot possibly affect
  unsafe  a MIGRATION could change a grant and expire NOTHING. Mig 50 revoked a SELECT this session
          and would not have moved one grant_matches_policy row. Silent false green.

This script re-banks each row from `verify_layer_invariants.py`, which asserts against the live
database and the repo rather than against a screen:

  check passed      -> green, kind: psql, depends_on = what the claim ACTUALLY rests on
                       (supabase/migrations for DB claims, supabase/functions for edge claims),
                       asserts = the measured detail, not a restatement of the question
  check failed      -> owed, with the failure recorded as a finding. A red row is not banked green
                       because the rest of its family passed.
  needs-live        -> left exactly as it is. There is no DB oracle for it, and dressing a
                       structural check as a behavioural one is the R6 violation the gate exists to
                       catch.
  no check          -> left alone. Silence is not evidence.

Run:  python tools/bank_layer_invariants.py            # dry run, prints what would change
      python tools/bank_layer_invariants.py --apply
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    harness = _load_module("vli", os.path.join(ROOT, "tools", "verify_layer_invariants.py"))
    validator = _load_module("vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))

    # run every check once; a check may back more than one registry row (the same (surface, state)
    # appears under both the AX-layer-contract and BA-invariant categories)
    results = {}
    for (layer, state), fn in harness.CHECKS.items():
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "error", f"{type(e).__name__}: {e}"
        results[(layer, state)] = (status, detail)

    reg = json.load(open(REGISTRY, encoding="utf-8"))
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg

    today = date.today().isoformat()
    banked = owed = skipped = 0
    changes = []

    for row in rows:
        key = (row.get("surface"), row.get("state"))
        if key not in results:
            continue
        status, detail = results[key]
        if status == "needs-live":
            skipped += 1
            continue

        deps = harness.DEPENDS_ON.get(row["surface"], [])
        old_deps = (row.get("evidence") or {}).get("depends_on") or []

        if status == "pass":
            row["status"] = "green"
            row["findings"] = []
            row["evidence"] = {
                "kind": "psql",
                "ref": (f"tools/verify_layer_invariants.py --layer {row['surface']} "
                        f"({row['surface']}/{row['state']}) — {today}"),
                "asserts": detail,
                "value_checked": True,
                "checked": detail,
                "depends_on": deps,
                "sha": validator.sha_of(deps),
                "walked_at": today,
            }
            banked += 1
            if sorted(old_deps) != sorted(deps):
                changes.append((row["id"], old_deps, deps))
        else:
            row["status"] = "owed"
            row["findings"] = [f"{status}: {detail}"]
            owed += 1

    print(f"{BOLD}Re-banking the layer and seam rows from the live system{RST}")
    print(f"  {GREEN}{banked} green{RST} · {RED}{owed} owed (a real red, recorded){RST} · "
          f"{YEL}{skipped} left for the browser{RST}")
    if changes:
        print(f"\n  {DIM}dependency corrections ({len(changes)} rows) — a DB claim no longer expires "
              f"when a page is edited, and now DOES expire when a migration lands:{RST}")
        for rid, old, new in changes[:4]:
            print(f"    {rid}\n      was: {old}\n      now: {new}")
        if len(changes) > 4:
            print(f"    {DIM}… and {len(changes) - 4} more{RST}")

    if not a.apply:
        print(f"\n  {YEL}dry run — pass --apply to write{RST}")
        return 0

    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    os.replace(tmp, REGISTRY)          # atomic: a truncated registry would lose every walk
    print(f"\n  {GREEN}written{RST} — {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
