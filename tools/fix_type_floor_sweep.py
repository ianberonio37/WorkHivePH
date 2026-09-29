"""
fix_type_floor_sweep.py — lift every sub-12px functional-text declaration to the platform floor.
=================================================================================================
The platform's own floor is 12px, and the design detector's is 11px. A census of the detector
baseline on 2026-09-16 found `undersized-ui-text` + `tiny-text` to be the largest REAL antipattern
class on the platform once two artefact classes are set aside (logbook's 92 and pm-scheduler's 30
low-contrast findings, both of which are `@media print`'s #111 measured against screen navy and are
pinned as disproven).

The strings involved are not decoration. On index.html, before this tool existed, they included the
signed-in home's four section headings at 9.92px ("Today at a Glance", "Quick Actions", "My Open
Jobs", "All Tools"), the language switch at 10.56px ("EN", "FIL"), and the readiness-ladder markers
at 9px ("Stage 1 complete", "PM compliance >=70% for 30 days"). index.html went 99 findings -> 44.

WHAT IT CHANGES. Three spellings of a font size, wherever the computed value is under 12px:

    font-size: <n>px      ->  font-size: 12px
    font-size: <n>rem     ->  font-size: 0.75rem
    text-[<n>px]          ->  text-xs                (Tailwind arbitrary value)

THE PRINT GUARD, and this is the point of the tool rather than a sed one-liner. A declaration inside
`@media print` is EXEMPT: a printed page is a different medium with a different reader, read at arm's
length on paper rather than at a phone's distance, and the platform deliberately runs denser there.
Lifting a print size to the screen floor would be the mirror image of the defect this bank has already
recorded twice - a static reader applying one medium's rule to another medium's stylesheet. The tool
parses the print blocks by brace-matching and skips anything inside them, and reports the count it
skipped so the exemption is visible rather than silent.

Idempotent: a lifted declaration no longer matches. Re-runnable.

Usage:  python tools/fix_type_floor_sweep.py [--check] [--self-test] [--only <glob>]
  --check      report what WOULD change, write nothing (exit 1 if changes are pending)
  --self-test  prove the patcher and the print guard on fixtures, touching no real file
  --only       restrict to paths matching a glob, e.g. --only "hive.html"
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path
from collections import Counter

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from served_page_set import served_pages as _served_pages   # ONE definition of the page set

# ★11.5 WAS THE DETECTOR'S *FUNCTIONAL-TEXT* BAR, NOT THE PLATFORM'S (2026-09-16). The first run of
# this tool used 11.5 and left 32 `tiny-text` findings standing at 11.52px and 11.84px - sizes that
# clear the detector's 11px functional floor and fail its 12px BODY bar, which is also the platform's
# own floor. 11.95 catches everything under 12px while leaving 0.75rem (exactly 12px) untouched, which
# a bare `< 12` would round into on some values.
FLOOR_PX = 11.95


def print_spans(text: str):
    """Byte ranges of every `@media print { ... }` block, by brace matching."""
    spans = []
    for m in re.finditer(r"@media[^{]*\bprint\b[^{]*\{", text, re.IGNORECASE):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        spans.append((m.start(), i))
    return spans


def patch(text: str):
    """Returns (new_text, lifted Counter, skipped_in_print int)."""
    spans = print_spans(text)
    in_print = lambda pos: any(a <= pos < b for a, b in spans)
    lifted, skipped = Counter(), 0

    def make(pattern, to_px, replacement, label):
        nonlocal text, skipped
        out, last = [], 0
        for m in re.finditer(pattern, text):
            px = to_px(m.group(1))
            if px >= FLOOR_PX:
                continue
            if in_print(m.start()):
                skipped += 1
                continue
            out.append((m.start(), m.end(), replacement))
            lifted["%s %gpx" % (label, round(px, 2))] += 1
        for a, b, rep in reversed(out):
            text = text[:a] + rep + text[b:]

    make(r"font-size:\s*(\d+(?:\.\d+)?)px", float, "font-size: 12px", "px")
    make(r"font-size:\s*(0?\.\d+)rem", lambda v: float(v) * 16, "font-size: 0.75rem", "rem")
    make(r"text-\[(\d+(?:\.\d+)?)px\]", float, "text-xs", "tw")
    return text, lifted, skipped


def targets(only=None):
    # The HUB pages (learn/index.html, tools/index.html) sit directly in their folder, so a
    # `learn/*/index.html` glob walks straight past them - and learn/index.html alone carried 55
    # undersized findings from ONE 0.65rem rule applied to 55 category chips. A glob that describes
    # the common shape is not a glob that covers the set.
    out = _served_pages(ROOT)
    if only:
        out = [p for p in out if p.match(only) or only in p.as_posix()]
    return [p for p in out if p.is_file()]


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    check = "--check" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    files, total, skipped_all = [], Counter(), 0
    for p in targets(only):
        t = p.read_text(encoding="utf-8", errors="replace")
        new, lifted, skipped = patch(t)
        skipped_all += skipped
        if not lifted:
            continue
        files.append((p, sum(lifted.values()), skipped))
        total.update(lifted)
        if not check:
            p.write_text(new, encoding="utf-8")

    verb = "WOULD lift" if check else "lifted"
    print("type floor: %s %d declaration(s) to 12px across %d file(s); %d left alone inside @media print."
          % (verb, sum(total.values()), len(files), skipped_all))
    for p, n, sk in sorted(files, key=lambda x: -x[1])[:12]:
        print("   %-44s %3d%s" % (p.relative_to(ROOT).as_posix(), n, "  (+%d print-exempt)" % sk if sk else ""))
    if len(files) > 12:
        print("   ... and %d more file(s)" % (len(files) - 12))
    if check and files:
        return 1
    return 0


def self_test() -> int:
    ok = True

    got, lifted, skipped = patch("<style>.a { font-size: 9px; } .b { font-size: .62rem; }</style>"
                                 "<p class='text-[10px]'>x</p>")
    if sum(lifted.values()) != 3 or "12px" not in got or "0.75rem" not in got or "text-xs" not in got:
        print("FAIL: the three spellings were not all lifted -> %s" % dict(lifted)); ok = False

    # THE POINT OF THE TOOL: a print declaration is a different medium and must survive untouched
    src = "<style>.a{font-size:9px}@media print{.p{font-size:8px}.q{font-size:.5rem}}</style>"
    got2, lifted2, skipped2 = patch(src)
    if skipped2 != 2:
        print("FAIL: expected 2 print-exempt declarations, got %d" % skipped2); ok = False
    if "font-size:8px" not in got2 or "font-size:.5rem" not in got2:
        print("FAIL: a print declaration was rewritten"); ok = False
    if sum(lifted2.values()) != 1:
        print("FAIL: the screen declaration beside the print block was not lifted"); ok = False

    # a size already at or above the floor is left alone
    _, lifted3, _ = patch(".ok { font-size: 12px; } .fine { font-size: 0.75rem; } .big { font-size: 2rem; }")
    if lifted3:
        print("FAIL: touched a declaration already at the floor -> %s" % dict(lifted3)); ok = False

    # idempotent
    _, lifted4, _ = patch(got)
    if lifted4:
        print("FAIL: not idempotent"); ok = False

    print("self-test: %s" % ("PASS - lifts all three spellings, exempts @media print, respects the floor, idempotent"
                             if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
