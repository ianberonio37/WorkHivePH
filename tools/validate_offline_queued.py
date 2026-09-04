#!/usr/bin/env python3
"""offline_queued family gate — T14's lock spoke (2026-08-25).

Runs tools/prove_offline_queued.mjs across ALL 8 queue-page cases (the complete
whCreateQueue roster + logbook's own queue) and FAILs on any case that cannot
prove the queue-and-tell oracle: offline, the write is HELD (the queue's own
store grows or the record is on screen), the person is TOLD it will sync, and
nothing claims the refusal wording.

WHY A GATE: the CG family's offline cell was `offline_refusal` — the WRONG
oracle for queue pages (green credited a refusal that must not exist). The
prover replaced it for these 8 pages; without a registered gate the family
regresses silently (the queue-registration defer race THIS oracle caught on
pm-scheduler — 2 of 5 runs lost — is exactly the class that returns quietly).

Discipline carried from the bank's own lessons:
  - retry-once per case before failing (full-suite live gates flake under load;
    the pm-completion case's comment records the re-run-first rule).
  - node invoked DIRECTLY, never npx (the repo path contains an ampersand).
  - skips cleanly when node or the local stack (Flask :5000 / Supabase :54321)
    is absent — a gate that cannot run must say SKIP, not PASS.

Re-drive one case: node tools/prove_offline_queued.mjs --case <name>
"""
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CASES = [
    "logbook-entry",
    "pm-completion",
    "community-post",
    "inventory-part",
    "dayplanner-item",
    "skillmatrix-targets",
    "projectmanager-progress",
    "assethub-fmea",
]


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run_case(node: str, case: str) -> tuple[bool, str]:
    # encoding pinned: node emits UTF-8; Windows' locale decode (cp1252) mangles the
    # prover's em-dash and the PASS marker with it — the first run scored 8 real PASSes
    # as 8 FAILs on exactly this (the gate's own first instrument bug).
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_offline_queued.mjs"), "--case", case],
        cwd=str(ROOT), capture_output=True, text=True, timeout=240,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(__import__("re").search(r"^\s*PASS", out, __import__("re").M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP offline-queued-family — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP offline-queued-family — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    failures = []
    for case in CASES:
        try:
            ok, tail = _run_case(node, case)
            if not ok:
                # Full-suite live gates flake under load — one retry before it counts.
                ok, tail = _run_case(node, case)
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {case}: {tail[:180]}")
            if not ok:
                failures.append(case)
        except subprocess.TimeoutExpired:
            print(f"  FAIL  {case}: timed out at 240s (twice would too — counted once)")
            failures.append(case)

    if failures:
        print(f"FAIL offline-queued-family — {len(failures)}/{len(CASES)} cases red: {', '.join(failures)}")
        return 1
    print(f"PASS offline-queued-family — {len(CASES)}/{len(CASES)} queue pages hold + tell offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
