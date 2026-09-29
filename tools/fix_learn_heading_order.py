"""
fix_learn_heading_order.py — Grounded Sweep (learn articles).
=============================================================
The static learn/*/index.html articles render an h1 (article title) immediately
followed by two template <h4>s — the table-of-contents label (<div class="toc">
<h4>What's in this guide</h4>) and the in-content CTA callout (<p class=
"cta-eyebrow">...</p><h4>...</h4>). That produces a WCAG 1.3.1 / axe
"heading-order" violation: h1 -> h4 (skips h2/h3) and h2 -> h4.

Each article carries its OWN inline <style>, so the low-blast-radius fix is
`aria-level`: ARIA overrides the computed heading level for assistive tech AND
axe's heading-order check, without touching the tag.

~W46129 SUPERSEDED (2026-09-20). Both branches of this sweep are now INERT, and
that is the intended end state rather than a regression. aria-level was the right
call while the styling was coupled to the tag; once the selectors matched both
tags, the tag itself could simply be correct. The TOC label is now <h2> on all 54
articles (tools/fix_learn_toc_label.py) and the CTA/related headings are <h3> on
all 27 (tools/fix_learn_cta_heading.py), so neither regex finds anything to patch.
The payoff is that `impeccable detect` agrees with the walk again: it reads the TAG
and ignored aria-level, so it reported a false `skipped-heading` on every one of
those articles while the walk measured headingSkips ZERO. Measured after: 2 -> 0 on
the page that surfaced it. This file is kept because a NEW article written by hand
against the old pattern would still be caught by it.

~W46101 CORRECTION (2026-09-20). This docstring used to say the visual styling
'keys on the h4 tag (`.toc h4`)' and is 'preserved exactly'. That was true of the
CTA callout and FALSE of the TOC label: `.toc h4` existed on 4 of the 49 articles
with a table of contents, while 45 carried `.toc h2` against <h4> markup and
rendered that label UNSTYLED at the browser default 16px - measured live. The
claim was never checked against the files. The selector is now `.toc h2, .toc h4`
on every article (tools/fix_learn_toc_label.py, gate `learn-toc-label`), so the
styling no longer depends on which tag the label happens to carry and this
sweep's aria-level approach is genuinely style-preserving.

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
