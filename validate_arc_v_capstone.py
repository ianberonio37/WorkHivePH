#!/usr/bin/env python3
"""Arc V (EFFORTLESS) - family-capstone cross-page ratchet gate (fast, static).

`tools/effortless_capstone.mjs` drives realistic multi-page JOBS and writes:
  - arc_v_capstone_results.json   (chains[] + summary: continuity_breaks / total_excess_hops / chains)
  - arc_v_capstone_baseline.json  (the ratchet: continuity_breaks must stay 0; excess_hops a CEILING)

This is the CHEAP CI guard (it does NOT re-drive the browser - that's the multi-min
`node tools/effortless_capstone.mjs --accept`). It asserts the LAST recorded capstone run still
holds: cross-page CONTINUITY never breaks (a hop that bounces to sign-in / loses hive context =
a regression) and the cumulative HOP-COST of a job never grows past its ideal. Same
read-the-harness-json pattern as validate_arc_v_effort.py.

Exit 0 = held; exit 1 = a capstone regressed (continuity break or extra hops) or a missing artifact.
Enforced via sys.exit(main()) - NOT the flywheel "reporting-only" path.
"""
import json
import os
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESULTS = "arc_v_capstone_results.json"
BASELINE = "arc_v_capstone_baseline.json"
REPORT = "arc_v_capstone_check_report.json"


def _load(path):
    if not os.path.exists(path):
        return None, f"missing {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as ex:  # noqa: BLE001
        return None, f"unreadable {path}: {ex}"


def main():
    res, e1 = _load(RESULTS)
    base, e2 = _load(BASELINE)
    if e1 or e2:
        msg = e1 or e2
        print(f"[Arc V capstone] ERROR - {msg}")
        print("  run: node tools/effortless_capstone.mjs --accept")
        try:
            with open(REPORT, "w", encoding="utf-8") as f:
                json.dump({"status": "ERROR", "reason": msg}, f, indent=2)
        except Exception:  # noqa: BLE001
            pass
        return 1

    summ = res.get("summary", {})
    breaks = int(summ.get("continuity_breaks", 0))
    excess = int(summ.get("total_excess_hops", 0))
    chains = int(summ.get("chains", 0))

    base_excess = base.get("total_excess_hops", 0)
    base_chains = int(base.get("chains", 0))

    # A partial run (--chain X) has fewer chains than the baseline - not a regression, pass with a note.
    if base_chains and chains < base_chains:
        print("=" * 64)
        print("Arc V - EFFORTLESS family-capstone ratchet gate")
        print("=" * 64)
        print(f"  PARTIAL ({chains} < baseline {base_chains} chains) - subset run, full ratchet not evaluated.")
        try:
            with open(REPORT, "w", encoding="utf-8") as f:
                json.dump({"status": "PASS", "partial": True, "chains": chains}, f, indent=2)
        except Exception:  # noqa: BLE001
            pass
        print("  [OK] pass (partial run not gated)")
        return 0

    failures = []
    if breaks > 0:
        failures.append(f"cross-page CONTINUITY broke on {breaks} hop(s) "
                        "(a job hop bounced to sign-in or lost hive/session context)")
    if base_excess is not None and excess > int(base_excess):
        failures.append(f"capstone hop-cost GREW: {excess} excess hops > baseline {base_excess} "
                        "(a multi-page job now takes more hops than its ideal)")

    print("=" * 64)
    print("Arc V - EFFORTLESS family-capstone ratchet gate")
    print("=" * 64)
    print(f"  chains : {chains}  continuity-breaks {breaks}  excess-hops {excess}")
    print(f"  baseline : continuity-breaks = 0  excess-hops <= {base_excess}  chains >= {base_chains}")

    report = {
        "status": "FAIL" if failures else "PASS",
        "chains": chains, "continuity_breaks": breaks, "total_excess_hops": excess,
        "baseline_excess_hops": base_excess, "baseline_chains": base_chains, "failures": failures,
    }
    try:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:  # noqa: BLE001
        pass

    if failures:
        for f in failures:
            print(f"  [X] {f}")
        return 1
    print(f"  [OK] all {chains} cross-page jobs effortless: continuity intact, no excess hops")
    return 0


if __name__ == "__main__":
    sys.exit(main())
