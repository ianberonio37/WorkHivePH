#!/usr/bin/env python3
"""validate_nav_roles_are_modes.py — every nav-hub `roles:` value must be a declared display MODE.

WHY THIS EXISTS (W3-JN J17, 2026-09-09). `nav-hub.js` entries carry `roles: [...]`, and the word is a
trap: it is matched in `isVisibleInMode(tool, mode)` against a DISPLAY MODE from
`MODES = [all, field, supervisor, engineer]`, not against an auth role. A worker's mode is **'field'**.

Walking J17 (sensor -> anomaly -> alert -> asset -> work) as the worker that archetype casts, all five
rows failed on "1 hop has no way onward at all": Asset Hub was reachable by NOBODY on a worker's
account, because its entry read `roles: ['supervisor','engineer']`. The page had always permitted
workers - asset-hub.html:1231 says "the query below scopes what each role sees; the reviewer BUTTONS
stay supervisor-only" - so it was a wayfinding gap, not a permission one.

The fix was one word, and THE FIRST ATTEMPT AT IT WAS A SILENT NO-OP: I added the literal string
'worker', which is not a mode, so nothing changed and the walk failed again identically. A no-op and a
working fix look the same in a diff; only the re-walk told them apart. This gate makes the difference
visible without a browser: an unknown value in a `roles:` list is a typo that disables an entry for
everyone it was meant to include, and it fails silently for ever otherwise.

    python tools/validate_nav_roles_are_modes.py
    python tools/validate_nav_roles_are_modes.py --selftest
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "nav-hub.js"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^\s*//.*$", re.M)
MODES_RE = re.compile(r"var\s+MODES\s*=\s*\[(.*?)\]\s*;", re.S)
MODE_ID_RE = re.compile(r"id:\s*'([a-z]+)'")
# roles: ['a','b'] — captured with its label so a failure can name the entry a human recognises
ENTRY_RE = re.compile(r"label:\s*'([^']+)'[^}]{0,400}?roles:\s*\[([^\]]*)\]", re.S)
VALUE_RE = re.compile(r"'([^']+)'")


def strip(src: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", src))


def declared_modes(src: str) -> set[str]:
    m = MODES_RE.search(src)
    return set(MODE_ID_RE.findall(m.group(1))) if m else set()


def offenders(src: str) -> list[tuple[str, str]]:
    """(label, bad_value) for every roles entry naming something that is not a MODE."""
    body = strip(src)
    modes = declared_modes(body)
    if not modes:
        return [("<MODES>", "could not read the MODES list - refusing to judge")]
    out = []
    for label, roles in ENTRY_RE.findall(body):
        for v in VALUE_RE.findall(roles):
            if v not in modes:
                out.append((label, v))
    return out


def run() -> int:
    try:
        src = NAV.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"FAIL nav-roles-are-modes: cannot read nav-hub.js ({e})")
        return 1
    modes = declared_modes(strip(src))
    bad = offenders(src)
    print(f"nav-roles-are-modes: modes declared = {sorted(modes)}")
    if not bad:
        print("  every roles: value names a real display mode")
        return 0
    print(f"FAIL nav-roles-are-modes: {len(bad)} entry value(s) name something that is not a mode:")
    for label, v in bad:
        print(f"  {label}: roles contains '{v}'")
    print("  `roles:` is matched against a display MODE, not an auth role - see MODES / isVisibleInMode.\n"
          "  A worker's mode is 'field'. An unknown value silently hides the entry from everyone it was\n"
          "  meant to include, and reads as a working fix in the diff.")
    return 1


def selftest() -> int:
    good = ("var MODES = [ { id: 'all' }, { id: 'field' }, { id: 'supervisor' }, { id: 'engineer' } ];"
            "{ label: 'Asset Hub', href: 'a.html', roles: ['supervisor','engineer','field'] }")
    bad = ("var MODES = [ { id: 'all' }, { id: 'field' }, { id: 'supervisor' }, { id: 'engineer' } ];"
           "{ label: 'Asset Hub', href: 'a.html', roles: ['supervisor','engineer','worker'] }")
    commented = ("var MODES = [ { id: 'all' }, { id: 'field' } ];"
                 "/* label: 'Ghost', roles: ['worker'] */ { label: 'Real', roles: ['field'] }")
    fails = 0
    for name, src, want in [("a real mode passes", good, 0),
                            ("the 'worker' no-op is caught", bad, 1),
                            ("a commented-out entry is not judged", commented, 0)]:
        got = len(offenders(src))
        if got != want:
            print(f"  FAIL {name}: {got} offender(s), want {want}")
            fails += 1
        else:
            print(f"  ok   {name}")
    if not declared_modes("no modes here"):
        print("  ok   an unreadable MODES list yields no modes (run() then refuses to judge)")
    else:
        print("  FAIL modes invented from a file with none")
        fails += 1
    print("selftest:", "PASS" if not fails else f"{fails} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
