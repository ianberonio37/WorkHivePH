#!/usr/bin/env python3
"""FB2 (Forward-Build) - browser-CI multi-persona live floor ratchet gate (fast, static).

The FB2 harness (`tools/browser_ci_persona_walk.mjs`) walks EVERY page HEADLESS as a diverse
persona roster (field-tech worker@mobile / supervisor@desktop / new-worker novice@desktop /
admin supervisor@cross-hive), runs the authoritative ufai_battery referee keyed by each
persona's role+experience, and writes two artifacts:
  - browser_ci_persona_board.json     (per-persona x per-page status + totals.live_pct)
  - browser_ci_persona_baseline.json  (the forward-only ratchet: live floor + per-persona floor)

This validator is the CHEAP CI guard: it does NOT re-drive the browser (that is the multi-minute
`node tools/browser_ci_persona_walk.mjs --accept` run, done locally / full-CI / the browser-ci
workflow). It asserts the cross-persona live floor never falls:

  1. SIGN-IN held  - every persona in the baseline still authenticated (a persona whose sign-in
     broke makes its whole column unmeasurable = a real regression, not a skip).
  2. TOTAL live floor - board.totals.live (pass + gated, i.e. clean-or-correctly-gated walks)
     stays >= the frozen baseline. A persona-specific runtime/security/serious-a11y break (a
     worker code path that throws, a tenant secret leak, a hive-data-dependent contrast bug)
     DROPS a walk from pass->fix and trips this.
  3. PER-PERSONA live floor - each baselined persona's (pass + gated) stays >= its own floor, so
     a regression that only hits ONE persona (the whole point of FB2) can't be masked by another
     persona improving.

FB2's floor is the PERSONA-DELTA only (console-error / dead-onclick-fn / serious-WCAG /
secret-exposure) - it deliberately does NOT re-gate Arc-D-owned absolutes (tap-target sizing,
font, focus, CLS/LCP) or the :5000 /workhive link artifact; see the harness header.

Exit 0 = sign-in held + live floor held; exit 1 = a persona lost sign-in, the total live floor
fell, a per-persona floor fell, or a missing/garbled artifact. Enforced via sys.exit(main()) -
NOT the flywheel reporting-only path.
"""
import json
import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BOARD = "browser_ci_persona_board.json"
BASELINE = "browser_ci_persona_baseline.json"
REPORT = "browser_ci_persona_check_report.json"

# a full run walks every mined page; a dev `--page`/`--limit` run leaves fewer. The floor only
# compares like-for-like full runs (mirrors Arc W's partial-run guard).
FULL_RUN_MIN_PAGES = 30


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


def main():
    board, e1 = _load(BOARD)
    base, e2 = _load(BASELINE)
    if e1 or e2:
        msg = e1 or e2
        print(f"[FB2 browser-CI persona] ERROR - {msg}")
        print("  run: node tools/browser_ci_persona_walk.mjs --accept --update-baseline")
        _write_report({"status": "ERROR", "reason": msg})
        return 1

    totals = board.get("totals", {})
    per_persona = board.get("per_persona", {})
    ppp = int(board.get("pages_per_persona", 0))

    print("=" * 68)
    print("FB2 - BROWSER-CI MULTI-PERSONA LIVE FLOOR ratchet gate")
    print("=" * 68)

    # Partial/subset run guard.
    if ppp and ppp < FULL_RUN_MIN_PAGES:
        print(f"  PARTIAL run ({ppp} pages/persona < {FULL_RUN_MIN_PAGES}) - subset, floor not evaluated.")
        print("  refresh: node tools/browser_ci_persona_walk.mjs --accept --update-baseline")
        _write_report({"status": "PASS", "partial": True, "pages_per_persona": ppp})
        print("  [OK] pass (partial run not gated)")
        return 0

    failures = []

    # 1. SIGN-IN held for every persona that the baseline measured.
    base_pp = base.get("per_persona", {})
    for pid in base_pp:
        rec = per_persona.get(pid)
        if rec is None:
            failures.append(f"persona '{pid}' MISSING from the board (was in baseline) - measurement gap")
        elif not rec.get("signIn", False):
            failures.append(f"persona '{pid}' SIGN-IN FAILED - its whole column is unmeasurable")

    # 2. TOTAL live floor.
    cur_live = int(totals.get("live", 0))
    base_live = int(base.get("live", 0))
    if cur_live < base_live:
        failures.append(f"TOTAL live {cur_live} < baseline {base_live} - a persona walk regressed pass->fix")

    # 3. PER-PERSONA live floor.
    persona_rows = []
    for pid, b in base_pp.items():
        rec = per_persona.get(pid, {})
        cur = int(rec.get("pass", 0)) + int(rec.get("gated", 0))
        floor = int(b.get("pass", 0)) + int(b.get("gated", 0))
        persona_rows.append((pid, cur, floor, rec.get("signIn", False), int(rec.get("fix", 0))))
        if cur < floor:
            failures.append(f"persona '{pid}' live {cur} < baseline floor {floor} - per-persona regression")

    print(f"  pages/persona : {ppp}   personas: {len(per_persona)}")
    for pid, cur, floor, signin, fix in persona_rows:
        flag = "X" if cur < floor else "OK"
        print(f"   [{flag}] {pid:<12} live {cur:>3} >= {floor:<3} signIn={'OK' if signin else 'FAIL'} fix={fix}")
    print(f"  TOTAL live: {cur_live} >= {base_live}  ({totals.get('live_pct', 0)}% of active walks; fix={totals.get('fix', 0)}, err={totals.get('error', 0)})")

    # surface the current persona-specific fixes (informational - the floor gates on COUNT, but a
    # human reading the gate output should see WHAT broke).
    fixes = board.get("fixes", [])
    if fixes:
        print(f"  open persona-fixes ({len(fixes)}):")
        for f in fixes[:12]:
            print(f"     [{f.get('persona')}] {f.get('page')}  floor={f.get('floorMajor')}"
                  f"{' +secrets' if f.get('secrets') else ''}  {' | '.join((f.get('top') or [])[:2])}")

    report = {
        "status": "FAIL" if failures else "PASS",
        "pages_per_persona": ppp,
        "total_live": cur_live, "baseline_live": base_live,
        "live_pct": totals.get("live_pct", 0),
        "per_persona": {pid: {"cur": cur, "floor": floor, "signIn": signin, "fix": fix}
                        for pid, cur, floor, signin, fix in persona_rows},
        "open_fixes": fixes,
        "failures": failures,
    }
    _write_report(report)

    if failures:
        for f in failures:
            print(f"  [X] {f}")
        print("  -> cross-persona live floor regressed.")
        return 1

    print(f"  [OK] live floor held: {cur_live} >= {base_live} across {len(per_persona)} personas; all sign-ins OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
