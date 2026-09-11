#!/usr/bin/env python3
"""walk_archetypes.py — run journey archetypes SERIALLY, keep every line, and refuse to start on a host
that cannot survive the walk.

WHY (W3-JN, 2026-09-10). Two mistakes in one chain, both mine, both cheap to prevent:

  1. I ran the archetypes as `for A in ...; do node prove_full_journeys.mjs --archetype $A | tail -2; done`.
     `tail -2` buffers, so nothing appeared until an archetype ENDED - I was blind to a walk's progress for
     its whole run - and when J25 and J19 died the only surviving line was `Node.js v24.14.1`, the last line
     of a stack trace whose message had been discarded. Twenty rows lost and no diagnosis kept.

  2. I then MISDIAGNOSED the crashes, and that is the costlier mistake. I blamed the 500-check `--fast`
     suite I had started beside them - free RAM had fallen to 0.67 GB, which was true - and wrote it up
     that way. They had actually died on a `ReferenceError: partnerCtx is not defined`: a `let` declared
     inside a `try` whose `finally` closed it, from an edit I had made minutes earlier. Every walk after
     that edit would have crashed on an idle machine.

     Two things made a wrong cause feel settled. The message had been thrown away by mistake (1), so the
     loudest surviving fact was a memory gauge; and a real, adjacent, measurable problem is the most
     seductive wrong answer. Building on it did further harm - I set this file's precondition to 1.2 GB,
     a level the host never reaches, so the guard parked the very queue it was meant to protect.
     **When a crash leaves no message, the job is to recover the message, not to explain the crash.**

  3. The contention is nevertheless real, and my check of it was also wrong. I asked "does --fast launch a
     browser?", searched the registered checks for `.mjs` scripts, found one that opens no browser, and
     concluded no. Grepping every fast check's SOURCE for `playwright|chromium|browser.new` finds 18 of
     the 518 driving a browser, all of them Python (validate_playwright_coverage, validate_landing, the
     a11y keyboard walk). I answered a question about the whole suite by searching for the one file
     extension the tools I happened to be editing used.

So: full output to a per-archetype log, a live line as each story lands, and a precondition that is about
the competing JOB (suite_running) with only a low floor on memory - because the floor is what blocked the
queue, and the job check is what would have prevented the contention.

    python tools/walk_archetypes.py J25 J19
    python tools/walk_archetypes.py J27 --min-free-gb 0.5
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".tmp"


def free_gb() -> float | None:
    """Free physical memory in GB, or None if it cannot be read (never guessed)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)"],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return None


def suite_running() -> bool:
    """Is a run_platform_checks.py suite alive right now?

    ★A MEMORY SNAPSHOT IS NOT A PROMISE ABOUT THE NEXT TEN MINUTES (2026-09-10). The first version of this
    file checked free RAM once and started - and it started J25 the moment the host crossed 1.2 GB while
    the 500-check suite was STILL RUNNING, so both grew and the host fell back to 0.51 GB. The precondition
    has to be about the competing JOB, not only about this instant's headroom: a suite that is still going
    will take the room back whatever the gauge said a second ago.
    """
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*run_platform_checks*' } | Measure-Object).Count"],
            capture_output=True, text=True, timeout=40)
        return int((out.stdout or "0").strip() or 0) > 0
    except Exception:
        return False          # unreadable is not a refusal, same rule as the memory gauge


def wait_for_room(need: float, patience_s: int) -> bool:
    """Block until the host has `need` GB free AND no check-suite is running, or give up."""
    waited = 0
    while True:
        f = free_gb()
        busy = suite_running()
        if f is None and not busy:
            print(f"  ! free memory unreadable - proceeding (an unknown is not a refusal)")
            return True
        if busy:
            if waited >= patience_s:
                print(f"  ! run_platform_checks is STILL running after {waited}s - REFUSING to start. "
                      f"Two heavy jobs on this host is what killed J25 and J19.")
                return False
            print(f"  … run_platform_checks is running ({f if f is not None else '?'} GB free) - waiting")
            time.sleep(20)
            waited += 20
            continue
        if f is not None and f >= need:
            return True
        if waited >= patience_s:
            print(f"  ! still only {f:.2f} GB free after {waited}s (need {need}) - REFUSING to start. "
                  f"A walk begun here is a walk that dies half way and reports nothing about the platform.")
            return False
        print(f"  … {f:.2f} GB free, need {need} - waiting (something else is using this host)")
        time.sleep(20)
        waited += 20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archetypes", nargs="+")
    # ★AND THE THRESHOLD MUST BE CALIBRATED TO THE HOST'S IDLE STATE, NOT TO THE CRASH NUMBER.
    # The first version demanded 1.2 GB because the walks died at 0.67. That reads like caution and it
    # blocked the very queue it was written to protect: measured with everything else stopped, this host
    # idles at ~0.5 GB available - vmmemWSL 1.0 GB, three VS Code processes 1.2 GB, docker-backend 0.3,
    # claude 0.35 - and every successful walk this session ran in exactly that. So 1.2 GB is a state this
    # machine never reaches, and a precondition that is never satisfiable is an outage, not a safeguard.
    # What actually predicted the crash was not the number but the COMPETING JOB (see suite_running):
    # two Playwright users plus 500 checks. The floor here is only a guard against a genuinely starved
    # host; the real interlock is the job check.
    ap.add_argument("--min-free-gb", type=float, default=0.35,
                    help="floor against a genuinely starved host; the real interlock is suite_running()")
    ap.add_argument("--patience", type=int, default=600, help="seconds to wait for room before refusing")
    ap.add_argument("--bank", action="store_true",
                    help="after each archetype, bank the rows the prover called ok (BAD rows are never banked)")
    args = ap.parse_args()
    TMP.mkdir(exist_ok=True)

    rc = 0
    for a in args.archetypes:
        print(f"\n=== {a} ===", flush=True)
        if not wait_for_room(args.min_free_gb, args.patience):
            rc = 1
            continue
        log = TMP / f"walk_{a}.log"
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            p = subprocess.Popen(
                [("node"), str(ROOT / "tools" / "prove_full_journeys.mjs"), "--archetype", a],
                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in p.stdout:                      # EVERY line kept, and echoed as it happens
                fh.write(line)
                # FLUSH each line. `bufsize=1` line-buffers the PIPE; it says nothing about this file
                # handle, which buffers ~8 KB by default - so a walk killed mid-run would leave the log
                # EMPTY, which is precisely the failure this file exists to prevent. Caught by watching
                # rows appear on stdout while `wc -l` on the log still read 0.
                fh.flush()
                s = line.rstrip()
                if s.strip().startswith(("ok", "BAD", "PASS", "FAIL")) or "Error" in s or "error" in s:
                    print(f"  {s[:150]}", flush=True)
            p.wait()
        if p.returncode != 0:
            rc = 1
            print(f"  ! {a} exited {p.returncode} - full output in {log.relative_to(ROOT)}")

        # ★BANK WHILE THE EVIDENCE IS FRESH, and only what the prover called ok. Opt-in, because writing
        # the registry is a deliberate act - but leaving a finished archetype unbanked until someone
        # remembers is how a walk's result becomes a walk nobody counted. `bank_journey_run.py` refuses
        # every BAD row by design (a year-2 fixture gap, a load artifact and a product defect are three
        # different dispositions and a script must not flatten them), so this can only ever advance rows
        # the walk actually proved.
        if args.bank:
            res = TMP / f"full_journeys_{a}.json"
            if not res.exists():
                print(f"  ! {a}: no result file to bank")
                continue
            for cmd in ([sys.executable, str(ROOT / "tools" / "bank_journey_run.py"), str(res)],
                        [sys.executable, str(ROOT / "tools" / "advance_trajectory.py"),
                         "--batch", str(TMP / "bank_journeys.json")]):
                out = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=900)
                for ln in (out.stdout or "").splitlines():
                    if any(k in ln for k in ("bankable", "advanced", "NOT banked", "PASS", "FAIL")):
                        print(f"    {ln.strip()[:150]}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
