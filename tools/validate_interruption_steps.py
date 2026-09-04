#!/usr/bin/env python3
"""interruption-steps — T122: nothing lost, at EVERY step (2026-08-26).

The first T122 walk injected an interruption at ONE step and found it green. One
step is a spot check: a multi-step wizard saves on its own schedule, so a step
where the draft is not yet written is invisible to a probe that only tests the
step where it is. A phone rings whenever it rings.

This fills the logbook wizard progressively and, at the end of EACH step, injects
the harshest realistic interruption — a FULL RELOAD, the OS killing a
backgrounded tab — then asserts everything typed so far comes back.

★THE MECHANISM IS logbook's OWN saveDraft/restoreDraft, NOT whAutoSaveDraft.
T122's first write-up credited the shared helper; logbook does not use it. That
matters beyond tidiness: the shared helper received OWNER STAMPING in T121, so
one worker's draft cannot surface for the next person on a shared plant phone,
and logbook — the platform's richest personal-text form — was never touched by
that fix. Checked rather than assumed: logbook is safe anyway by a different
route, because DRAFT_KEY is 'wh_logbook_draft_' + WORKER_NAME and the next
person's page computes a key it cannot read. Two mechanisms, one guarantee —
worth writing down before someone unifies them and removes a protection they did
not know was there.

★THE PROBE REFUSES TO MEASURE A VALUE THAT DID NOT TAKE. Its first run reported
"the draft lost f-root-cause" — a <select>, where assigning a value that is not
one of its options silently yields "". Nothing had been set, so nothing could be
lost, and the defect did not exist.

Mutation-proven: with restoreDraft disabled, 0 of 3 steps keep their work and
every lost field is named.

Re-drive: node tools/prove_interruption_steps.mjs
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
        print("SKIP interruption-steps — node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP interruption-steps — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_interruption_steps.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL interruption-steps — timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-5:]:
        print("  " + line.strip()[:170])
    if not ok:
        print("FAIL interruption-steps — a worker's typing did not survive an interruption at some "
              "step of the logbook wizard. Losing a half-written repair entry is the failure this "
              "whole family exists to prevent.")
        return 1
    print("PASS interruption-steps — the wizard keeps a worker's typing through a kill at every step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
