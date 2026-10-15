#!/usr/bin/env python3
"""Arc K - Live-Page Journeys ratchet gate (fast, static).

The live-page-journeys harness (`tools/live_page_journeys.mjs`) drives every page's
jobs-to-be-done against the LIVE local stack (worker/supervisor sign-in + real DB
verification) and writes two artifacts:
  - live_page_journeys_results.json   (journeys[] + summary: live / applicable / floor)
  - live_page_journeys_baseline.json  (the forward-only ratchet: live>=N, floor<=N)

This validator is the CHEAP CI guard: it does NOT re-drive the browser (that's the
~15-min `node tools/live_page_journeys.mjs --accept --update-baseline` run, done
locally/full-CI). It just asserts the LAST recorded results still meet the locked
baseline ratchet - live count never regresses, deterministic floor never grows. Same
read-the-harness-json pattern as validate_auth_live_flows / validate_realtime_live.

Exit 0 = ratchet held; exit 1 = regression (a journey went non-live, or a new floor
finding appeared) or a missing/garbled artifact.
"""
import json
import os
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESULTS = "live_page_journeys_results.json"
BASELINE = "live_page_journeys_baseline.json"
REPORT = "live_page_journeys_check_report.json"


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
        print(f"[Arc K live-journeys] ERROR - {msg}")
        print("  run: node tools/live_page_journeys.mjs --accept --update-baseline")
        _write_report({"status": "ERROR", "reason": msg})
        return 1

    summary = res.get("summary", {})
    live = int(summary.get("live", 0))
    applicable = int(summary.get("applicable", 0))
    floor = int(summary.get("floor_findings", 0))
    live_pct = summary.get("live_pct", 0)
    external = int(summary.get("external", 0))

    base_live = int(base.get("live", 0))
    base_applicable = int(base.get("applicable", 0))
    base_floor = base.get("floor", None)

    # Partial/subset run guard: a dev `--page`/`--phase` run leaves a results.json with
    # fewer journeys than the full-suite baseline. The ratchet only compares like-for-like
    # full runs, so a partial result is NOT a regression - pass with a note.
    if base_applicable and applicable < base_applicable:
        print("=" * 64)
        print("Arc K - Live-Page Journeys ratchet gate")
        print("=" * 64)
        print(f"  PARTIAL results ({applicable} < baseline {base_applicable} journeys) - "
              "subset run, full-suite ratchet not evaluated.")
        print("  refresh: node tools/live_page_journeys.mjs --accept --update-baseline")
        _write_report({"status": "PASS", "partial": True,
                       "applicable": applicable, "baseline_applicable": base_applicable})
        print("  [OK] pass (partial run not gated)")
        return 0

    failures = pinned_failures(res, base)
    if live < base_live:
        failures.append(f"live REGRESSED: {live} < baseline {base_live}")
    if base_floor is not None and floor > int(base_floor):
        failures.append(f"floor findings GREW: {floor} > baseline {base_floor}")

    print("=" * 64)
    print("Arc K - Live-Page Journeys ratchet gate")
    print("=" * 64)
    print(f"  measured : live {live}/{applicable} = {live_pct}%  "
          f"(+{external} ext external)  floor findings {floor}")
    print(f"  baseline : live >= {base_live}  floor <= {base_floor}")

    report = {
        "status": "FAIL" if failures else "PASS",
        "live": live, "applicable": applicable, "live_pct": live_pct,
        "external": external, "floor_findings": floor,
        "baseline_live": base_live, "baseline_floor": base_floor,
        "failures": failures,
    }
    _write_report(report)

    if failures:
        for f in failures:
            print(f"  [X] {f}")
        print("  -> a journey went non-live or a new deterministic floor finding appeared.")
        return 1

    print(f"  [OK] ratchet held: live {live} >= {base_live}, floor {floor} <= {base_floor}")
    return 0


# ★A COUNT CANNOT HOLD ONE JOURNEY (BRH-J, 2026-10-15). live >= 95 deliberately absorbs the LLM journeys' flicker, so a
# DETERMINISTIC journey that breaks - 109 -> 108 - stays green. A journey banked as live is pinned by id in the
# baseline (pinned_live), and each pinned id must be present and live in the results, whatever the total says.
def pinned_failures(res, base):
    out = []
    rows = {j.get("id"): j for j in res.get("journeys", [])}
    for jid in base.get("pinned_live", []):
        j = rows.get(jid)
        if not j:
            out.append(f"pinned journey {jid} is missing from the results")
        elif not j.get("live"):
            failing = "".join(k for k, v in (j.get("verdict") or {}).items() if v is False)
            out.append(f"pinned journey {jid} is NOT live (fails {failing or '?'})")
    return out


def self_test():
    base = {"pinned_live": ["A1", "B2"]}
    ok_res = {"journeys": [{"id": "A1", "live": True}, {"id": "B2", "live": True}]}
    bad_res = {"journeys": [{"id": "A1", "live": True}, {"id": "B2", "live": False, "verdict": {"J": False, "T": True}}]}
    gone_res = {"journeys": [{"id": "A1", "live": True}]}
    ok = (not pinned_failures(ok_res, base) and len(pinned_failures(bad_res, base)) == 1
          and len(pinned_failures(gone_res, base)) == 1 and not pinned_failures(bad_res, {}))
    print(("PASS" if ok else "FAIL") + " live-page-journeys self-test - a pinned journey that is not live, or missing, "
          "reddens; an unpinned one does not")
    return 0 if ok else 1


def _write_report(obj):
    try:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
