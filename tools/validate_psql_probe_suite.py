#!/usr/bin/env python3
"""validate_psql_probe_suite.py -- re-execute EVERY psql recipe in tools/psql_probes/ and fail if one
of them stops being true.

WHY THIS EXISTS (2026-08-31). The bank holds 96 rows whose evidence kind is `psql`: an invariant proven
by a recipe file rather than by a walk. Each of those rows carries a `replay` line naming its recipe -
and until now NOTHING RAN THEM. They were proven once, at bank time, and then never again. The bank's
freshness machinery expires such a row when its declared deps change, which is the right behaviour for
a CLAIM about a file; it says nothing about an invariant that lives in the DATABASE, where a migration,
a policy edit or a dropped grant can falsify a recipe while every file it depends on sits untouched.

The gap became concrete the same day it was found. `public-feed__public_identity_only.sql` is a
REGRESSION LOCK: it exists because an anonymous visitor could read every public post author's internal
auth_uid, and it asserts that the table-wide grant is gone and the column has left the truth view. A
lock nothing executes locks nothing. This gate is what makes that recipe - and the other 95 - bite.

WHAT IT ASSERTS: every recipe still passes its own declared expectations. The recipes carry the real
assertions; this file's whole job is to run all of them and refuse to be green while any one is red.

RESIDUE: none by construction. Every mutating recipe wraps its teeth in BEGIN/ROLLBACK and most assert
their own restoration afterwards, so the suite is safe to run against a live local stack.

Sequential on purpose: these recipes take row locks and several assume a role, and running them
concurrently would trade a real signal for flake under load - the failure mode this repo has already
paid for once in its full-suite live gates.
"""
import argparse
import glob
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, "tools", "psql_probes")
RUNNER = os.path.join(ROOT, "tools", "psql_probe_runner.py")

GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run just the recipes whose filename contains this substring")
    ap.add_argument("--fast", action="store_true",
                    help="sample one recipe per page rather than the whole suite")
    a = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(PROBES, "*.sql")))
    if a.only:
        files = [f for f in files if a.only in os.path.basename(f)]
    if a.fast:
        # one per page prefix: enough to catch a stack-wide breakage without paying for the suite
        seen, sampled = set(), []
        for f in files:
            page = os.path.basename(f).split("__")[0]
            if page not in seen:
                seen.add(page)
                sampled.append(f)
        files = sampled

    if not files:
        print(f"{RED}FAIL{RST} psql-probe-suite: no recipes found under tools/psql_probes/")
        return 1

    print(f"  psql recipe suite - {len(files)} recipe(s)"
          + (f" {DIM}(--fast: one per page){RST}" if a.fast else ""))

    def run_one(path):
        try:
            r = subprocess.run([sys.executable, RUNNER, path], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=300)
            return r.returncode == 0, r
        except subprocess.TimeoutExpired:
            return False, None

    failed, flaked, t0 = [], [], time.time()
    for f in files:
        name = os.path.basename(f)[:-4]
        ok, p = run_one(f)
        if not ok:
            # ★RETRY ONCE, AND SAY SO. These recipes take row locks and several SET ROLE; running 99 of
            # them back to back reproduces this repo's known flake-under-load class - measured here, on
            # the suite's first full run, assistant__citations_resolve_lawfully failed inside the suite
            # and then passed three times standalone and every full run since. A false RED is worse than
            # a slow gate: it sends someone hunting a defect that is not there, and it teaches the team
            # to re-run a red gate until it turns green, which is how a real failure gets waved through.
            # So the retry is neither silent nor unlimited - one retry, and a flake is REPORTED as a
            # flake rather than folded into the pass.
            ok, p = run_one(f)
            if ok:
                flaked.append(name)
                print(f"    {YEL}flaked{RST} {name} {DIM}(failed once, passed on retry){RST}")
        if not ok:
            # the recipe's own output names WHICH expectation went missing - keep it, that is the
            # whole diagnosis and re-deriving it by hand is the expensive part.
            detail = ""
            if p is not None:
                detail = "\n".join(l for l in (p.stdout or "").splitlines()
                                   if "MISSING" in l or "FORBIDDEN" in l or "FAIL" in l)
            failed.append((name, detail or "timed out after 300s"))
            print(f"    {RED}FAIL{RST} {name}")
        else:
            print(f"    {GREEN}ok{RST}   {DIM}{name}{RST}")

    dt = time.time() - t0
    print(f"\n  {len(files) - len(failed)}/{len(files)} recipes hold  {DIM}({dt:.0f}s){RST}")
    if failed:
        print(f"\n{RED}FAIL{RST} psql-probe-suite: {len(failed)} recipe(s) no longer hold. Each one is a"
              f" banked invariant that has stopped being true - the bank still says green.")
        for name, detail in failed:
            print(f"\n  {YEL}{name}{RST}")
            for line in (detail or "").splitlines():
                print(f"    {line}")
        return 1
    print(f"{GREEN}PASS{RST} psql-probe-suite: every banked psql invariant still holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
