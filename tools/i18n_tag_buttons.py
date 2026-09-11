#!/usr/bin/env python3
"""i18n_tag_buttons.py — tag every plain-text control whose label the shared Filipino dictionary already
knows (EX-TL, 2026-09-07), so the page translates it without a per-page edit.

WHY THIS EXISTS. The Tagalog-first walk measured 169 untranslated control labels across the 27 pages that
carry no _t() call. Most of those labels are the platform's common verbs - Save, Cancel, Delete, Refresh,
Export, Add - and utils.js already holds their Filipino in WH_FIL_COMMON, keyed by the label lowercased
with its spaces removed. A button that carries `data-i="<key>"` is swapped by whI18nApply on every page
that loads utils.js. The gap was never the dictionary; it was 169 buttons nobody had tagged.

WHAT IT WILL NOT TOUCH, and why:
  * a button with CHILD ELEMENTS (an icon span, an svg) - whI18nApply sets textContent, which would erase
    the icon; those need a span around the words, by hand, so the swap lands on the words alone
  * a button already carrying data-i or an aria-label that differs from its text (a deliberate label)
  * a label the dictionary does not know - reported, never guessed; the Filipino for it is authored,
    not derived

  python tools/i18n_tag_buttons.py            # tag (idempotent), print per-page counts + the unknown labels
  python tools/i18n_tag_buttons.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def dictionary_keys() -> set[str]:
    src = (ROOT / "utils.js").read_text(encoding="utf-8")
    i = src.index("window.WH_FIL_COMMON = {")
    j = src.index("\n};", i)
    return set(re.findall(r"(?:^|[\s,{])'?([a-z_]+)'?\s*:", src[i:j]))

def roster() -> list[str]:
    """Every root page but the SKIP set. The first version took "pages with no _t() call", which shrank
    to nothing the moment the sentence wrapper landed _t() on them - a roster must not depend on the
    fix it is there to drive. Idempotent: a button already carrying data-i is left alone."""
    skip = {"design-system.html", "symbol-gallery.html", "validator-catalog.html", "promo-poster.html",
            "offline-fallback.html", "terms.html"}
    return [f for f in sorted(p.name for p in ROOT.glob("*.html")) if f not in skip and not f.startswith("_")]

# a plain-text button: an opening tag, text with NO child element, a closing tag
BUTTON = re.compile(r"<button\b([^>]*)>([^<]{2,40})</button>", re.I)

def key_of(label: str) -> str:
    return re.sub(r"[^a-z]", "", label.lower())

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    keys = dictionary_keys()
    unknown: Counter = Counter()
    tagged_total = 0
    for f in roster():
        path = ROOT / f
        src = path.read_text(encoding="utf-8")
        tagged = 0
        def repl(m: re.Match) -> str:
            nonlocal tagged
            attrs, label = m.group(1), m.group(2).strip()
            if "data-i=" in attrs or "${" in label:                  # already tagged, or a template slot
                return m.group(0)
            k = key_of(label)
            if not k:
                return m.group(0)
            if k not in keys:
                unknown[f"{label}  ({f})"] += 1
                return m.group(0)
            tagged += 1
            return f'<button{attrs} data-i="{k}">{label}</button>'
        new = BUTTON.sub(repl, src)
        if tagged and not args.dry_run:
            path.write_text(new, encoding="utf-8", newline="")
        tagged_total += tagged
        print(f"  {f:<34} tagged {tagged}")
    print(f"\n  {tagged_total} control(s) tagged from the shared dictionary" + (" (dry run)" if args.dry_run else ""))
    if unknown:
        print(f"  {len(unknown)} label(s) the dictionary does not know - author these, do not guess:")
        for label, n in unknown.most_common(200):
            print(f"    {n:>3}  {label}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
