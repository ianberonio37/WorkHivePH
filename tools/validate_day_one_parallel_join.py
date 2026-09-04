#!/usr/bin/env python3
"""day-one-parallel-join - T185: five workers, one invite code, the same minute.

Wrapper around tools/prove_day_one_parallel_join.mjs. A supervisor reads ONE code out at the morning
briefing and the crew types it in at once - the first thing that has to work on a pilot's first day,
because if two of the five silently fail to join the pilot is over before anyone logs a repair.

Distinct from join-names-the-namesake, which proves the RPC's behaviour for a SINGLE caller. This
puts N distinct identities on the same hive row and the same unique index CONCURRENTLY and asserts
the three things that can go wrong: nobody is silently lost, nobody lands twice, and the one who
shares a teammate's name is refused BY NAME rather than by the raw index.

Writes real rows and removes them, re-counting to prove the cleanup. Skips when node or the local
database is absent.
"""
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if not shutil.which("node"):
        print("SKIP day-one-parallel-join - node not on PATH (live gate)")
        return 0
    if not shutil.which("docker"):
        print("SKIP day-one-parallel-join - docker not on PATH (live gate)")
        return 0
    try:
        r = subprocess.run([shutil.which("node"), str(ROOT / "tools" / "prove_day_one_parallel_join.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL day-one-parallel-join - the walk timed out at 420s")
        return 1
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("  " + line.strip()[:190])
    if re.search(r"^\s*SKIP", out, re.M):
        return 0
    if re.search(r"^\s*PASS", out, re.M) and r.returncode == 0:
        return 0
    print("FAIL day-one-parallel-join - a crew sharing one invite code did not all get in cleanly.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
