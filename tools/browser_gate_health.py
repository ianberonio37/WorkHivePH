#!/usr/bin/env python3
"""browser_gate_health.py — tell a BROKEN MACHINE apart from a broken product.

Found 2026-07-31 while running the full suite. Three live-browser gates went RED — the marketplace state
inducers, the journey lane, and the P3 CRUD gate — and every one of them PASSED when run on its own
moments later. The cause was not any of them: 32 ORPHANED chrome/node processes, left behind by earlier
Playwright runs in the same session, had starved the worker pool. The three errors it produced were all
different ("Failed to fetch", a `waitForFunction` timeout, and "Worker failed to respond due to a resource
limit"), which is exactly why it read as three separate product bugs instead of one exhausted machine.

WHY THIS MATTERS MORE THAN IT SOUNDS. A false RED is worse than a SKIP. A skip says "I did not measure
this"; a red says "your product is broken" and sends someone to read page code that was never wrong — the
same waste `feedback_a_dead_fixture_invents_page_defects` cost an afternoon to learn. Worse, gates that cry
wolf get excluded, and an excluded gate is how nine cron jobs stayed dead for weeks on this platform.

WHAT THIS IS NOT. It is NOT a way to make failures go away. The signatures below are narrow and specific to
process/worker exhaustion; an assertion failure, a 5xx, a missing element or a real timeout inside a healthy
run all still FAIL. And a skip here is LOUD: it prints the live process count and the signature that matched,
so "the machine was overloaded" is a claim with evidence attached rather than a shrug.

Usage (from a gate):
    from browser_gate_health import infra_exhausted, reap_orphans, browser_proc_count
    verdict = infra_exhausted(combined_stdout_stderr)
    if verdict:
        print(f"  SKIP (infrastructure): {verdict}")
        return 0
"""
import re
import subprocess
import sys

# Narrow ON PURPOSE. Each of these is a statement about the RUNNER, not about the page under test.
EXHAUSTION_SIGNATURES = [
    (r"Worker failed to respond due to a resource limit",
     "Playwright could not start a worker — the machine is out of capacity, not the page"),
    (r"browserType\.launch.*(ENOMEM|Out of memory|spawn ENOENT)",
     "the browser could not be launched at all"),
    (r"Target (page|browser) (has been )?closed.*before any assertion",
     "the browser died before a single assertion ran"),
    (r"net::ERR_INSUFFICIENT_RESOURCES",
     "Chromium refused further requests for want of resources"),
]

# Above this many live chrome/node processes, a browser gate is competing with leftovers rather than
# measuring the product. Chosen from the observed failure: 32 alive, three gates red, all three green at 19.
ORPHAN_ALARM = 28


def browser_proc_count():
    """-> int. Best-effort; a platform where this cannot be counted returns 0 and simply never alarms."""
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30).stdout or ""
    except Exception:
        try:
            out = subprocess.run(["ps", "-e"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=30).stdout or ""
        except Exception:
            return 0
    return len(re.findall(r"\b(chrome|headless_shell|node)\b", out, re.I))


def infra_exhausted(output: str):
    """-> a human explanation if the RUNNER failed, else None.

    Returns a string rather than a bool so the caller can print WHY it skipped. A skip with no reason is
    the silent-skip this platform has banned everywhere else.
    """
    for pattern, why in EXHAUSTION_SIGNATURES:
        if re.search(pattern, output or "", re.I):
            n = browser_proc_count()
            return (f"{why} (matched: {pattern[:48]}...); {n} chrome/node processes alive"
                    + (f" — over the {ORPHAN_ALARM} alarm, so earlier runs did not clean up"
                       if n >= ORPHAN_ALARM else ""))
    return None


def reap_orphans(dry_run: bool = False):
    """Kill leftover headless browsers. Returns (before, after).

    Deliberately NOT called automatically by a gate: a gate that kills processes as a side effect of
    measuring is a surprise, and it could kill a browser someone is deliberately driving. This is for a
    runner or a human who has decided to clean up.
    """
    before = browser_proc_count()
    if dry_run:
        return before, before
    for image in ("chrome.exe", "headless_shell.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", image, "/T"],
                           capture_output=True, text=True, timeout=60)
        except Exception:
            pass
    return before, browser_proc_count()


def selftest():
    print("  selftest: a runner failure must be recognised, and a PRODUCT failure must NOT be")
    ok = True
    if not infra_exhausted("Error: Worker failed to respond due to a resource limit (please check logs)"):
        print("  FAIL — the observed exhaustion signature was not recognised"); ok = False
    # The three shapes that MUST still fail: an assertion, a real timeout inside a healthy run, a 5xx.
    for benign in ["expect(received).toBe(expected)  // assertion failed",
                   "TimeoutError: page.waitForFunction: Timeout 8000ms exceeded.",
                   "Failed to load resource: the server responded with a status of 500"]:
        if infra_exhausted(benign):
            print(f"  FAIL — a PRODUCT failure was misread as infrastructure: {benign[:44]}"); ok = False
    if browser_proc_count() < 0:
        print("  FAIL — process count is nonsensical"); ok = False
    print("  PASS — recognises runner exhaustion, and leaves real failures alone" if ok else "")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--reap" in sys.argv:
        b, a = reap_orphans()
        print(f"reaped browser processes: {b} -> {a}")
        sys.exit(0)
    if "--count" in sys.argv:
        print(browser_proc_count())
        sys.exit(0)
    sys.exit(selftest())
