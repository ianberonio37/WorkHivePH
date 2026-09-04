#!/usr/bin/env python3
"""edge-down-admits-it - T198: a dead edge fn must not become a confident answer.

Edge functions fail independently of the database - a cold start times out, one is
mid-deploy, a region hiccups - and the page keeps working, which is the point of the
client fallback. The danger is the fallback filling the gap with a POSITIVE-LOOKING ZERO.

MEASURED, AND IT WAS REAL. project-manager's clientRollup returned
`critical_path: { item_ids: [], total_days: 0, slack_per_item: {} }` when project-progress
was unreachable. renderCpm() carries a PJ8 guard written for exactly this case - `if (!cp)`
prints "The critical path could not be computed right now" - but AN EMPTY OBJECT IS TRUTHY,
so the guard never fired on the path it was written for. With the function down, a shutdown
project whose real schedule is "12d, 7 of 7 items on the critical path" rendered as:

    CRITICAL PATH 0d - 0 of 7 items on critical path      [full Gantt beneath]

Not a blank and not an error: a confident INVERSION, on the screen a supervisor uses to
plan a plant outage. Fixed by returning `critical_path: null` so the existing message
speaks - every consumer already used optional chaining. The EVM half of that same fallback
had received its marker (evm_reason: 'unavailable'); the CPM half was left behind, which is
the sibling-fix pattern this codebase keeps meeting.

THE ASSERTION, both directions: with project-progress forced to 503 the pane SAYS it could
not compute, and with the function up it still renders a real schedule. A gate that only
checked the failure case would pass on a pane that is permanently broken.

Re-drive: node tools/prove_edge_down_admits_it.mjs
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
        print("SKIP edge-down-admits-it - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)) or not shutil.which("docker"):
        print("SKIP edge-down-admits-it - local stack / docker down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_edge_down_admits_it.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*(PASS|SKIP)", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL edge-down-admits-it - timed out at 600s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if not ok:
        print("FAIL edge-down-admits-it - with the schedule engine unreachable the pane must SAY so. A")
        print("    '0d, 0 of N items on the critical path' is not an empty state, it is a confident")
        print("    inversion of the truth on the screen used to plan a plant outage.")
        return 1
    print("PASS edge-down-admits-it - the schedule pane renders a real critical path when the engine "
          "answers, and admits it cannot compute when the engine is down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
