#!/usr/bin/env python3
"""engineer-lens-is-one-lens - T52: two switches called Engineer must not contradict (2026-08-26).

There is no engineer ROLE here: hive_members.role is CHECK-constrained to worker | supervisor.
"Engineer" exists twice as a LENS - nav-hub's localStorage 'wh_nav_mode' (which filters TOOLS) and
asset-hub's 'wh_asset_view' (which decides PANELS). Independent keys, same user-facing word.

TWO DEFECTS, both user-visible, both caught here:
  1. Someone who picked the Engineer lens in the hub still landed in asset-hub's WORKER view,
     because an unset wh_asset_view reads as false. They declared themselves once and had to
     declare it again, with nothing saying a second switch existed.
  2. _syncAssetView ran from exactly two places - the toggle's click handler and loadDetailFmea -
     so on a fresh load the button kept its markup default and read "Show Reliability Workbench"
     (i.e. off) even for someone whose stored choice was engineer. They would press it to enable
     what was already enabled, and disable it.

★THE FIX IS A DEFAULT, NOT A MERGE. The scopes really differ - a tool filter is not a panel toggle
- so only the UNSET case derives from the hub lens; an explicit local toggle still wins, because
the last thing someone did on this page is better evidence than a global lens. Four cases are
driven for exactly that reason: a fix that merely mirrored the hub would pass the first two and
destroy the local choice.

★AND THE ORACLE TOOK THREE TRIES, which is the transferable part. Asking _assetViewIsEngineer()
directly failed pre-fix with 'noFn' - a fact about the patch, not the user. Reading the reliability
CARD's visibility failed the other way, since that card lives in the asset detail pane and is
hidden at load regardless of lens. The honest signal is the toggle BUTTON's aria-expanded: set
straight from the lens, independent of any selection, and present in the pre-fix world so the
comparison is real.

Re-drive: node tools/prove_engineer_lens_is_one_lens.mjs
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
        print("SKIP engineer-lens-is-one-lens - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP engineer-lens-is-one-lens - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_engineer_lens_is_one_lens.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if re.search(r"^\s*SKIP", out, re.M):
            return None, out
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if ok is False:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL engineer-lens-is-one-lens - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP engineer-lens-is-one-lens - no active hive for the test account")
        return 0
    if not ok:
        print("FAIL engineer-lens-is-one-lens - the two Engineer switches disagree, or the toggle does not")
        print("    describe its own state at load. Someone who says 'I am an engineer' once should not")
        print("    have to say it again on the next page - and should not be overruled when they say")
        print("    something different on THIS one.")
        return 1
    print("PASS engineer-lens-is-one-lens - the hub lens supplies the default, an explicit local choice "
          "still wins, and the toggle tells the truth before it is touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
