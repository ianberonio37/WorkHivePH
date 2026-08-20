#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fn_digest_versions.py — locks the digest contract that kept collapsing the bank.
=====================================================================================
THE DEFECT THIS LOCKS. `fn_digests(version=3)` segments a file's top-level code by counting
brackets per line, and it counted them INSIDE COMMENTS. This repo's house style writes long
prose comments that name calls — "every client routes through getDb(", "118 annotated
catch (_) { ... } blocks". Such a line carries an unbalanced bracket, raising the splitter's
depth so every following line is glued into one giant statement and every statement hash moves.

Measured on utils.js: adding the single comment line

    // every client routes through getDb( and _timeoutFetch

vanished **881 of 881** top-level keys — expiring every banked row anchored to the file. That
is the real root of four bank collapses (752 green -> 34, then 342, ~365, ~320), each read at
the time as "shared-library edits are expensive". They were not expensive because the library
was shared. They were expensive because writing a SENTENCE ABOUT the code counted as changing
the code. 93% of what v3 hashed as utils.js "top-level statements" was prose.

v4 strips comments (string-aware) before both the function-body digest and the top-level split.

THREE PROPERTIES, and the third is the one that makes v4 safe to introduce at all:
  1. a PROSE-only edit must move NOTHING under v4  (it moved 881 keys under v3)
  2. a REAL code edit must still move a key under v4 — or v4 mints false greens, which is
     strictly worse than the over-sensitivity it replaces
  3. v3 recordings must be read by v3 FOREVER. `fn_digests_still_hold` dispatches on the
     version each row recorded, because the last time this measurement changed without
     versioning, recomputing old recordings under the new algorithm expired 661 rows in one
     run and the ratchet correctly refused it.

FILES ARE READ AND WRITTEN AS BYTES. The ad-hoc probe that first found this defect used text
mode with newline="", which silently rewrote utils.js's 4,024 CRLF line endings as LF — a
4KB diff that changed every hash in the file and produced an 18-row "regression" that was
purely my own measurement damaging the artifact. A test that mutates a real source file must
restore it byte-for-byte or it becomes the defect it is hunting.

RUN:  python tools/test_fn_digest_versions.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "utils.js")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _fresh_gate():
    """A new module object each time: fn_digests reads the file at call time, but importing
    fresh keeps any module-level cache from carrying a stale read across a mutation."""
    spec = importlib.util.spec_from_file_location(
        "_vlmb_test_%s" % os.urandom(4).hex(),
        os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def keys(version):
    return dict(_fresh_gate().fn_digests(["utils.js"], version=version))


def run():
    ok = True

    def ck(c, msg):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", msg))

    original = open(TARGET, "rb").read()          # BYTES. see the module docstring.
    base3, base4 = keys(3), keys(4)
    try:
        # ---- 1. prose-only edit -------------------------------------------------------
        prose = b"// every client routes through getDb( and _timeoutFetch\n" + original
        open(TARGET, "wb").write(prose)
        a3, a4 = keys(3), keys(4)
        lost3 = len(set(base3) - set(a3))
        lost4 = len(set(base4) - set(a4))
        ck(lost3 > 100, "v3 shatters on a prose comment (%d keys vanish) - the defect" % lost3)
        ck(lost4 == 0, "v4 survives the same prose comment (%d keys vanish)" % lost4)

        # ---- 2. a real code change must still expire ----------------------------------
        i = original.find(b"function ")
        j = original.find(b"{", i)
        mutated = original[:j + 1] + b" var __probe = 1;" + original[j + 1:]
        open(TARGET, "wb").write(mutated)
        b4 = keys(4)
        moved4 = len(set(base4) - set(b4))
        ck(moved4 > 0, "v4 still expires on a REAL code edit (%d keys move)" % moved4)
    finally:
        open(TARGET, "wb").write(original)        # byte-for-byte, always

    restored = open(TARGET, "rb").read()
    ck(restored == original, "utils.js restored byte-for-byte (%d bytes, %d CRLF)"
       % (len(restored), restored.count(b"\r\n")))

    # ---- 3. version isolation --------------------------------------------------------
    V = _fresh_gate()
    v3_recording = dict(base3)
    v3_recording["::v"] = "3"
    ck(V.fn_digests_still_hold(v3_recording),
       "a v3 recording still holds under v3 (no retroactive reinterpretation)")
    v4_recording = dict(base4)
    v4_recording["::v"] = "4"
    ck(V.fn_digests_still_hold(v4_recording), "a v4 recording holds under v4")
    ck(len([k for k in base4 if "::top:" in k]) < len([k for k in base3 if "::top:" in k]),
       "v4 records fewer top-level keys than v3 (%d vs %d - the difference was prose)"
       % (len([k for k in base4 if "::top:" in k]), len([k for k in base3 if "::top:" in k])))

    print("  %s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
