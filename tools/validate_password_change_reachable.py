#!/usr/bin/env python3
"""password-change-reachable - T59: a signed-in worker can find how to change their password.

Wrapper around tools/prove_password_change_reachable.mjs. See that file for the full reasoning;
the short version is that this platform has no settings/account/profile page at all, and the only
password write runs inside the PASSWORD_RECOVERY event - so changing a password meant leaving the
app for the landing page's forgot-password flow, with nothing anywhere saying so.

Skips cleanly when node or the local stack is absent (live gate).
"""
import io
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP password-change-reachable - node not on PATH (live gate)")
        return 0
    if not _port_open(5000) or not _port_open(54321):
        print("SKIP password-change-reachable - local stack down (Flask :5000 / Supabase :54321)")
        return 0
    try:
        r = subprocess.run([node, str(ROOT / "tools" / "prove_password_change_reachable.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print("FAIL password-change-reachable - the walk timed out at 300s")
        return 1

    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("  " + line.strip()[:190])
    if re.search(r"^\s*SKIP", out, re.M):
        return 0
    if re.search(r"^\s*PASS", out, re.M) and r.returncode == 0:
        return 0
    print("FAIL password-change-reachable - a signed-in worker cannot find how to change their password.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
