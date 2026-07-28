#!/usr/bin/env python3
"""
validate_pm_deepwalk.py — root entry point for the PM Scheduler deepwalk ratchet.

WHY THIS THIN FILE EXISTS, AND WHY IT SHIPS IN THE SAME CHANGE AS THE BOARD: the flywheel
orchestrator classifies a baseline INCREASE by re-running `validate_<name>.py` for the baseline named
`<name>_baseline.json`. A board that lives only at `tools/<name>_scoreboard.py` has nothing to re-run,
so its rise falls into the conservative `unknown` bucket and is SCORED as a regression — which blocks
a commit on the canonical board's "Flywheel turns" gate. That is backwards for this metric:
`pm_deepwalk_baseline.json` holds a COMPLETION FLOOR, so a rise means the arc advanced, which is
exactly what the ratchet exists to produce.

The hive shim's docstring predicted the third arc would rediscover this, and it did. This is the
fourth, and the lesson is now mechanical rather than learned again: the shim lands WITH the board.

Delegates to the scoreboard, which fails only when the board falls BELOW its accepted baseline. Any
flag passes through, so `--accept` and `--selftest` still work from here.
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

# Platform rule: every validate_*.py installs the cp1252 stdout guard, so a box-drawing or accented
# character in a report never kills the run on a Windows console (validate_validator_cp1252_guard).
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SCOREBOARD = ROOT / "tools" / "pm_manager_deepwalk_scoreboard.py"


def main() -> int:
    if not SCOREBOARD.exists():
        print(f"pm deepwalk scoreboard missing: {SCOREBOARD}")
        return 1
    return subprocess.run([sys.executable, str(SCOREBOARD), *sys.argv[1:]], cwd=str(ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
