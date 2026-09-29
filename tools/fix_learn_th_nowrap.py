"""
fix_learn_th_nowrap.py — a scroll wrapper that cannot scroll is a crushed header.
=================================================================================
W46083 found and fixed this on the public pillar template: `[data-table-scroll]` announces a
horizontally scrollable region, but the table inside is pinned to `width:100%`, so it can never
overflow and therefore never scrolls. Instead it CRUSHES the columns, and the first thing to
give is the header cell - at 390px the headers "Product" and "Paid entry" wrapped to THREE
lines in 66px. `white-space: nowrap` on `th` is what makes the wrapper real: the header keeps
one line, the table finally exceeds its container, and the region the markup promised actually
scrolls.

The pillar template carries that fix. The NINETEEN off-template learn articles do not, and the
defect surfaced again on a routine audit walk: W46205 (psme-iiee-piche-which-association-to-join)
reported the ONLY non-zero fit finding in a run of nine clean pages -
`th 3 lines @124px "Annual membership"`.

MEASURED 2026-09-21 across all 54 learn articles: 38 have tables, every one of them has the
`[data-table-scroll]` wrapper, and NINE lack the nowrap rule. All nine are off-template. Their
`.prose-wh th` rule is otherwise byte-identical to the canonical one - same background, weight,
colour, size, transform and letter-spacing - so this appends the single declaration that is
missing rather than rewriting the rule.

Pairs the other post-build sweeps in tools/build_pillar_pages.py.

RUN:  python tools/fix_learn_th_nowrap.py --check    # exit 1 if any page still crushes
      python tools/fix_learn_th_nowrap.py --apply
      python tools/fix_learn_th_nowrap.py --self-test
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# The th rule that styles the header cell. Matched non-greedily to its own closing brace so a
# later rule cannot be swallowed.
TH_RULE = re.compile(r"(\.prose-wh th\s*\{)([^}]*?)(\})", re.S)

NOTE = ("\n      /* [data-table-scroll] promises a scrollable region, and a table pinned to width:100%%\n"
        "         can never overflow - so it crushed the header instead. Measured: 3 lines @124px for\n"
        '         "Annual membership" at 390 (W46205, 2026-09-21). One line here is what makes the\n'
        "         wrapper real. Ported from the pillar template's W46083 fix. */\n"
        "      white-space: nowrap; ")


def needs_fix(html: str) -> bool:
    """True when the page has a table and a .prose-wh th rule that lacks nowrap."""
    if "<table" not in html:
        return False
    for m in TH_RULE.finditer(html):
        if "white-space" not in m.group(2):
            return True
    return False


def apply_to(html: str) -> tuple[str, int]:
    n = 0

    def rep(m):
        nonlocal n
        body = m.group(2)
        if "white-space" in body:
            return m.group(0)
        n += 1
        return m.group(1) + body.rstrip().rstrip(";") + ";" + NOTE + m.group(3)

    return TH_RULE.sub(rep, html), n


def run(mode: str) -> int:
    pages = sorted(glob.glob(str(ROOT / "learn/*/index.html")))
    touched, fixed = [], 0
    for f in pages:
        p = Path(f)
        html = p.read_text(encoding="utf-8", errors="replace")
        if not needs_fix(html):
            continue
        rel = p.relative_to(ROOT).as_posix()
        touched.append(rel)
        if mode == "--apply":
            new, n = apply_to(html)
            p.write_text(new, encoding="utf-8")
            fixed += n
    print("=" * 70)
    print("  LEARN TABLE HEADERS — does the scroll wrapper actually scroll?")
    print("=" * 70)
    have_tables = sum(1 for f in pages
                      if "<table" in Path(f).read_text(encoding="utf-8", errors="replace"))
    if mode == "--apply":
        print("  %d article(s) with tables · added white-space:nowrap to %d rule(s) on %d page(s)"
              % (have_tables, fixed, len(touched)))
    else:
        print("  %d article(s) with tables · %d still crush their headers"
              % (have_tables, len(touched)))
    for t in touched:
        print("     %s" % t)
    print("-" * 70)
    if mode == "--check" and touched:
        print("  FAIL — a [data-table-scroll] region that cannot scroll.")
        print("  FIX: python tools/fix_learn_th_nowrap.py --apply")
        print("=" * 70)
        return 1
    print("  PASS — every table header holds one line, so the wrapper can scroll.")
    print("=" * 70)
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", m))

    bad = "<table></table><style>.prose-wh th { font-weight: 700; letter-spacing: 0.05em; }</style>"
    good = "<table></table><style>.prose-wh th { font-weight: 700; white-space: nowrap; }</style>"
    none = "<style>.prose-wh th { font-weight: 700; }</style>"  # no table at all

    ck(needs_fix(bad), "a th rule without nowrap on a page WITH a table is caught")
    ck(not needs_fix(good), "a th rule that already has nowrap is left alone")
    ck(not needs_fix(none), "a page with no table is not touched")

    out, n = apply_to(bad)
    ck(n == 1 and "white-space: nowrap;" in out, "the fix inserts exactly one declaration")
    ck("letter-spacing: 0.05em" in out, "the existing declarations survive the edit")
    ck(not needs_fix(out), "the fixed page no longer trips the check")
    out2, n2 = apply_to(out)
    ck(n2 == 0 and out2 == out, "re-running is a no-op (idempotent)")

    live = run("--check")
    ck(live == 0, "the live corpus is clean, so this registers as a ratchet")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--self-test" in argv:
        raise SystemExit(self_test())
    if "--apply" in argv:
        raise SystemExit(run("--apply"))
    raise SystemExit(run("--check"))
