#!/usr/bin/env python3
"""collision-is-not-try-again - a permanent collision must not be answered with "try again".

Wrapper around tools/prove_collision_is_not_try_again.mjs, which exercises the real whWriteError
rather than grepping for a branch. See that file for the reasoning; the short version is that
whWriteError passed DELIBERATE refusals through in their own words but left 23505 (unique violation)
to the caller's "...try again" fallback - and a taken name, tag, code or username never becomes
free, so retrying is the one action that cannot work.

Node-only; skips cleanly when node is absent.
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
    node = shutil.which("node")
    if not node:
        print("SKIP collision-is-not-try-again - node not on PATH")
        return 0
    try:
        r = subprocess.run([node, str(ROOT / "tools" / "prove_collision_is_not_try_again.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL collision-is-not-try-again - the prover timed out at 120s")
        return 1
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("  " + line.strip()[:190])
    if re.search(r"^\s*SKIP", out, re.M):
        return 0
    if re.search(r"^\s*PASS", out, re.M) and r.returncode == 0:
        return 0
    print("FAIL collision-is-not-try-again - a person hitting a taken name/tag/code is told to retry "
          "the one value that can never succeed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
