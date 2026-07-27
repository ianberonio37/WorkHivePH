#!/usr/bin/env python3
"""
validate_marketplace_deepwalk.py — root entry point for the marketplace deepwalk ratchet.

WHY THIS THIN FILE EXISTS: the flywheel orchestrator classifies a baseline INCREASE by re-running
`validate_<name>.py` for the baseline named `<name>_baseline.json`. Our board lives at
`tools/marketplace_deepwalk_scoreboard.py`, so there was no `validate_marketplace_deepwalk.py` to
re-run and every rise fell into the conservative `unknown` bucket and was scored as a regression.

That was backwards for this metric. `marketplace_deepwalk_baseline.json` holds an adoption FLOOR: the
count of deepwalk cells that are LOCKED. It rising (77 -> 84 -> 92 over one session) means more of the
arc is verified and held, which is exactly the outcome the ratchet exists to produce. The orchestrator
already has the right bucket for this ("adoption-ratchet ... an improvement, not rot"), and it reaches
that bucket by re-running the validator and seeing it PASS. So the fix is to give it something to run
rather than to special-case the name.

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
SCOREBOARD = ROOT / "tools" / "marketplace_deepwalk_scoreboard.py"


def main() -> int:
    if not SCOREBOARD.exists():
        print(f"marketplace deepwalk scoreboard missing: {SCOREBOARD}")
        return 1
    return subprocess.run([sys.executable, str(SCOREBOARD), *sys.argv[1:]], cwd=str(ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
