#!/usr/bin/env python3
"""ci_gate.py - Pillar DR (Delivery & Recovery): the LOCAL-runnable CI gate.
================================================================================
Mirrors what the (written-but-not-enabled) GitHub Actions workflow runs, but
LOCALLY and NON-MUTATING by default - so you can run "CI" before pushing without
the run_platform_checks --fast artifact-regen hazard in a dirty tree. Wraps the
existing sibling runners; invents nothing.

Stages (default = --light):
  1. fullstack_dev.py --self-test   - orchestrator wiring ($0, offline)
  2. fullstack_dev.py pillars       - per-pillar/per-phase scorecard (writes JSON only)
  3. verify_backups.py              - migration/backup integrity (read-only)

  --full   ALSO runs run_platform_checks.py --fast (the heavy G0 ratchet). Use on
           a CLEAN CI checkout only - it regenerates ~33 report artifacts, which
           pollutes a dirty local tree (documented ops hazard).

Exit 0 = gate green; non-zero = a stage failed (the count of failed stages).
This is the local half of "enable the CI gate"; the GH workflow yaml stays the
prod trigger (Ian-gated).
"""
from __future__ import annotations
import io
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
GREEN = "\033[92m"; RED = "\033[91m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def run(label: str, args: list[str]) -> bool:
    print(f"\n{CYAN}>>> {label}{RESET}\n    $ {' '.join(str(a) for a in args)}")
    proc = subprocess.run([PY, *map(str, args)], cwd=str(ROOT))
    okk = proc.returncode == 0
    print(f"    {(GREEN + 'PASS' + RESET) if okk else (RED + 'FAIL' + RESET)}  ({label})")
    return okk


def main() -> int:
    full = "--full" in sys.argv
    print(f"{BOLD}{CYAN}\n================ LOCAL CI GATE (Pillar DR) ================{RESET}")
    print(f"  mode: {'FULL (incl. heavy G0 ratchet)' if full else 'LIGHT (non-mutating; --full for the ratchet)'}")

    stages: list[tuple[str, list[str]]] = [
        ("orchestrator self-test", ["tools/fullstack_dev.py", "--self-test"]),
        ("gateway pillar scorecard", ["tools/fullstack_dev.py", "pillars"]),
        ("backup / restore integrity", ["tools/verify_backups.py"]),
    ]
    if full:
        stages.append(("G0 guardian ratchet (--fast)", ["run_platform_checks.py", "--fast"]))

    results = [(label, run(label, args)) for label, args in stages]
    failed = [label for label, okk in results if not okk]

    print(f"{BOLD}{CYAN}\n================ CI GATE SUMMARY ================{RESET}")
    for label, okk in results:
        print(f"  {(GREEN + 'PASS' + RESET) if okk else (RED + 'FAIL' + RESET)}  {label}")
    if failed:
        print(f"\n{RED}{BOLD}  CI GATE: BLOCK{RESET} - {len(failed)} stage(s) failed: {', '.join(failed)}")
        return len(failed)
    print(f"\n{GREEN}{BOLD}  CI GATE: GREEN{RESET} - safe to push (prod deploy stays Ian-gated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
