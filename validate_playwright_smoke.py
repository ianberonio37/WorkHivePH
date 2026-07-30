"""
Playwright UI Smoke Validator — guardian wrapper for tests/*.spec.ts.

Runs the full Playwright suite via `npx playwright test --reporter=json`
and parses results into the platform-validator format. Provides:

  L1  Test infrastructure healthy   playwright.config.ts present, tests/ exists
  L2  Suite ran without infra error  npx command succeeded
  L3  All tests passed               every spec.ts file's tests green

The validator skips gracefully (no FAIL) when:
  - playwright.config.ts is missing
  - npx is unavailable
  - the Flask seeder isn't running on :5000 (we ping it first; if down,
    skip rather than fail, since this gate is meant to run when the
    user explicitly stands up the test environment)

To run manually:
  python validate_playwright_smoke.py

To run as part of run_platform_checks.py the Flask seeder + Docker
Supabase must be up. Otherwise the gate cleanly skips.

Skills consulted: qa (Playwright reporter parsing), platform-guardian
(graceful skip pattern, parseable output), devops (subprocess timeout,
no infinite wait on broken environment).
"""
from __future__ import annotations

import json
import os
import re
import sys
import subprocess
import time
import urllib.request

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result


CONFIG_FILE = "playwright.config.ts"
TESTS_DIR   = "tests"
SEEDER_URL  = "http://127.0.0.1:5000"
REPORT_FILE = "playwright-report.json"
# Measured, not guessed: `tests/logbook.spec.ts` alone takes ~31s (3 tests, real sign-in, video+trace
# capture), so the 7-spec worker-critical subset costs ~215s. A 180s bound could not fit its own declared
# scope, which is how this gate spent its life either timing out or reporting a stale report's verdict.
# The bound now fits the scope; if the subset grows, this number is what must move with it.
RUN_TIMEOUT = 300  # seconds - bounds the SMOKE_SPECS subset, and the process TREE is killed on expiry


# Ping the path the app is actually SERVED from, not the bare root.
#
# THE BUG THIS FIXES (found 2026-07-30): this validator had been silently SKIPPING — "Flask seeder not
# running at http://127.0.0.1:5000" — while the seeder was up and answering. Measured:
#
#     http://127.0.0.1:5000            -> 200, but after 5.86 SECONDS
#     http://127.0.0.1:5000/workhive/  -> 200 in 0.01 seconds
#
# The bare root is slow enough to blow a 2-second timeout, so the probe concluded the whole local stack
# was down and deferred all three checks. A gate that skips is indistinguishable from a gate that passes
# in a suite summary, so the UI smoke suite simply had not run — the same "a skip reads like coverage"
# class this session found in two authority partitions of the test bank.
#
# `/workhive/` is both instant and correct: it is where the site lives ([[feedback_workhive_url_prefix]])
# and the path the tests themselves drive. The timeout is 6s rather than 2 so a cold or loaded seeder is
# reported honestly as slow-but-up instead of absent.
SEEDER_PING = SEEDER_URL + "/workhive/"

# THE SMOKE SUBSET — and why this gate needed one.
#
# It ran the WHOLE `tests/` tree: **138 spec files**, the entire platform E2E suite. Its own registration
# says `skip_if_fast: True  # ~3 min runtime; opt-in via full guardian`, so a ~3-minute gate was always the
# intent — the implementation just never revisited its scope as the suite grew from a handful of specs to
# 138. The result was a gate that could not pass by construction: `RUN_TIMEOUT` is 180s, the suite needs
# far longer, so every run either timed out or (before the bound was made real) hung for 20+ minutes.
#
# The subset is NOT hand-picked. It is the platform's own `WORKER_CRITICAL_PAGES` list, lifted from
# `validate_sw_offline.py` — the pages a technician on the factory floor is expected to be able to open,
# which is exactly the set whose silent failure matters most. Borrowing an existing, already-justified
# list beats inventing a new one, and it means the two gates agree about what "critical" means.
#
# Full-suite coverage is NOT lost by narrowing here: the bank's own journey lane
# (`marketplace-bank-journey`) runs the two-context marketplace specs, and other arcs carry their own
# spec gates. This gate's job is the smoke tier.
SMOKE_SPECS = [
    "tests/logbook.spec.ts",
    "tests/inventory.spec.ts",
    "tests/pm-scheduler.spec.ts",
    "tests/parts-tracker.spec.ts",
    "tests/shift-brain-freshness.spec.ts",
    "tests/asset-hub-telemetry.spec.ts",
    "tests/hive.spec.ts",
]


def _seeder_up() -> bool:
    try:
        with urllib.request.urlopen(SEEDER_PING, timeout=6) as _:
            return True
    except Exception:
        return False


def _run_playwright() -> tuple[int, str, str]:
    """Run the suite. Returns (exit_code, stdout, stderr).

    Uses Z: drive on Windows if available (avoids the `&` in path bug per
    memory: 'Deploy workaround — subst Z:'). If Z: doesn't map back to the
    project root, falls back to native cwd.
    """
    # `node <cli.js>`, NOT `npx`. npx is broken in this repo because the project path contains `&`
    # ("Build & Sell"): the shim splits cwd on the ampersand and looks for @playwright in the parent
    # directory ([[reference_npx_ampersand_path_bug]]). The relative path has no `&` in it, so this works
    # from the real cwd and no longer depends on a `Z:` subst happening to be mapped.
    # NO `--reporter=json` on the command line. That flag OVERRIDES playwright.config.ts's reporter list
    # and sends the JSON to **stdout**, so nothing ever writes `playwright-report.json` — and this
    # validator reads the FILE. The config already declares
    # `['json', { outputFile: 'playwright-report.json' }]`, so running without the flag puts the report
    # exactly where the parser looks ([[reference_npx_ampersand_path_bug]] records this same trap).
    #
    # It is the last of four defects that stacked in this one function, and the reason the gate's failure
    # was so hard to read: with the file never written, the parser fell back to a THREE-HOUR-OLD report and
    # narrated its contents as this run's result.
    cmd = ["node", os.path.join("node_modules", "@playwright", "test", "cli.js"),
           "test", *SMOKE_SPECS]
    cwd = None
    if sys.platform == "win32" and os.path.exists("Z:\\playwright.config.ts"):
        cwd = "Z:\\"

    # THE BOUND HAS TO KILL THE TREE, not just the parent.
    #
    # This used to be `subprocess.run(..., timeout=RUN_TIMEOUT, shell=True)`. On Windows that spawns
    # cmd.exe -> npx -> node -> N browser workers, and the timeout kills only cmd.exe. The workers were
    # ORPHANED and kept running; worse, `capture_output=True` then blocks waiting to drain pipes those
    # orphans still hold, so the call itself sailed past its own 180s bound. Measured 2026-07-30: a gate
    # that had "timed out" at 180 seconds still had **37 live node/python processes** thirteen minutes
    # later, and the suite recorded it as 1200.1s. Orphaned browser workers are also the most likely
    # source of the "concurrency contamination" this session blamed on itself three times.
    #
    # Popen + kill-the-tree makes RUN_TIMEOUT mean what it says.
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, cwd=cwd)
    except FileNotFoundError:
        return 127, "", "node or @playwright/test/cli.js not found"
    try:
        out, err = proc.communicate(timeout=RUN_TIMEOUT)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            # /T = the whole tree, /F = force. Without /T the browser workers survive the gate.
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, check=False)
        else:
            proc.kill()
        try:
            proc.communicate(timeout=15)
        except Exception:
            pass
        return 124, "", (f"timeout after {RUN_TIMEOUT}s - the process TREE was killed. If this is the "
                         f"normal runtime, the gate is running more than a smoke subset.")


def _parse_report(started_at: float | None = None) -> dict:
    """Load the JSON report, but ONLY if this run wrote it.

    A stale report is the worst input this validator can have, because it reports fiction in the exact
    grammar of a real finding. Observed 2026-07-30: the run was killed at its 180s bound, this function
    happily loaded a report written **three hours earlier** by a targeted run of one spec file, and the
    gate announced *"9 of 9 tests FAILed"* with five named test titles. The report's own stats said
    `expected: 0, unexpected: 0, skipped: 9` — nine tests SKIPPED, zero failed, nothing run at all
    ([[feedback_a_dead_fixture_invents_page_defects]] is the same shape: plausible, specific, entirely
    fictional).

    So freshness is a precondition, not a detail. `started_at` is the wall clock from just before the
    suite was launched; a report not modified after that instant did not come from this run.
    """
    if not os.path.exists(REPORT_FILE):
        return {"loaded": False, "reason": "no report file"}
    if started_at is not None and os.path.getmtime(REPORT_FILE) < started_at:
        age = started_at - os.path.getmtime(REPORT_FILE)
        return {"loaded": False,
                "reason": f"report is STALE — last written {age / 60:.0f} min before this run started, "
                          f"so it describes a different run and is not evidence about this one"}
    try:
        with open(REPORT_FILE, encoding="utf-8") as f:
            return {"loaded": True, **json.load(f)}
    except Exception as e:
        return {"loaded": False, "reason": f"parse error: {e}"}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPlaywright UI Smoke Validator"))
    print("=" * 60)

    CHECK_NAMES = ["infra_present", "suite_ran", "all_passed"]
    CHECK_LABELS = {
        "infra_present": "L1  playwright.config.ts + tests/ directory present",
        "suite_ran":     "L2  npx playwright test exited cleanly",
        "all_passed":    "L3  All UI smoke tests passed",
    }
    issues = []

    # L1: infra check
    if not os.path.exists(CONFIG_FILE):
        issues.append({
            "check": "infra_present", "skip": False,
            "reason": f"{CONFIG_FILE} missing — Playwright config not initialised"
        })
    if not os.path.isdir(TESTS_DIR):
        issues.append({
            "check": "infra_present", "skip": False,
            "reason": f"{TESTS_DIR}/ missing — no Playwright tests to run"
        })
    if issues:
        n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
        sys.exit(1 if n_fail > 0 else 0)

    # Skip gracefully if Flask seeder isn't up — Playwright would just
    # fail every test on ECONNREFUSED. The skip is informational.
    if not _seeder_up():
        print("  \033[93mSKIP\033[0m  Flask seeder not running at " + SEEDER_URL)
        print("        Start it via launch_workhive_tester.bat or `python test-data-seeder/app.py`,")
        print("        then re-run this validator.")
        # We mark all 3 as skip (info only) rather than fail
        for cn in CHECK_NAMES:
            issues.append({"check": cn, "skip": True,
                "reason": "Flask seeder offline — UI smoke deferred until local stack is up"})
        n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} SKIP  {n_fail} FAIL\033[0m")
        with open("playwright_smoke_report.json", "w", encoding="utf-8") as f:
            json.dump({"validator": "playwright_smoke", "skipped": "seeder offline"}, f)
        sys.exit(0)

    # L2 + L3: actually run the suite.
    # `started` is taken BEFORE launching and handed to the parser, which refuses any report older than
    # it. Without that, a run killed at its bound silently inherits the verdict of whatever run last
    # wrote the file — which is how this gate once reported nine named failures from a three-hour-old
    # report of a different spec.
    print(f"  Running the Playwright suite via node (bound {RUN_TIMEOUT}s, process tree killed on "
          f"timeout)...")
    started = time.time()
    rc, out, err = _run_playwright()

    report = _parse_report(started_at=started)
    if not report.get("loaded") and report.get("reason"):
        print(f"  \033[93mnote\033[0m  no usable report: {report['reason']}")
    n_tests = 0
    n_failed = 0
    n_skipped = 0
    failed_names: list[str] = []

    if report.get("loaded"):
        suites = report.get("suites", [])
        def walk(s):
            nonlocal n_tests, n_failed, n_skipped
            for spec in s.get("specs", []):
                for t in spec.get("tests", []):
                    n_tests += 1
                    results = t.get("results") or []
                    status = results[0].get("status", "") if results else ""
                    # A test with NO result DID NOT RUN. It used to land in the `else` branch and be
                    # counted — and NAMED — as a failure, which is how this gate announced five specific
                    # test titles as failing when the report said all nine were skipped. "Did not run" and
                    # "ran and failed" are opposite facts about the product, and only one of them is a bug.
                    if not results or status in ("skipped", ""):
                        n_skipped += 1
                    elif status == "passed":
                        pass
                    else:
                        n_failed += 1
                        failed_names.append(f"{spec.get('title')} ({s.get('title')})")
            for sub in s.get("suites", []):
                walk(sub)
        for s in suites:
            walk(s)

    # Detect environment-level errors and SKIP rather than FAIL.
    # The `&` in the project path breaks node module resolution; the
    # MODULE_NOT_FOUND error is environmental, not a test failure.
    env_error_signals = ("MODULE_NOT_FOUND", "Cannot find module", "ENOENT")
    is_env_error = any(sig in (err or "") for sig in env_error_signals)

    if rc == 127:
        issues.append({"check": "suite_ran", "skip": True,
            "reason": "npx not found — install Node.js + Playwright (npm install -D @playwright/test)"})
    elif rc == 124:
        issues.append({"check": "suite_ran", "skip": False,
            "reason": f"Playwright suite exceeded {RUN_TIMEOUT}s timeout"})
    elif is_env_error:
        issues.append({"check": "suite_ran", "skip": True,
            "reason": "Node/npx env error (MODULE_NOT_FOUND). Use `subst Z: <project-path>` then run `cd /z && npx playwright test` manually."})
    elif not report.get("loaded"):
        issues.append({"check": "suite_ran", "skip": False,
            "reason": f"Could not parse {REPORT_FILE}: rc={rc} err_tail={err[-200:] if err else ''}"})

    if n_failed > 0:
        issues.append({"check": "all_passed", "skip": False,
            "reason": f"{n_failed} of {n_tests} tests FAILed. First failures: {failed_names[:5]}"})
    elif n_tests == 0:
        # ZERO TESTS IS NOT A PASS. "All UI smoke tests passed" over an empty denominator is the exact
        # false green this session spent a turn removing from a test bank — a claim that nothing was
        # asserted, printed in the grammar of a claim that everything held.
        issues.append({"check": "all_passed", "skip": False,
            "reason": "0 tests ran, so nothing was asserted — an empty denominator is not a pass"})
    elif n_skipped == n_tests:
        issues.append({"check": "all_passed", "skip": False,
            "reason": f"all {n_tests} tests were SKIPPED — the suite reported no outcome to verify"})

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print(f"\n  Tests: {n_tests} total · {n_tests - n_failed - n_skipped} passed · {n_failed} failed · {n_skipped} skipped")

    with open("playwright_smoke_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "validator":      "playwright_smoke",
            "exit_code":      rc,
            "n_tests":        n_tests,
            "n_failed":       n_failed,
            "n_skipped":      n_skipped,
            "failed":         failed_names,
            "issues":         [i for i in issues if not i.get("skip")],
        }, f, indent=2, default=str)

    if n_fail == 0 and n_warn == 0:
        print(f"\n  \033[92mAll {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\n  \033[91m{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
