"""
fix_subpage_a11y.py — Grounded Sweep (axe-core findings on static subpages).
============================================================================
Live axe-core (WCAG 2 A/AA) scan of the learn + legal static subpages surfaced
two template-level violations my element-checks missed:

  1. color-contrast (serious): the footer uses `text-white/35`
     (rgba(255,255,255,0.35)) which composites to ~#626a72 on the dark footer
     bg = 3.22:1, below the 4.5:1 AA floor for normal text. Bump to /60
     (~6.9:1) — still muted, now legible.
  2. scrollable-region-focusable (serious): `.prose-wh pre` code blocks have
     overflow-x:auto but no keyboard access. Add tabindex="0" so they're
     focus-scrollable.

Idempotent + re-runnable. Repo-wide over subdir index.html (learn/*, about/,
feedback/, privacy-policy/, terms-of-service/).

Usage:  python tools/fix_subpage_a11y.py [--check]
"""
from __future__ import annotations
import io, re, sys, glob, os
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
# <pre ...> without a tabindex (don't double-add)
_PRE_RE = re.compile(r'<pre\b(?![^>]*\btabindex=)', re.IGNORECASE)


def patch(text: str) -> tuple[str, int]:
    n = 0
    # 1) footer contrast: the muted footer container
    new, c1 = re.subn(r'text-white/35\b', 'text-white/60', text)
    n += c1
    # 2) scrollable <pre> keyboard access
    new, c2 = _PRE_RE.subn('<pre tabindex="0"', new)
    n += c2
    return new, n


def main() -> int:
    check = "--check" in sys.argv
    targets = sorted(glob.glob(str(ROOT / "**" / "index.html"), recursive=True))
    scaffold = ROOT / "tools" / "scaffold_article.py"
    if scaffold.exists():
        targets.append(str(scaffold))
    changed, total = [], 0
    for fp in targets:
        if "node_modules" in fp or "test-data-seeder" in fp:
            continue
        p = Path(fp)
        text = p.read_text(encoding="utf-8", errors="replace")
        new, n = patch(text)
        if n and new != text:
            total += n
            changed.append((os.path.relpath(fp, ROOT).replace("\\", "/"), n))
            if not check:
                p.write_text(new, encoding="utf-8")
    verb = "WOULD fix" if check else "fixed"
    print(f"subpage a11y: {verb} {total} edit(s) across {len(changed)} file(s).")
    for rel, n in changed[:50]:
        print(f"  {rel:<58s} +{n}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
