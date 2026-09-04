#!/usr/bin/env python3
"""hive-rename-reaches - T140: a rename must reach the OTHER devices (2026-08-26).

*** THIS GATE EXISTS BECAUSE THE TRAJECTORY'S RECORDED PREMISE WAS WRONG, IN BOTH
HALVES. *** T140's basis read that hive rename "does not exist - no UI, no update
path (grep: zero rename/hive_name edit sites in hive.html)" and concluded that no
stale-name propagation class could exist. But hive.html renames a hive, and a
live test showed the consequence: after another device renamed the plant, this
session kept showing the OLD name on its board and in its chrome, because every
page trusts localStorage.wh_hive_name and nothing re-read hives.name. That cache
is written at join/switch time, so "eventually" can mean weeks. A grep that
misses one line turns a real defect into a recorded absence.

THE FIX is central: whReconcileHiveName (utils.js) asks the server what this hive
is called, once per load, and corrects the cache and the glass when they
disagree. It is best-effort by construction - a page whose check fails keeps the
cached name, which is what it would have shown anyway - and it joins the board's
allSettled so it can never stop the page loading.

THE TEST'S SHAPE IS THE ONLY ONE THAT CAN SEE THIS: the rename happens OUTSIDE
the session being measured, straight into the database, exactly as another
supervisor's browser would. A test that renamed through the same page would prove
only that a page can update itself, which was never in doubt.

Three assertions, and the third is the one that matters: the cache is corrected,
the board title is corrected, and the old name appears NOWHERE - because chrome
that fixes its title while a sidebar keeps the old name is still showing two
truths. Resurrection: all three RED against the pre-fix utils.js.

The hive's name is restored in a finally block and the restore is verified.

Re-drive: node tools/prove_hive_rename_reaches.mjs
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
        print("SKIP hive-rename-reaches - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)) or not shutil.which("docker"):
        print("SKIP hive-rename-reaches - local stack / docker down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_hive_rename_reaches.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*(PASS|SKIP)", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL hive-rename-reaches - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-8:]:
        print("  " + line.strip()[:150])
    if not ok:
        print("FAIL hive-rename-reaches - a hive renamed on one device still reads as its old name on "
              "another. Check whReconcileHiveName is called with a live db handle on page load.")
        return 1
    print("PASS hive-rename-reaches - a rename done elsewhere corrects this session's cache and glass, "
          "with no stale name left anywhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
