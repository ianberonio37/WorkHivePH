#!/usr/bin/env python3
"""
validate_logbook_deepwalk.py — root entry point for the logbook deepwalk ratchet.

WHY THIS THIN FILE EXISTS: the flywheel orchestrator classifies a baseline INCREASE by re-running
`validate_<name>.py` for the baseline named `<name>_baseline.json`. A board that lives only at
`tools/<name>_scoreboard.py` has nothing to re-run, so its rise falls into the conservative `unknown`
bucket and is SCORED as a regression — which blocks a commit on the canonical board's "Flywheel turns"
gate. That is backwards for this metric: `logbook_deepwalk_baseline.json` holds a COMPLETION FLOOR, so
a rise means the arc advanced, which is exactly the outcome the ratchet exists to produce.

This is the third deepwalk arc, and the hive shim's own docstring predicted this file: "a third
deepwalk arc should add its shim in the same change that adds its board, or it will hit this identical
phantom block on its first real progress." Added in the same change as the board, per that instruction,
and kept a deliberate mirror of `validate_marketplace_deepwalk.py` / `validate_hive_deepwalk.py` so the
three arcs stay ONE pattern rather than three.

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
SCOREBOARD = ROOT / "tools" / "logbook_deepwalk_scoreboard.py"


def main() -> int:
    if not SCOREBOARD.exists():
        print(f"logbook deepwalk scoreboard missing: {SCOREBOARD}")
        return 1
    return subprocess.run([sys.executable, str(SCOREBOARD), *sys.argv[1:]], cwd=str(ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
