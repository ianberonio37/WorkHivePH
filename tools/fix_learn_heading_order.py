"""
fix_learn_heading_order.py — Grounded Sweep (learn articles).
=============================================================
The static learn/*/index.html articles render an h1 (article title) immediately
followed by two template <h4>s — the table-of-contents label (<div class="toc">
<h4>What's in this guide</h4>) and the in-content CTA callout (<p class=
"cta-eyebrow">...</p><h4>...</h4>). That produces a WCAG 1.3.1 / axe
"heading-order" violation: h1 -> h4 (skips h2/h3) and h2 -> h4.

Each article carries its OWN inline <style> keyed on the tag (`.toc h4`,
`.cta-box h4`), so changing the tag would break styling across 37 files. The
low-blast-radius fix is `aria-level`: ARIA overrides the computed heading level
for assistive tech AND axe's heading-order check, while the visual styling
(which keys on the h4 tag) is preserved exactly.

  - TOC label   -> aria-level="2"  (peer of the article's top-level sections)
  - CTA callout -> aria-level="3"  (subordinate to the surrounding h2 section)

Idempotent: skips any <h4> that already declares aria-level. Re-runnable.
Also patches tools/scaffold_article.py so NEW articles are born correct.

Usage:  python tools/fix_learn_heading_order.py [--check]
  --check : report what WOULD change, write nothing (exit 1 if changes pending).
"""
from __future__ import annotations
import io, re, sys, glob, os
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# TOC label: the <h4> immediately inside <div class="toc"> (no aria-level yet).
_TOC_RE = re.compile(r'(<div class="toc">\s*<h4)(?![^>]*aria-level)(>)', re.IGNORECASE)
# CTA callout: the <h4> right after a <p class="cta-eyebrow">...</p> (no aria-level yet).
_CTA_RE = re.compile(r'(<p class="cta-eyebrow">.*?</p>\s*<h4)(?![^>]*aria-level)(>)', re.IGNORECASE)


def patch(text: str) -> tuple[str, int]:
    out, n1 = _TOC_RE.subn(r'\1 aria-level="2"\2', text)
    out, n2 = _CTA_RE.subn(r'\1 aria-level="3"\2', out)
    return out, n1 + n2


def main() -> int:
    check = "--check" in sys.argv
    targets = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    scaffold = ROOT / "tools" / "scaffold_article.py"
    if scaffold.exists():
        targets.append(str(scaffold))

    changed, total_edits = [], 0
    for fp in targets:
        p = Path(fp)
        text = p.read_text(encoding="utf-8", errors="replace")
        new, n = patch(text)
        if n > 0 and new != text:
            total_edits += n
            changed.append((os.path.relpath(fp, ROOT), n))
            if not check:
                p.write_text(new, encoding="utf-8")

    verb = "WOULD fix" if check else "fixed"
    print(f"learn heading-order: {verb} {total_edits} <h4>(s) across {len(changed)} file(s).")
    for rel, n in changed:
        print(f"  {rel:<60s} +{n}")
    if check and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
