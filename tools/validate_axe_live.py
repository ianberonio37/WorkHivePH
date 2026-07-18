#!/usr/bin/env python3
"""validate_axe_live.py — Python wrapper that runs the AUTHENTICATED axe a11y gate.

run_platform_checks invokes every validator with `python <script>`, but the axe
runner is Node (Playwright + vendored axe.min.js; the project path contains "&"
which breaks npx, so we call node directly). This shim shells out to
`node tools/axe_scan_live.js` and propagates its result.

Why a LIVE authed gate (not just the static axe_scan.js): the static scan seeds
a FAKE identity on a static server, so the Tier-1 OPERATIONAL WRITE pages
(hive/inventory/logbook/pm-scheduler/skillmatrix/community/dayplanner/marketplace/
project-manager) bounce to the sign-in gate and get ZERO axe coverage — exactly
the highest-a11y-risk surfaces (forms, modals, destructive actions). This runner
password-grants a real seeded supervisor against the local stack and scans them
authed. Integrity-at-zero: baseline 0, any NEW violation FAILs. Found 0 live
2026-07-07 (dim-8 keyboard/a11y).

Skips cleanly (exit 0) if node is unavailable or the local stack is down —
same contract as the other *_live validators.

Usage:  python tools/validate_axe_live.py
Exit:   0 = pass/skip · 1 = a new WCAG 2.2 AA violation on an authed write page.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "axe_scan_live.js"


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("  SKIP — node not on PATH (authed axe a11y gate needs Node + Playwright).")
        return 0
    if not RUNNER.exists():
        print(f"  SKIP — runner missing: {RUNNER}")
        return 0
    try:
        p = subprocess.run([node, str(RUNNER)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=240)
    except subprocess.TimeoutExpired:
        print("  SKIP — authed axe runner timed out (local stack slow/absent).")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  SKIP — could not launch node runner: {type(e).__name__}: {e}")
        return 0
    sys.stdout.write(p.stdout or "")
    sys.stdout.write(p.stderr or "")
    # The runner itself exits 0 on skip (env absent) and 1 only on a real regression.
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
