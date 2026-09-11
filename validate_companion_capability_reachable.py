#!/usr/bin/env python3
"""
Is the AI companion's certified capability REACHED?  (L0, static, no DB, forward-only ratchet)
=============================================================================================

WHAT THIS COUNTS, AND WHY IT IS NOT THE SAME AS THE TWENTY VALIDATORS IT SITS BESIDE.

`voice-handler.js` is guarded by twenty `validate_ai_companion_*.py` files. Between them they name 283
symbols that the file actually defines, and every one of those checks asks the same question: **is this
name spelled in the source?** A function defined once and called never satisfies all of them.

Measured 2026-09-08:

    283  symbols the companion validators guard and voice-handler defines
    154  never called anywhere inside voice-handler.js
     73  never called ANYWHERE (72 after _logKnowledgeGap was wired the same day) - not in the file, not in a page, not in a test, not in a tool

The 81 in between are exercised by the Playwright sentinel, which reaches into the exports on purpose; the
file says so in its own header, and that is a legitimate caller. The 73 are not called by anything.

WHY THIS IS WORTH A GATE RATHER THAN A NOTE. Four of those 73 were opened up by hand the same day, and all
four were also WRONG in a way that had never surfaced:

  · `_executeErasure`   - the assistant offers to delete a worker's history and, on "yes", nothing happened
  · `_emitAuditEvent`   - "every confirmed write action writes to ai_audit_log"; none did
  · `_enforceRetention` - a 180-day policy that had never aged anything out
  · `_buildAuditCsv`    - a compliance export nobody could produce

and each of them wrote to a column ai_audit_log does not have (`event_type`; the column is `event`). They
were never exercised, so the mistake kept. **Dead code is not merely absent: it is untested, and it rots in
place while a gate certifies it.** That is the whole argument for counting this.

WHAT A FIX LOOKS LIKE. Three honest outcomes, and the count falls for any of them: wire the capability to
the path that should call it; move it to the layer it belongs in and point the validator there (retention
became a pg_cron job); or delete it and drop its check. What is not an outcome is leaving it certified.

RATCHET, NOT A CLIFF. The baseline is today's measured number. It may only fall.

  python validate_companion_capability_reachable.py
  python validate_companion_capability_reachable.py --list
  python validate_companion_capability_reachable.py --selftest
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
SUBJECT = "voice-handler.js"
GUARDS = "validate_ai_companion_*.py"
BASELINE = 59
REPORT = "companion_capability_reachable.json"


def strip_comments(src: str) -> str:
    """A symbol named only in prose is not a call. This file explains its own bugs at length, so a
    reader that counts comments would credit the explanation as the fix."""
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("//", "*", "/*")))


def call_count(text: str, sym: str) -> int:
    return text.count(sym + "(") - text.count("function " + sym + "(")


def guarded_symbols(code: str, pattern: str = GUARDS) -> dict[str, set[str]]:
    """Symbols the companion validators name AND the subject actually defines."""
    out: dict[str, set[str]] = {}
    for f in sorted(glob.glob(pattern)):
        try:
            src = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for s in re.findall(r'["\'](_[A-Za-z][A-Za-z0-9_]{3,})["\']', src):
            if ("function " + s + "(") in code:
                out.setdefault(s, set()).add(os.path.basename(f))
    return out


def callers_text() -> str:
    """Everything that could legitimately call one: pages, shared scripts, the Playwright specs, tools.
    The sentinel reaching into the exports IS a caller - the file's own header says so - so counting it
    as one is not leniency, it is reading the design."""
    out = []
    for pat in ("*.html", "*.js", "tests/*.ts", "tests/*.js", "tools/*.mjs"):
        for f in glob.glob(pat):
            if os.path.basename(f) == SUBJECT:
                continue
            try:
                out.append(open(f, encoding="utf-8", errors="replace").read())
            except OSError:
                pass
    return "\n".join(out)


def unreached(code: str, elsewhere: str, guards: dict[str, set[str]]) -> list[str]:
    dead = []
    for s in guards:
        if call_count(code, s) > 0:
            continue
        if call_count(elsewhere, s) > 0 or ("." + s) in elsewhere:
            continue                      # a test or a page reaches it through the export surface
        dead.append(s)
    return sorted(dead)


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN + 'PASS' + RESET if good else RED + 'FAIL' + RESET}  {label}: got {got}, want {want}")

    code = "function _alpha(){} function _beta(){} _beta(); function _gamma(){}"
    guards = {"_alpha": {"g.py"}, "_beta": {"g.py"}, "_gamma": {"g.py"}}
    chk("a defined-and-called symbol is not counted", unreached(code, "", guards), ["_alpha", "_gamma"])
    chk("a symbol a TEST calls is not counted", unreached(code, "_alpha(1)", guards), ["_gamma"])
    chk("a symbol reached through the export surface is not counted",
        unreached(code, "WHVoice._gamma", {"_gamma": {"g.py"}}), [])
    chk("a comment mentioning the symbol is NOT a call",
        unreached(strip_comments("// calls _alpha() one day\nfunction _alpha(){}"), "", {"_alpha": {"g.py"}}),
        ["_alpha"])
    chk("a symbol the subject does not define is not guarded",
        sorted(guarded_symbols("function _real(){}", "no_such_glob_*.py")), [])
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    print(f"{BOLD}\nIs the AI companion's certified capability REACHED? (static){RESET}")
    print("=" * 62)
    try:
        raw = open(SUBJECT, encoding="utf-8", errors="replace").read()
    except OSError:
        print(f"  {YELLOW}SKIP{RESET}  {SUBJECT} not found - nothing is claimed")
        return 0
    code = strip_comments(raw)
    guards = guarded_symbols(code)
    if not guards:
        print(f"  {YELLOW}SKIP{RESET}  no companion validators found - nothing is claimed")
        return 0
    elsewhere = callers_text()
    dead = unreached(code, elsewhere, guards)
    inside = [s for s in guards if call_count(code, s) <= 0]

    print(f"  validators guarding it:        {len(glob.glob(GUARDS))}")
    print(f"  symbols they guard:            {len(guards)}")
    print(f"  never called inside {SUBJECT}: {len(inside)}")
    print(f"  never called ANYWHERE:         {len(dead)}  (baseline: {BASELINE})")
    if "--list" in sys.argv:
        for s in dead:
            print(f"    {s:34} guarded by {', '.join(sorted(guards[s]))}")
    try:
        with open(REPORT, "w", encoding="utf-8") as fh:
            json.dump({"guarded": len(guards), "uncalled_in_file": len(inside),
                       "uncalled_anywhere": dead}, fh, indent=2)
    except OSError:
        pass
    if len(dead) > BASELINE:
        print(f"\n{RED}FAIL - {len(dead)} > baseline {BASELINE}. A new capability was certified without a "
              f"caller; wire it, move it to the layer it belongs in, or delete it.{RESET}")
        return 1
    if len(dead) < BASELINE:
        print(f"\n{GREEN}PASS - and {BASELINE - len(dead)} fewer than the baseline. Lower BASELINE to "
              f"{len(dead)} to hold the ground.{RESET}")
        return 0
    print(f"\n{GREEN}PASS - held at the baseline. Every one of these is a capability the platform promises "
          f"and nothing performs; see --list.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
