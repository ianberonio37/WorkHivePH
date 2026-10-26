#!/usr/bin/env python3
"""advice-names-a-real-filter - advice that says 'Filter to "X"' must point at a filter the page offers (2026-10-27).

inventory.html's next-step box told a supervisor 'Filter to "Pending approval" below and sign off' - and the status
filter had no such option (All stock, Below reorder point, Out of stock, Critical low, Low stock, In stock, Surplus).
A worker's own pending part sat on page 4 of an 8-row list under a card that said REVIEW with nothing to tap. Advice that
names a control the reader cannot find is worse than no advice: it sends them looking for something that is not there.

ASSERTION: every English 'Filter to "<label>"' in a production page names an <option> or a button/chip on that same
page whose visible text is <label> (case-insensitive).

    python tools/validate_advice_names_a_real_filter.py [--ref HEAD]
"""
from __future__ import annotations

import glob
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADVICE = re.compile(r"""Filter to [\\]?["“]([^"”\\]{2,40})[\\]?["”]""")
OPTION = re.compile(r"<option\b[^>]*>([^<]{1,60})</option>", re.I)
CONTROL = re.compile(r"<(?:button|a)\b[^>]*>([^<]{1,60})</(?:button|a)>", re.I)


def _pages(ref: str | None) -> dict[str, str]:
    out = {}
    if ref:
        names = subprocess.run(["git", "ls-tree", "--name-only", ref], cwd=ROOT, capture_output=True, text=True).stdout.split()
        for n in names:
            if n.endswith(".html"):
                out[n] = subprocess.run(["git", "show", f"{ref}:{n}"], cwd=ROOT, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace").stdout
        return out
    for p in glob.glob(str(ROOT / "*.html")):
        out[Path(p).name] = Path(p).read_text(encoding="utf-8", errors="replace")
    return out


def check(pages: dict[str, str]) -> list[str]:
    bad = []
    for name, src in sorted(pages.items()):
        asked = {m.group(1).strip() for m in ADVICE.finditer(src)}
        if not asked:
            continue
        offered = {html.unescape(t).strip().lower() for t in OPTION.findall(src) + CONTROL.findall(src)}
        for label in sorted(asked):
            if label.lower() not in offered:
                bad.append(f"{name}: advice says 'Filter to \"{label}\"' but no option or control on the page reads '{label}'")
    return bad


def self_test() -> int:
    bad = check({"x.html": '<select><option value="">All</option></select><script>t="Filter to \\"Pending approval\\" below"</script>'})
    good = check({"x.html": '<select><option value="pending">Pending approval</option></select><script>t="Filter to \\"Pending approval\\""</script>'})
    ok = len(bad) == 1 and not good
    print(("PASS" if ok else "FAIL") + " advice-names-a-real-filter self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    bad = check(_pages(ref))
    print("advice-names-a-real-filter - every 'Filter to \"X\"' names a filter the page offers")
    for b in bad:
        print("  - " + b)
    print("PASS" if not bad else f"FAIL - {len(bad)} piece(s) of advice name a filter that is not there")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
