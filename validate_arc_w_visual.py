#!/usr/bin/env python3
"""Arc W (VISUAL UI/UX) - 9-lens visual-quality ratchet gate (fast, static).

The Arc W sweep (`tools/arc_w_visual_sweep.mjs`) navigates every registered page at the mobile
(390px) and desktop (1280px) viewport, runs the 9-lens DOM probe, and writes two artifacts:
  - arc_w_results.json   (records[] + summary: per-lens platform violation floors)
  - arc_w_baseline.json  (the forward-only ratchet: every per-lens floor is a CEILING)

This validator is the CHEAP CI guard: it does NOT re-drive the browser (that's the multi-minute
`node tools/arc_w_visual_sweep.mjs --accept` run, done locally/full-CI). It asserts two things:

  1. RATCHET (no visual rot) - every per-lens floor in the LAST recorded results stays <= the
     frozen baseline ceiling (+tol). depth/whitespace/grouping/color/icon/focal floors can only
     FALL (visual quality improves); the cross-page consistency variant-spread can only hold or
     shrink (no new component cousins). Same read-the-harness-json pattern as Arc V / Arc K.

  2. M/S CSS-rule FLOOR (the one lens the page-probe can't read) - components.css must keep at
     least the baseline number of `:active` + `:focus-visible` control-state rules (target UP,
     W1 raises it) and must NOT lose the `.wh-skeleton` loader or the prefers-reduced-motion
     guard (regression guards). At the R1 baseline both state-rule counts are 0; W1 drives them
     up and re-banks, after which dropping them fails here.

Exit 0 = ratchet held + state floor held; exit 1 = a lens floor ROSE (visual rot), a consistency
variant set GREW, a control-state rule was LOST, or a missing/garbled artifact. The exit code is
enforced via sys.exit(main()) - NOT the flywheel "reporting-only, exit 0 always" path
(run_platform_checks.py:998).
"""
import json
import os
import re
import sys

RESULTS = "arc_w_results.json"
BASELINE = "arc_w_baseline.json"
CSS = "components.css"
REPORT = "arc_w_visual_check_report.json"

# the per-lens platform floors the ratchet enforces as CEILINGS (must not rise).
CEILINGS = [
    "lens_floor", "depth_floor", "focal_floor", "whitespace_floor", "grouping_floor",
    "color_floor", "icon_floor",
    "consistency_radius_variants", "consistency_pad_variants",
    "consistency_combo_variants", "consistency_shadow_variants_max",
]
# data-driven pages render a variable number of cards/gaps run-to-run; a small tolerance on the
# large structural floors prevents async-jitter false alarms while still catching real rot (a
# W-phase regression moves dozens). The small/structural floors (focal/color/icon/consistency)
# are exact counts -> tol 0.
TOL = {"lens_floor": 4, "depth_floor": 3, "whitespace_floor": 3, "grouping_floor": 2}


def _load(path):
    if not os.path.exists(path):
        return None, f"missing {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as ex:  # noqa: BLE001
        return None, f"unreadable {path}: {ex}"


def _write_report(obj):
    try:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
    except Exception:  # noqa: BLE001
        pass


def _count_ms_rules():
    """Static M/S signals from components.css: control-state rule counts + regression guards."""
    try:
        with open(CSS, "r", encoding="utf-8") as f:
            css = f.read()
    except Exception:  # noqa: BLE001
        return None
    return {
        "active_rules": len(re.findall(r":active\b", css)),
        "focus_visible_rules": len(re.findall(r":focus-visible\b", css)),
        "has_skeleton": ".wh-skeleton" in css,
        "has_reduced_motion": "prefers-reduced-motion" in css,
    }


def main():
    res, e1 = _load(RESULTS)
    base, e2 = _load(BASELINE)
    if e1 or e2:
        msg = e1 or e2
        print(f"[Arc W visual] ERROR - {msg}")
        print("  run: node tools/arc_w_visual_sweep.mjs --accept --update-baseline")
        _write_report({"status": "ERROR", "reason": msg})
        return 1

    summary = res.get("summary", {})
    pages = int(summary.get("pages_probed", 0))
    base_pages = int(base.get("pages_probed", 0))

    # Partial/subset run guard: a dev `--page` run leaves results with fewer pages than the
    # full-suite baseline. The ceilings only compare like-for-like full runs.
    if base_pages and pages < base_pages:
        print("=" * 68)
        print("Arc W - VISUAL UI/UX 9-lens ratchet gate")
        print("=" * 68)
        print(f"  PARTIAL results ({pages} < baseline {base_pages} pages) - subset run, "
              "full-suite ceiling not evaluated.")
        print("  refresh: node tools/arc_w_visual_sweep.mjs --accept --update-baseline")
        _write_report({"status": "PASS", "partial": True,
                       "pages": pages, "baseline_pages": base_pages})
        print("  [OK] pass (partial run not gated)")
        return 0

    failures = []
    rows = []
    for k in CEILINGS:
        cur = int(summary.get(k, 0))
        bk = base.get(k)
        if bk is None:
            continue
        tol = int(TOL.get(k, 0))
        rows.append((k, cur, int(bk), tol))
        if cur > int(bk) + tol:
            failures.append(f"{k} ROSE: {cur} > baseline {bk} (+{tol} tol) - visual rot")

    # ── M/S CSS-rule floor (the lens the page-probe can't observe) ──
    ms = _count_ms_rules()
    base_ms = base.get("ms") or {}
    ms_rows = []
    if ms is None:
        failures.append(f"cannot read {CSS} for M/S state-rule floor")
    else:
        # control-state rules: must not DROP below baseline (target UP - W1 raises + re-banks).
        for key in ("active_rules", "focus_visible_rules"):
            cur = ms[key]
            floor = int(base_ms.get(key, 0))
            ms_rows.append((key, cur, floor))
            if cur < floor:
                failures.append(f"{key} DROPPED: {cur} < baseline floor {floor} - lost a control-state rule")
        # regression guards: skeleton + reduced-motion must stay present once baselined true.
        for key in ("has_skeleton", "has_reduced_motion"):
            if base_ms.get(key) and not ms[key]:
                failures.append(f"{key} LOST - a motion/state regression guard was removed")

    print("=" * 68)
    print("Arc W - VISUAL UI/UX 9-lens ratchet gate")
    print("=" * 68)
    print(f"  pages probed : {pages}  (baseline {base_pages})")
    for k, cur, bk, tol in rows:
        flag = "X" if cur > bk + tol else "OK"
        print(f"   [{flag}] {k:<32} {cur:>5} <= {bk}{(' +' + str(tol)) if tol else ''}")
    if ms is not None:
        for key, cur, floor in ms_rows:
            flag = "X" if cur < floor else "OK"
            print(f"   [{flag}] M/S {key:<28} {cur:>5} >= {floor}")
        print(f"        M/S guards: skeleton={ms['has_skeleton']} reduced-motion={ms['has_reduced_motion']}")

    report = {
        "status": "FAIL" if failures else "PASS",
        "pages": pages, "baseline_pages": base_pages,
        "ceilings": {k: {"cur": cur, "baseline": bk, "tol": tol} for k, cur, bk, tol in rows},
        "ms": ms, "baseline_ms": base_ms,
        "failures": failures,
    }
    _write_report(report)

    if failures:
        for f in failures:
            print(f"  [X] {f}")
        print("  -> visual quality regressed (a lens floor rose / a state rule was lost).")
        return 1

    print(f"  [OK] ratchet held: lens_floor {int(summary.get('lens_floor', 0))} <= {base.get('lens_floor')}; all 9 lenses within ceiling; M/S state floor held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
