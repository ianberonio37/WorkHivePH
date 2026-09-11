#!/usr/bin/env python3
"""fix_learn_contrast_remap.py - carry the platform's white-opacity contrast decision to the learn pages.

★THE APP FIXED ITS CONTRAST AND THE PUBLIC PAGES NEVER HEARD (walked 2026-09-10, FILIPINO, phone-390).
The RA 11285 guide graded C2 97% with its whole byline - "By WorkHive Editorial Team", the date, "9 min
read" - at 4.27:1 against the 4.5:1 that 12px text owes. The colour comes from Tailwind's `text-white/45`.

The platform ALREADY decided this: its own build, wh-tw.css, deliberately remaps seven low-opacity white
utilities away from their stock values -

    text-white/45 -> 0.8    text-white/55 -> 0.8    text-white/65 -> 0.85    text-white/75 -> 0.85
    text-white/50 -> 0.8    text-white/60 -> 0.8    text-white/70 -> 0.85

- so /45 renders at 0.8 everywhere in the app. The 54 learn articles never got it, because they load
Tailwind from the CDN (cdn.tailwindcss.com) instead of wh-tw.css, and the CDN ships the stock ramp. All
seven classes are in use across the catalogue: /60 on all 54 pages, /55 on 53, /45 on 45, /75 on 27,
/65 on 19, /50 on 8, /70 on 1. The most PUBLIC surface on the platform - the pages a search arrival meets
first - has been the one place the contrast remediation did not reach.

WHY body-SCOPED AND NOT !important. The CDN injects its utilities at runtime, so a plain `.text-white/45`
override can lose on source order. `body .text-white/45` is specificity (0,1,1) against the utility's
(0,1,0) and wins regardless of order, with no !important and no cascade debt. Verified live before this
tool was written: the byline moved 0.45 -> 0.8 with the body-scoped rule alone.

  python tools/fix_learn_contrast_remap.py            # dry run
  python tools/fix_learn_contrast_remap.py --apply
  python tools/fix_learn_contrast_remap.py --self-test
"""
from __future__ import annotations

import glob
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BS = chr(92)                       # a literal backslash, built rather than escaped (heredoc-safe)
MARK = "wh-learn-contrast-remap"   # idempotency marker

# class -> the platform's own value in wh-tw.css (NOT the stock n/100)
REMAP = [("45", "0.8"), ("50", "0.8"), ("55", "0.8"), ("60", "0.8"),
         ("65", "0.85"), ("70", "0.85"), ("75", "0.85")]


def block() -> str:
    """The override block, matching wh-tw.css exactly. body-scoped so it beats the CDN on specificity."""
    lines = [f"    /* {MARK}: the learn pages load Tailwind from the CDN, so they miss the contrast",
             "       remap wh-tw.css applies app-wide. 12px byline text at /45 measured 4.27:1 against the",
             "       4.5:1 it owes. body-scoped (0,1,1) so it wins over the CDN utility whatever the order. */"]
    for n, v in REMAP:
        lines.append(f"    body .text-white{BS}/{n} {{ color: rgb(255 255 255 / {v}); }}")
    return "\n".join(lines)


def needs_fix(src: str) -> bool:
    return "<style>" in src and MARK not in src


def apply_block(src: str) -> str:
    if not needs_fix(src):
        return src
    i = src.index("<style>") + len("<style>")
    return src[:i] + "\n" + block() + src[i:]


def main() -> int:
    apply = "--apply" in sys.argv
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    if not files:
        print("refused: no learn articles found - a fixer that matches nothing is a broken path")
        return 1
    changed, already, skipped = [], [], []
    for f in files:
        src = io.open(f, encoding="utf-8").read()
        if MARK in src:
            already.append(f); continue
        if "<style>" not in src:
            skipped.append(f); continue
        if apply:
            io.open(f, "w", encoding="utf-8", newline="").write(apply_block(src))
        changed.append(f)
    print(f"{'APPLIED' if apply else 'DRY RUN'}: {len(changed)} article(s) "
          f"{'given' if apply else 'would get'} the contrast remap; {len(already)} already had it"
          + (f"; {len(skipped)} skipped (no <style>)" if skipped else ""))
    if not apply and changed:
        print("  re-run with --apply to write")
    return 0


def _self_test() -> int:
    fails = []
    page = "<html><head>\n  <style>\n    body { font-family: 'Poppins'; }\n  </style></head></html>"
    out = apply_block(page)
    if "text-white" + BS + "/45" not in out:
        fails.append("the /45 override must be written with a real backslash before the slash")
    if "rgb(255 255 255 / 0.8)" not in out:
        fails.append("the value must match wh-tw.css (0.8 for /45), not the stock 0.45")
    if "body .text-white" not in out:
        fails.append("the rule must be body-scoped so it beats the CDN utility on specificity")
    if "!important" in out:
        fails.append("no !important - specificity is what makes this win, and it was verified live")
    if out.index(MARK) > out.index("font-family"):
        fails.append("the block must land first in the style block")
    if apply_block(out) != out:
        fails.append("applying twice must be a no-op - the marker makes it idempotent")
    if len([1 for n, _ in REMAP if f"text-white{BS}/{n}" in out]) != 7:
        fails.append("all seven remapped classes must be emitted - the learn pages use every one")

    nostyle = "<p>no style</p>"
    if needs_fix(nostyle) or apply_block(nostyle) != nostyle:
        fails.append("a page with no <style> must be skipped untouched")

    print("FAIL fix_learn_contrast_remap self-test - " + "; ".join(fails) if fails
          else "self-test OK: all seven classes emitted at wh-tw.css's values, body-scoped, no "
               "!important, lands first, and applying twice changes nothing")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
