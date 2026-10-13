#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_no_retracted_evidence.py — no trajectory may be COUNTED closed on an instrument Ian retracted.

THE RULE. On 2026-09-15 Ian retracted every row banked on a Playwright-LIBRARY prover: "I thought we are using
relevant live MCPs?" A prover may WALK to find defects and produce receipts; it may not CLOSE a row reserved
for an MCP walk.

WHY A GATE ON THE STATE RATHER THAN ON EACH PRODUCER. The retraction was enforced inside one banker
(bank_w4_passers._is_retracted), and the ledger that decides whether a basis COUNTS knew nothing about it - its
`playwright` marker tuple accepts the bare prefix "prove_", so every library prover satisfied the instrument
test. Measured 2026-10-05: **916 rows read CLOSED on a retracted prover**, and for every one of them the
retracted run was the NEWEST evidence segment, not a superseded entry in its history
(prove_w4_actions 431 · prove_full_journeys 325 · prove_w4_navhub 90 · prove_w4_confusions 70). The headline
read 8,909 closed / 75.7%; honest, it was 8,480 / 72.0%.

Ten tools in `tools/bank_*.py` advance a row's status and only two know the word "retracted". Teaching each of
them is necessary but not sufficient - the eleventh will not know either, and a hand-written basis bypasses all
of them. So this gate asserts the INVARIANT instead: whatever wrote it, no row is counted closed on retracted
evidence. It reads the ledger's own classification rather than re-deriving freshness or markers, which is the
standing rule for a guard here ([[feedback_install_the_guard_never_re_derive_it]]).

  python tools/validate_no_retracted_evidence.py          # report
  python tools/validate_no_retracted_evidence.py --check   # the gate
"""
from __future__ import annotations

import collections
import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"


def _ledger():
    """The ledger's OWN classification, computed fresh - never a re-derivation of its rules here."""
    spec = importlib.util.spec_from_file_location("_lwm", ROOT / "tools" / "live_walk_manifest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ★AND THE GATE MUST GUARD THE LIST, NOT ONLY THE ROWS (added on this file's first teeth test, 2026-10-05).
# The first version asserted "nothing KNOWN-retracted is counted closed" - and the teeth test showed why that is
# not enough: deleting one name from the ledger's tuple made 431 rows stop being "known retracted", so they
# silently counted closed again and the gate still passed. A guard bound to a list that the thing it guards can
# edit is the ★×14 shape - every condition under which the guard relaxes becomes the next loophole.
# So the five names Ian retracted on 2026-09-15 are ALSO pinned here. The list may GROW - retiring another
# instrument is a legitimate decision - but a name may not quietly leave, because each departure silently
# re-closes hundreds of rows. Removing one is a deliberate act that should fail this gate and be argued for.
RETRACTED_FLOOR = (
    "tools/prove_w4_actions.mjs",        # 431 rows rested on it
    "tools/prove_full_journeys.mjs",     # 325
    "tools/prove_w4_navhub.mjs",         # 90
    "tools/prove_w4_confusions.mjs",     # 70
    "tools/prove_w4_layer_ca.mjs",       # 126 walked clean 2026-10-05 and correctly did not bank
)


def main() -> int:
    check = "--check" in sys.argv
    m = _ledger()
    rows = m.build()["rows"]

    declared = tuple(getattr(m, "RETRACTED_INSTRUMENTS", ()))
    dropped = [n for n in RETRACTED_FLOOR if n not in declared]
    if dropped:
        print(f"  {RED}FAIL{RST} no-retracted-evidence — {len(dropped)} instrument(s) have been REMOVED from "
              f"live_walk_manifest.RETRACTED_INSTRUMENTS: {', '.join(dropped)}. Each removal silently re-closes "
              f"every row resting on it, which is the defect this gate exists to prevent. The list may grow; a "
              f"name leaves only by a decision argued on its own terms (and by editing RETRACTED_FLOOR here).")
        return 1

    resting = [r for r in rows if r.get("retracted_instrument")]
    counted = [r for r in resting if not r.get("needs_mcp_rewalk")]
    by_inst = collections.Counter(r["retracted_instrument"] for r in resting)

    print(f"  retracted instruments declared: {len(m.RETRACTED_INSTRUMENTS)}")
    print(f"  rows whose NEWEST evidence names one: {len(resting)}")
    for inst, n in by_inst.most_common():
        print(f"    {n:5}  {inst}")
    print(f"  of those, COUNTED CLOSED: {len(counted)}")

    if counted:
        print(f"  {RED}FAIL{RST} no-retracted-evidence — {len(counted)} row(s) are counted closed on an "
              f"instrument Ian retracted on 2026-09-15. A prover may WALK to find defects; it may not CLOSE a "
              f"row reserved for an MCP walk. Walk them through the MCP, or correct the basis.")
        for r in counted[:10]:
            print(f"      {r['id']:8} {r['wave']:8} {r['retracted_instrument']}")
        return 1
    if check:
        print(f"{GREEN}PASS{RST} no-retracted-evidence — every one of the {len(resting)} row(s) resting on a "
              f"retracted prover sits in the re-walk queue where it belongs; none inflates the closed count")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    raise SystemExit(main())
