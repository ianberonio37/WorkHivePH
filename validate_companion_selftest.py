#!/usr/bin/env python3
"""Run the AI companion's OWN self-test suite as a gate.

voice-handler.js ships `_runSelfTest()` - two dozen assertions written alongside the features they cover,
exported on the module surface, and invoked by nothing but a badge a person has to open in a browser.
That is a lock nothing turns: the cases could rot for months and every suite run would stay green.

This gate turns it. `tools/companion_selftest_harness.cjs` stubs the handful of page globals the file
touches while loading, calls the module's own `_runSelfTest()`, and reports what it says. No assertion
here duplicates one there - the point is to RUN the ones that already exist, so that a change breaking
the affirmation regex, the PII scrub, the symptom normaliser or the six input-normalisation
capabilities fails the suite instead of a badge nobody opens.

    python validate_companion_selftest.py
    python validate_companion_selftest.py --selftest   # does this gate have teeth?
"""
import json
import os
import subprocess
import sys

# every validator here carries this: a Windows console defaults to cp1252 and a single non-Latin-1
# character in a failure message kills the process with a UnicodeEncodeError, so the gate dies at the
# exact moment it has something to say
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

G, R, Y, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "tools", "companion_selftest_harness.cjs")
SUBJECT = os.path.join(HERE, "voice-handler.js")
REPORT = os.path.join(HERE, "companion_selftest.json")

# the suite is a ratchet: cases may be added, never quietly dropped
MIN_CASES = 27


def run_harness(subject_override=None):
    """Return (passed, total, failures, err). err is a string when the harness could not speak."""
    env = dict(os.environ)
    if subject_override:
        env["WH_SELFTEST_SUBJECT"] = subject_override
    try:
        p = subprocess.run(["node", HARNESS], capture_output=True, text=True, timeout=180, env=env, cwd=HERE)
    except FileNotFoundError:
        return None, None, None, "node is not on PATH, so the companion's self-test could not be run"
    except subprocess.TimeoutExpired:
        return None, None, None, "the harness did not finish within 180s"
    out = (p.stdout or "") + (p.stderr or "")
    # the harness prints the module's own object; read the numbers off the line it writes for us
    passed = total = None
    failures = []
    for line in out.splitlines():
        s = line.strip()
        if "self-test checks pass" in s:
            head = s.split()[0]
            if "/" in head:
                a, b = head.split("/", 1)
                if a.isdigit() and b.isdigit():
                    passed, total = int(a), int(b)
        elif s.startswith("- "):
            failures.append(s[2:].strip())
    if passed is None:
        return None, None, None, "the harness produced no verdict: " + out.strip()[:400]
    return passed, total, failures, None


def selftest():
    """A gate with teeth fails when the thing it guards breaks. Prove it on a copy, never the real file."""
    import shutil
    import tempfile

    cases = []
    tmp = tempfile.mkdtemp(prefix="wh_selftest_")
    broken = os.path.join(tmp, "voice-handler.js")
    try:
        src = open(SUBJECT, encoding="utf-8").read()
        # break ONE assertion's subject and require the gate to notice
        hurt = src.replace("function _stripFillers(text) {", "function _stripFillers(text) { return String(text || '');", 1)
        cases.append(("the break is real (the source actually changed)", hurt != src))
        with open(broken, "w", encoding="utf-8") as f:
            f.write(hurt)
        passed, total, failures, err = run_harness(subject_override=broken)
        cases.append(("a broken normaliser fails the suite", err is None and bool(failures)))
        cases.append(("and it names which case fell", err is None and any("filler" in f.lower() for f in (failures or []))))
        # the healthy file passes
        passed, total, failures, err = run_harness()
        cases.append(("the real file passes", err is None and not failures))
        cases.append(("and the case count has not shrunk", err is None and (total or 0) >= MIN_CASES))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = 0
    for name, good in cases:
        print(f"  {G}PASS{X}" if good else f"  {R}FAIL{X}", name)
        ok += 1 if good else 0
    print()
    if ok == len(cases):
        print(f"{G}All {ok} teeth cases passed.{X}")
        return 0
    print(f"{R}{len(cases) - ok} of {len(cases)} teeth cases failed.{X}")
    return 1


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print(f"{B}\nDoes the AI companion's OWN self-test suite actually run?{X}")
    print("=" * 62)
    passed, total, failures, err = run_harness()
    if err:
        print(f"  {R}FAIL{X} {err}")
        return 1

    print(f"  cases the module defines:     {total}")
    print(f"  cases that pass:              {passed}")
    print(f"  ratchet floor:                {MIN_CASES}")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "total": total, "failures": failures, "floor": MIN_CASES}, f, indent=2)

    if failures:
        print(f"\n  {R}failing:{X}")
        for name in failures:
            print(f"    - {name}")
        print(f"\n{R}FAIL - the companion's own assertions do not hold.{X}")
        return 1
    if total < MIN_CASES:
        print(f"\n{R}FAIL - the suite has SHRUNK ({total} < {MIN_CASES}). Cases may be added, not quietly dropped.{X}")
        return 1
    print(f"\n{G}PASS - all {passed} of the companion's own assertions hold, run outside a browser.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
