#!/usr/bin/env python3
"""dialog-floor — T113: every dialog measured at the 320px budget-Android floor (2026-08-26).

cj_dialog_layout sweeps 390/641/1280 — the widths with banked owed rows. 320 is
the floor this platform actually targets and NO dialog had ever been measured
there, so this runs the same prover (WH_DIALOG_WIDTHS=320) as a separate gate
rather than widening the existing one: silently adding a fourth width would
change what cj_dialog_layout MEANS without anyone deciding to, and its rows
describe the three it has.

WHAT THE FIRST FLOOR RUN FOUND — three real defects, in a place nobody had looked:

  pm-scheduler #completion-sheet  the PM completion sheet's PRIMARY ACTION hung
      21px past the panel. btn-primary is width:100% by design, but in the sheet
      it shares one flex row with Cancel, and at 320 the panel's content box is
      278px — the two cannot fit however the remainder is divided (two attempts
      to make them share went 21px -> 10px -> 14px, which was the measurement
      saying so). They stack at the floor now, which is the ordinary pattern.
  analytics #results-panel        an inline style pinned THREE columns regardless
      of width; its tiles pushed 52px past the panel. auto-fit keeps three where
      they fit and drops to two on a budget phone.
  public-feed #feed-list          a 229x12px link — and it turned out NOT to be a
      floor-only defect at all: it lives in whListError, so it was in ~20 pages'
      read-failure states, failing at 390 too. Fixed centrally.

★THE LAST ONE IS THE ARGUMENT FOR THIS GATE. Measuring a width nobody had
measured found a defect that was never about that width — it was platform-wide
and had been sitting in the state a person reaches when something has already
gone wrong.

Re-drive: WH_DIALOG_WIDTHS=320 node tools/prove_dialog_layout.mjs
"""
import io
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# A BROKEN MACHINE IS NOT A BROKEN PRODUCT. This gate drives a real browser and had no health check, so
# an infra death was reported as a layout defect: on 2026-08-28 the prover graded three dialogs and then
# died on `SIGN-IN FAILED: Failed to fetch`, and this gate printed "a dialog overflows or has an
# under-44px target at the 320 floor" — a sentence with no measurement behind it. Its four sibling
# browser gates already import this helper (see feedback_full_suite_live_gates_flake_under_load); this
# one simply never did. A false RED is worse than a SKIP: a skip says "not measured", a red sends someone
# to hunt CSS that was never wrong, and gates that cry wolf get excluded from the board.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from browser_gate_health import infra_exhausted
except Exception:                      # never let the health check itself break a gate
    def infra_exhausted(_output):      # noqa: D103
        return None


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP dialog-floor — node not on PATH (live viewport gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP dialog-floor — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    env = dict(os.environ, WH_DIALOG_WIDTHS="320")

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_dialog_layout.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace", env=env)
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()          # live viewport gates flake under full-suite load
    except subprocess.TimeoutExpired:
        print("FAIL dialog-floor — timed out at 900s")
        return 1

    # the prover refuses to call an empty denominator a pass; surface the graded count either way
    m = re.search(r"(\d+) of (\d+) dialog\(s\) graded, (\d+) failing", out)
    if m:
        print(f"  graded {m.group(1)} of {m.group(2)} at 320px, {m.group(3)} failing")
    named = [l for l in out.splitlines() if l.strip().startswith("FAIL")][:6]
    for line in named:
        print("  " + line.strip()[:170])

    # NEVER ACCUSE MUTELY. Twice on 2026-08-28 this gate printed "a dialog overflows or has an under-44px
    # target" and NOTHING else: the prover had died before reaching its FAIL section, so the prefix filter
    # above matched nothing and the only thing on screen was a verdict with no evidence under it. A reader
    # then has to re-run a 900s browser sweep by hand just to learn WHICH dialog — which is how a gate
    # stops being read. If the run failed and we cannot name the dialog, show the tail we do have.
    if not ok and not named:
        tail = [l.rstrip() for l in out.splitlines() if l.strip()][-12:]
        if tail:
            print("  no per-dialog FAIL line was emitted — the prover's own last words:")
            for line in tail:
                print("    | " + line[:160])

    if not ok:
        # Ask FIRST whether the runner died, because a run that never measured cannot have found a defect.
        verdict = infra_exhausted(out)
        if verdict:
            print(f"  SKIP (infrastructure): {verdict}")
            return 0
        print("FAIL dialog-floor — a dialog overflows or has an under-44px target at the 320 floor. "
              "This is the budget Android a field worker actually carries.")
        return 1
    print("PASS dialog-floor — every gradable dialog fits the 320px floor with tap targets at 44px.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
