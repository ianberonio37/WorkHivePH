#!/usr/bin/env python3
"""validate_one_clock_per_string.py — Cluster 1's lock: a rendered timestamp uses ONE clock.

Walked live 2026-09-02 at GMT+12: logbook's card read "Sep 1, 2026 · 12:09 AM" for a save made at
20:09 Manila — the DATE half came from whFmtDate (Asia/Manila-pinned) and the TIME half from
toLocaleTimeString with NO timeZone (the viewer's local clock). Manila's date glued to Auckland's
time is a pair no clock on earth shows; any worker east of UTC logging after local midnight got
yesterday's date on their entry, and the platform's own surfaces answered "what shift is it" three
different ways in one moment (ops-home UTC-hour, shift-brain Manila, the card mixed).

The lock: in every page, a string CONCATENATION that joins a whFmtDate(...) result with a
toLocaleTimeString(...) call must give that time call an explicit timeZone (the un-pinned form
floats with the viewer while the date half stays pinned — the exact defect shape). Static, fast.
Self-test: the pre-fix logbook shape must redden (resurrection).
"""
from __future__ import annotations

import glob
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["one-clock-per-string"]

# whFmtDate(...) ... + ... toLocaleTimeString('en-PH', { ... }) with no timeZone inside the options.
MIXED_RE = re.compile(
    r"whFmtDate\([^)]*\)[^;\n]{0,120}?\+[^;\n]{0,120}?toLocaleTimeString\(\s*'[^']*'\s*,\s*\{(?![^}]*timeZone)[^}]*\}",
    re.S)


def offenders() -> list[str]:
    out = []
    for f in glob.glob(str(ROOT / "*.html")):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        for m in MIXED_RE.finditer(src):
            line = src.count("\n", 0, m.start()) + 1
            out.append(f"{Path(f).name}:{line}")
    return out


def _shift_line_anchored() -> str | None:
    """index.html's date+shift line must derive from Asia/Manila AND carry the (PHT) label —
    a shift belongs to the plant's clock (walked 2026-09-02: viewer-local said Morning at the
    viewer's midnight while shift-brain said Afternoon on the plant clock)."""
    src = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()
    m = re.search(r"function _dateStr\(\)\s*\{[\s\S]{0,2600}?return[\s\S]{0,300}?\n\s*\}", src)
    if not m:
        return "index.html _dateStr() not found - the shift-line anchor moved; re-point this check"
    body = m.group(0)
    if "Asia/Manila" not in body:
        return "index.html _dateStr() no longer derives from Asia/Manila - the shift label floats with the viewer again"
    if "(PHT)" not in body:
        return "index.html _dateStr() dropped the (PHT) label - a plant-clock figure must say so (qualifier-beside-figure)"
    # T46 walk (2026-09-02): the GREETING must ride the same plant clock — "Magandang hapon ...
    # Umaga Shift" rendered on one line at 09:53 Manila because _greeting still used viewer-local
    # hours. The platform speaks plant time everywhere, greeting included.
    g = re.search(r"function _greeting\([\s\S]{0,900}?\n  \}", src)
    if not g:
        return "index.html _greeting() not found - the greeting anchor moved; re-point this check"
    if "Asia/Manila" not in g.group(0):
        return "index.html _greeting() no longer derives from Asia/Manila - the greeting contradicts the shift line for any viewer off the plant clock"
    return None


def main() -> int:
    bad = offenders()
    anchor = _shift_line_anchored()
    if bad or anchor:
        print("FAIL one-clock-per-string:")
        if bad:
            print("    pinned DATE glued to floating viewer-local TIME (two-clocks render): " + ", ".join(bad[:8]))
        if anchor:
            print("    " + anchor)
        return 1
    print("PASS one-clock-per-string - no page concatenates a Manila-pinned date with an "
          "un-pinned toLocaleTimeString, and index's shift line is plant-anchored + labeled (PHT).")
    return 0


def self_test() -> int:
    fails = []
    if offenders() or _shift_line_anchored():
        fails.append("HEAD should PASS")
    # anchor teeth: a _dateStr body without Asia/Manila or without (PHT) must redden
    real = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()
    import unittest.mock as _m
    stripped = real.replace("Asia/Manila", "Local/Zone")
    with _m.patch("io.open", side_effect=lambda p, *a, **k: io.StringIO(stripped) if str(p).endswith("index.html") else open(p, *a, **k)):
        if _shift_line_anchored() is None:
            fails.append("an un-anchored shift line must redden")
    pre_fix = "const s = whFmtDate(iso) + ' · ' + d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' });"
    if not MIXED_RE.search(pre_fix):
        fails.append("the pre-fix logbook shape must match (resurrection)")
    fixed = "const s = whFmtDate(iso) + ' · ' + d.toLocaleTimeString('en-PH', { hour: '2-digit', timeZone: 'Asia/Manila' });"
    if MIXED_RE.search(fixed):
        fails.append("a pinned time half must NOT match")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_one_clock_per_string self-test (pre-fix shape reddens; pinned shape passes)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
