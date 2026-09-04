#!/usr/bin/env python3
"""hive-at-scale - T61: the people surfaces at 20 members.

Wrapper around tools/prove_hive_at_scale.mjs. Every seeded hive here is small - 8 members in the
largest - so the people surfaces have only ever been read at a size where nothing can go wrong. The
fixture is ON-DEMAND rather than standing: a permanent 20-member hive would move the numbers every
other gate reads, and a fixture that quietly changes someone else's denominator is worse than none.

Skips when node or docker is absent.
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
    if not shutil.which("node") or not shutil.which("docker"):
        print("SKIP hive-at-scale - node or docker not on PATH (live gate)")
        return 0
    try:
        r = subprocess.run([shutil.which("node"), str(ROOT / "tools" / "prove_hive_at_scale.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL hive-at-scale - the scale walk timed out at 300s")
        return 1
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("  " + line.strip()[:190])
    if re.search(r"^\s*SKIP", out, re.M):
        return 0
    if re.search(r"^\s*PASS", out, re.M) and r.returncode == 0:
        return 0
    print("FAIL hive-at-scale - a 20-member hive did not list every member exactly once in a stable order.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
