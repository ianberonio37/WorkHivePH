#!/usr/bin/env python3
"""auto-read-retry — T126: a failed READ recovers itself on reconnect (2026-08-26).

THE FINDING. Reconnect handling on this platform was write-only: offline queues
drain on 'online', logbook syncs, banners repaint — but a failed READ sat behind
a Retry button waiting for a tap. "Manual" assumes somebody is standing there. A
wall-mounted alert board has nobody, so one network blip left a plant staring at
a stale error for the rest of a shift; a phone in a pocket has nobody at the
moment the signal returns.

whListError now registers its retry for auto-recovery, and the six assertions are
as much about RESTRAINT as recovery — an auto-retry that misbehaves is worse than
none, because it hammers a backend that is already unwell:

  helperPresent       the registration helper exists
  noSpuriousCall      registering does not itself call the retry
  retriedOnReconnect  an 'online' event re-runs it            <- the defect
  rateFloorHeld       a second reconnect inside 3s does NOT
  leftRecoveredAlone  a section no longer showing an error is not touched
  droppedDetached     an element removed from the DOM is dropped, not retried
                      forever (the listener-lifecycle leak this repo gates for)

★NO TIMER, EVER. It fires on connectivity events only — 'online', and a tab
becoming visible after an offline spell. A polling retry would turn a backend
outage into a self-inflicted load test.

★AN HONEST NOTE ON THE RESURRECTION. Against the pre-fix utils.js the run goes
RED on the two assertions that decide it (helperPresent, retriedOnReconnect).
Two others — rateFloorHeld and leftRecoveredAlone — also read false there, but
only because they assert "exactly one call" and the pre-fix world made zero. They
are not evidence of anything in that world, and are not counted as such.

Re-drive: node tools/prove_auto_read_retry.mjs
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
        print("SKIP auto-read-retry — node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP auto-read-retry — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_auto_read_retry.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL auto-read-retry — timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-8:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL auto-read-retry — a failed read no longer recovers on reconnect, or the "
              "restraints slipped (rate floor, recovered sections, detached elements). An unattended "
              "screen depends on the first; an unwell backend depends on the rest.")
        return 1
    print("PASS auto-read-retry — failed reads recover on reconnect, once, only while still failing, "
          "and never after the element is gone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
