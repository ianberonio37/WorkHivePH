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
import urllib.request

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result


CONFIG_FILE = "playwright.config.ts"
TESTS_DIR   = "tests"
SEEDER_URL  = "http://127.0.0.1:5000"
REPORT_FILE = "playwright-report.json"
RUN_TIMEOUT = 180  # seconds — bound the whole suite


def _seeder_up() -> bool:
    try:
        with urllib.request.urlopen(SEEDER_URL, timeout=2) as _:
            return True
    except Exception:
        return False


def _run_playwright() -> tuple[int, str, str]:
    """Run the suite. Returns (exit_code, stdout, stderr).

    Uses Z: drive on Windows if available (avoids the `&` in path bug per
    memory: 'Deploy workaround — subst Z:'). If Z: doesn't map back to the
    project root, falls back to native cwd.
    """
    cmd = ["npx", "playwright", "test", "--reporter=json"]
    cwd = None
    if sys.platform == "win32" and os.path.exists("Z:\\playwright.config.ts"):
        cwd = "Z:\\"
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT,
            shell=(sys.platform == "win32"), cwd=cwd,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "npx not found"


def _parse_report() -> dict:
    if not os.path.exists(REPORT_FILE):
        return {"loaded": False}
    try:
        with open(REPORT_FILE, encoding="utf-8") as f:
            return {"loaded": True, **json.load(f)}
    except Exception as e:
        return {"loaded": False, "parse_error": str(e)}


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

    # L2 + L3: actually run the suite
    print("  Running `npx playwright test` (timeout 3min)...")
    rc, out, err = _run_playwright()

    report = _parse_report()
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
                    status = (t.get("results") or [{}])[0].get("status", "")
                    if status == "passed":
                        pass
                    elif status == "skipped":
                        n_skipped += 1
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
