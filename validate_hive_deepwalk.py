#!/usr/bin/env python3
"""
validate_hive_deepwalk.py — root entry point for the hive deepwalk ratchet.

WHY THIS THIN FILE EXISTS (2026-07-27): the flywheel orchestrator classifies a baseline INCREASE by
re-running `validate_<name>.py` for the baseline named `<name>_baseline.json`. The hive board lives at
`tools/hive_deepwalk_scoreboard.py`, so there was no `validate_hive_deepwalk.py` to re-run, the rise
fell into the conservative `unknown` bucket, and it was SCORED as a regression — which BLOCKED a
commit on the canonical board's "Flywheel turns" gate.

It was backwards for this metric. `hive_deepwalk_baseline.json` holds a COMPLETION FLOOR: the percent
of deepwalk cells that are walked and locked. Ours rising 33 -> 100 over one session means the arc got
finished, which is precisely the outcome the ratchet exists to produce. The orchestrator already has
the right bucket ("adoption-ratchet ... an improvement, not rot") and it reaches that bucket by
re-running the validator and seeing it PASS.

So the fix is to give it something to run, NOT to special-case the name — the same conclusion the
marketplace arc reached, and this file is deliberately the mirror of `validate_marketplace_deepwalk.py`
so the two arcs stay one pattern rather than two. A third deepwalk arc should add its shim in the same
change that adds its board, or it will hit this identical phantom block on its first real progress.

Delegates to the scoreboard, which fails only when the board falls BELOW its accepted baseline. Any
flag passes through, so `--accept` still ratchets from here too.
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
SCOREBOARD = ROOT / "tools" / "hive_deepwalk_scoreboard.py"


def main() -> int:
    if not SCOREBOARD.exists():
        print(f"hive deepwalk scoreboard missing: {SCOREBOARD}")
        return 1
    return subprocess.run([sys.executable, str(SCOREBOARD), *sys.argv[1:]], cwd=str(ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
