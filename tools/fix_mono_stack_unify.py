"""
fix_mono_stack_unify.py — one monospace answer, recorded in DESIGN.md and shipped on every page.
=================================================================================================
MEASURED 2026-09-16. `design-system-font` was the largest UNPINNED antipattern class left on the
platform (93 of 334), and every finding says the same thing: a `<pre>` or code chip "uses consolas;
not declared in DESIGN.md typography".

The platform had THREE answers to "what is our monospace font", and DESIGN.md recorded none of them
correctly:

  1. `'Consolas','Courier New',monospace`  - 99 declarations across 85 calculator and learn pages,
     BYTE-IDENTICAL, the formula and code blocks on the public funnel
  2. `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New",
     monospace` - Tailwind's `.font-mono` in wh-tw.css, what the app pages get
  3. DESIGN.md's `mono` role: `ui-monospace, SFMono-Regular, monospace` - a truncation of neither

THE DESIGN PROBLEM, not just the detector's. Stack 1 is Windows-first: it names Consolas and then
falls straight to Courier New. A reader on macOS gets Courier New for every engineering formula on
the public calculators, and so does a reader on Linux - Courier New is a 1955 typewriter face with a
thin stroke and tiny x-height, which is a poor way to render `MTBF = Total Operating Time / Number of
Failures` to someone deciding whether to trust the tool.

Stack 2 degrades properly on every OS AND still names Consolas, so Windows - the platform's primary
reader - renders exactly as it does today. Unifying on it is a strict improvement with no regression
where most of the audience is, which is why it is the one recorded in DESIGN.md rather than a fourth
invention.

Quoting: every one of the 99 declarations sits inside a `<style>` block (checked), but the
replacement uses SINGLE quotes for the two multi-word families anyway, so it stays safe if one is
ever moved into a double-quoted `style="..."` attribute.

Usage:  python tools/fix_mono_stack_unify.py [--check] [--self-test]
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

OLD = "'Consolas','Courier New',monospace"
NEW = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"

# what DESIGN.md should say, so the record matches what ships
DESIGN_OLD = '    fontFamily: "ui-monospace, SFMono-Regular, monospace"'
DESIGN_NEW = ('    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, '
              "'Liberation Mono', 'Courier New', monospace\"")


def targets():
    seen, out = set(), []
    for pat in ("*.html", "learn/*.html", "tools/*.html", "learn/*/index.html", "tools/*/index.html"):
        for p in ROOT.glob(pat):
            if p.as_posix() in seen or not p.is_file():
                continue
            seen.add(p.as_posix())
            out.append(p)
    return sorted(out)


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    check = "--check" in sys.argv

    files, total = [], 0
    for p in targets():
        t = p.read_text(encoding="utf-8", errors="replace")
        n = t.count(OLD)
        if not n:
            continue
        files.append((p, n))
        total += n
        if not check:
            p.write_text(t.replace(OLD, NEW), encoding="utf-8")

    design = ROOT / "DESIGN.md"
    design_pending = False
    if design.exists():
        dt = design.read_text(encoding="utf-8")
        if DESIGN_OLD in dt:
            design_pending = True
            if not check:
                design.write_text(dt.replace(DESIGN_OLD, DESIGN_NEW), encoding="utf-8")

    verb = "WOULD unify" if check else "unified"
    print("mono stack: %s %d declaration(s) across %d file(s)%s."
          % (verb, total, len(files),
             "; DESIGN.md's mono role %s" % ("WOULD be corrected" if check else "corrected")
             if design_pending else "; DESIGN.md already records the shipped stack"))
    for p, n in files[:6]:
        print("   %-46s %d" % (p.relative_to(ROOT).as_posix(), n))
    if len(files) > 6:
        print("   ... and %d more file(s)" % (len(files) - 6))
    if check and (files or design_pending):
        return 1
    return 0


def self_test() -> int:
    ok = True
    src = "<style>pre { font-family: %s; font-size: 0.8rem; }</style>" % OLD
    got = src.replace(OLD, NEW)
    if "SFMono-Regular" not in got or "Menlo" not in got:
        print("FAIL: the replacement did not carry the cross-platform families"); ok = False
    if "Consolas" not in got:
        print("FAIL: Windows lost Consolas - the replacement must not regress the primary reader"); ok = False
    if '"' in NEW:
        print("FAIL: the replacement contains a double quote and could break a style attribute"); ok = False
    if OLD in got:
        print("FAIL: the old stack survived"); ok = False
    if got.replace(NEW, OLD) != src:
        print("FAIL: the replacement changed something other than the font stack"); ok = False
    print("self-test: %s" % ("PASS - cross-platform families added, Consolas kept, attribute-safe quoting"
                             if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
