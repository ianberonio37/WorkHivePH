#!/usr/bin/env python3
"""queue-survives-restart gate - T14's third half (2026-08-27).

Runs tools/prove_queue_survives_restart.mjs. The offline-queued family proves a write is HELD; the
drain gate proves it DRAINS exactly once. Both stay inside ONE page life. This one puts a full
document RESTART between the enqueue and the reconnect, which is what actually happens in a plant:
the worker logs the job in a dead zone, pockets the phone, and the PWA is gone - reclaimed by the
OS or simply closed - before signal returns.

WHY THAT IS A DIFFERENT SURFACE, NOT A VARIATION. The queue is created by a `_ensure<X>Queue()`
accessor and its auto-sync is attached INSIDE that accessor, so the drain only ever happens if a
FRESH page life calls it. T14 already measured what that costs when it does not: pm-scheduler's
defer race lost the queue on 2 of 5 loads, silently. A queue whose rows persist but whose sync is
never re-attached is worse than no queue at all - the work is neither sent nor lost but INVISIBLE,
and the worker was told it was saved.

Five assertions: HELD (zero server writes offline), PERSISTS (the item is still in IndexedDB after
the restart, read from the store directly rather than through the page object a restart destroys),
REWIRED (the fresh life re-creates the queue and re-attaches auto-sync), DRAINED, and ONCE (one row
after a further settle, store emptied). Writes a MARKED row and deletes it; ABORTS on dirty state.

Teeth: `node tools/prove_queue_survives_restart.mjs --teeth` suppresses whCreateQueue on the
restarted document, reproducing the defer race's end state. REWIRED goes false and the row is left
stranded in the store, while PERSISTS stays true - so the assertions are shown to be independent
and the prover is shown to see the defect it was built for.

Discipline (carried from validate_queue_drain.py):
  - retry-once before failing (full-suite live gates flake under load).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - utf-8 pinned on the subprocess decode; PASS matched line-anchored.
  - SKIPs cleanly when node / the local stack is absent - a gate that cannot run must say SKIP.
  - the prover ABORTS (exit 2) on dirty pre-state rather than deleting rows it did not create.

Re-drive: node tools/prove_queue_survives_restart.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str) -> tuple[bool, str]:
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_queue_survives_restart.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(re.search(r"^\s*PASS", out, re.M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP queue-survives-restart — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP queue-survives-restart — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL queue-survives-restart — timed out at 300s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:240]}")
    if not ok:
        print("FAIL queue-survives-restart — the queued write did not survive the restart, the fresh "
              "page life did not re-attach its sync, or it drained wrong.")
        return 1
    print("PASS queue-survives-restart — held offline, survived a document restart, rewired its sync, "
          "drained once, store emptied, probe row cleaned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
