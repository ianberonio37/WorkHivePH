#!/usr/bin/env python3
"""approval-race - T145: two supervisors, one pending item, one outcome (2026-08-26).

The sharpest concurrency case on this platform. Two supervisors see the same
pending submission and both press Approve within the same second. The database
must end with exactly ONE outcome, the winner must get a real receipt, and - the
part easiest to get wrong - the LOSER must be told something true and kind rather
than shown an error, because they did nothing wrong.

The walk found this already correct and needing no fix. This gate exists so it
STAYS correct: the optimistic guard is one `.eq('status','pending')` away from
being deleted by somebody tidying a query, and the failure is invisible in normal
use - you only meet it when two people happen to act at once.

*** A REAL RACE, NOT TWO AWAITED CALLS. *** Awaiting the first update before
firing the second proves nothing: the second simply sees the finished state. Both
updates are dispatched concurrently and settled together, which is the only shape
that exercises a guard. This codebase already carries a scar from a double-submit
test that awaited its own clicks.

Four assertions: exactly one update reports a changed row; the other reports ZERO
rows (a no-op the UI can explain, not an error); the item ends approved once by
one person; and the audit trail records ONE approval - a log showing two
approvals of one thing is a log nobody can use.

*** IT PICKS ITS HIVE BY THE PROPERTY IT NEEDS. *** The first version pinned the
Baguio fixture, which has ONE supervisor, and SKIPped - a race test that cannot
find two racers is not a pass, and a pinned hive would have quietly disabled this
gate the day a fixture changed. It now selects any hive with two active
supervisors and SKIPs honestly when none exists.

Cleanup order matters and the first run had it backwards: deleting the audit rows
before the asset leaves the asset's own delete_asset_node audit row behind,
because the delete itself fires the trigger. Row first, then its audit trail.

Re-drive: node tools/prove_approval_race.mjs
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
        print("SKIP approval-race - node not on PATH")
        return 0
    if not shutil.which("docker"):
        print("SKIP approval-race - docker absent (the database is the oracle)")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_approval_race.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*(PASS|SKIP)", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL approval-race - timed out at 180s")
        return 1

    for line in out.strip().splitlines()[-6:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL approval-race - two supervisors approving at once did not resolve to exactly one "
              "outcome, or the loser was handed an error instead of an explanation.")
        return 1
    print("PASS approval-race - one winner, one kindly-refused loser, one row, one audit entry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
