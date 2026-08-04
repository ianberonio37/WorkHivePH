#!/usr/bin/env python3
"""stamp_fn_digests.py — record WHICH FUNCTIONS a fresh claim rests on, so a shared library can grow.

WHY THIS EXISTS. The bank expires a green row when a file it depends on changes (validate_live_mcp_bank
R4). That is right for a page: edit marketplace.html and every claim about marketplace.html deserves a
re-walk. It is wrong for utils.js, which nearly every row names. On 2026-08-04, appending ONE new helper
to utils.js -- touching no existing line -- expired 402 of 435 green rows in a single commit. Not one of
those claims could have been affected: "the seller edit form refuses a blank title" does not become
doubtful because a function it never calls now exists.

An instrument that cannot tell "the code this claim rests on changed" from "unrelated code was added
beside it" is measuring file mtime with extra steps, and it is paid for in re-walks that re-confirm what
nobody doubted -- which is how a discipline stops being followed.

WHAT IT DOES. For every row whose file-level sha is CURRENTLY FRESH -- i.e. whose evidence is valid at
this moment -- it records `fn_digests`: a digest per top-level function in each .js dependency, plus one
for the file's top-level code. R4b then keeps that row green through a later change as long as every
function it recorded is still byte-identical. A NEW function is absent from the map and so expires
nothing; a CHANGED or DELETED one still expires the row.

WHY IT ONLY EVER TOUCHES FRESH ROWS. Recording digests for a STALE row would launder the very change
that expired it -- the row would come back green on the strength of code it was never walked against.
So a stale row is skipped and stays owed, which is the whole point.

Run it after a banking session. Idempotent.

Usage:  python tools/stamp_fn_digests.py [--dry-run]
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_live_mcp_bank import REGISTRY, sha_of, fn_digests  # noqa: E402


def main(argv):
    dry = "--dry-run" in argv
    reg = json.load(io.open(REGISTRY, encoding="utf-8"))
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg

    cache = {}
    stamped = skipped_stale = already = no_js = 0
    for s in rows:
        ev = s.get("evidence")
        if s.get("status") != "green" or not ev:
            continue
        dep = ev.get("depends_on") or []
        if not dep:
            continue
        if sha_of(dep) != ev.get("sha"):
            skipped_stale += 1          # deliberately: see the module docstring
            continue
        if ev.get("fn_digests"):
            already += 1
            continue
        key = tuple(dep)
        if key not in cache:
            cache[key] = fn_digests(list(key))
        if not cache[key]:
            no_js += 1                  # nothing but .html/.css to scope; the file hash stays its guard
            continue
        if not dry:
            ev["fn_digests"] = cache[key]
        stamped += 1

    if not dry:
        with io.open(REGISTRY, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, ensure_ascii=False)

    print(f"  stamped {stamped} fresh row(s) with function-scoped digests")
    print(f"  already scoped: {already}   no .js dependency: {no_js}")
    print(f"  left alone because STALE (re-walk them, do not stamp them): {skipped_stale}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
