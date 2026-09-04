#!/usr/bin/env python3
"""pending-submission-reach gate — T108's last silent row (2026-08-26).

Runs tools/prove_pending_submission_reach.mjs. A supervisor's only signal that
work was waiting on them was a realtime subscription living on hive.html, so it
fired while — and only while — they had the board open. A trigger on asset_nodes
and inventory_items now catches every writer: pending rows come from asset-hub
(submit + resubmit), inventory (two paths), logbook, and integrations' bulk CMMS
upsert, and wiring six client sites is the fix-every-path hazard at its worst,
where the miss is invisible — the row lands, nobody is told, nothing errors.

FIVE ASSERTIONS. Two of them are why this design is safe rather than merely
functional:

  submit              -> the hive's supervisors get a push
  non-pending update  -> silent
  already-pending     -> silent (only the TRANSITION into pending is news)
  20 rows at once     -> ONE push, not twenty
  push helper broken  -> the submission still lands

★THE STORM TEST IS THE DESIGN. A per-row notification would turn one CMMS import
into two hundred pushes. The copy names no row precisely so enqueue_user_push's
2-minute dedupe collapses them, and the board is where the count lives — the
dedupe window becomes the storm guard instead of a second mechanism.

★AND THE BLOCKING TEST IS THE SAFETY. The trigger body is wrapped so any failure
is swallowed: a notification is an extra, a submission is the user's work. This
codebase has already paid once for a guard that broke the writes it rode on, so
the gate proves the write survives a deliberately broken notifier rather than
trusting the EXCEPTION clause to be right.

The prover repairs itself: assertion 5 renames a platform-wide helper, so the
probe restores it in a finally AND re-checks at start and end, because a probe
that can outlive its own damage is not acceptable.

Re-drive: node tools/prove_pending_submission_reach.mjs
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


def _run(node: str):
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_pending_submission_reach.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^\s*PASS", out, re.M)), out


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP pending-submission-reach — node not on PATH")
        return 0
    if not _port_open(54321) or not shutil.which("docker"):
        print("SKIP pending-submission-reach — local stack / docker down (psql is the oracle)")
        return 0

    try:
        ok, out = _run(node)
        if not ok:
            ok, out = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL pending-submission-reach — timed out at 180s")
        return 1

    for line in out.strip().splitlines()[-7:]:
        print("  " + line.strip()[:200])
    if not ok:
        print("FAIL pending-submission-reach — a submission did not reach the supervisors, or "
              "notified when it should not have, or a bulk insert stormed, or a broken notifier "
              "blocked the write. See mig 20260826000003 (tg_notify_pending_submission).")
        return 1
    print("PASS pending-submission-reach — submissions reach supervisors from any page, bulk "
          "coalesces to one, and a broken notifier never costs someone their work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
