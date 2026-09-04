#!/usr/bin/env python3
"""icon-meaning-registry - T179: one glyph, one meaning (2026-08-26).

An icon-only control teaches by repetition. A worker learns that a small x in the
corner makes something go away, and after the tenth time they stop reading and just
tap. That learned reflex is the whole value of an icon - and the whole danger, because
the moment the same glyph does something ELSE, the reflex fires anyway.

CENSUSED every icon-only button across the app pages (a button whose visible text is
glyphs plus at most 3 other characters). Five glyphs are in use; two carried trouble:

  ✕ meant Close, Remove, AND "Delete resume <title>" - the same mark for "dismiss this
    panel" and for "permanently destroy the resume you spent an hour building". A person
    who has learned ✕ = go away taps it expecting dismissal. Fixed by adopting the
    platform's OWN declared delete glyph: audit-log.html:790 maps edit:'✎', delete:'🗑',
    so the resume delete is now 🗑 and ✕ is left meaning dismiss.

  × appeared on three project-manager buttons carrying `title="Remove"` and NO
    aria-label. ★THE TITLE DOES NOT SAVE IT: the accessible-name order is
    aria-labelledby, aria-label, CONTENT, then title - so content wins and a screen
    reader announces "multiplication sign", never reaching the title. On touch there is
    no hover, so a phone user gets nothing at all. Each now names what it removes
    ("Remove scope item <title>", "Remove link <label>", "Remove <name> from this
    project") rather than a bare "Remove", since three identical "Remove" buttons in one
    list are their own kind of unusable.

TWO ASSERTIONS:
  named    every icon-only button has an accessible name that is not just its glyph
  onemean  no glyph carries both a DISMISS meaning (close/cancel/hide) and a DESTROY
           meaning (delete/erase/permanently remove)

★"Remove" IS DELIBERATELY NOT TREATED AS DESTROY. Removing a link from a list or a
person from a project is undoable list-editing, and lumping it with delete would force
a second glyph for something users correctly read as dismissal. The line is drawn at
destruction of a user's own artifact.

Usage: python tools/validate_icon_meaning_registry.py
"""
import glob
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

BTN = re.compile(r"<button[^>]*>(.*?)</button>", re.S | re.I)
ARIA = re.compile(r"aria-label(?:ledby)?=[\"']([^\"']+)", re.I)
GLYPH = re.compile("[\U0001F300-\U0001FAFF←-⇿⌀-➿⬀-⯿×✕✖✓✔]")
SKIP = re.compile(r"backup|test|^index-", re.I)

DISMISS = re.compile(r"\b(close|dismiss|cancel|hide|collapse)\b", re.I)
DESTROY = re.compile(r"\b(delete|erase|destroy|permanently)\b", re.I)


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html"))) if not SKIP.search(Path(f).name)]
    if not files:
        print("SKIP icon-meaning-registry - no pages found")
        return 0

    meanings = defaultdict(set)
    unnamed = []
    total = 0
    for f in files:
        name = Path(f).name
        src = io.open(f, encoding="utf-8", errors="replace").read()
        for m in BTN.finditer(src):
            tag, inner = m.group(0), re.sub(r"<[^>]+>", "", m.group(1)).strip()
            glyphs = [g for g in GLYPH.findall(inner) if g != "️"]
            if not glyphs:
                continue
            # ★ICON-ONLY MEANS NOTHING BUT THE GLYPH. An earlier version allowed "at most 3 other
            # characters" and promptly flagged six buttons that are perfectly fine: "⬇ CSV",
            # "⬇ PDF", "⬇ SVG", "🟢 Low". Those are icon+LABEL, and their visible text IS their
            # accessible name - demanding an aria-label there would be ceremony. The control this
            # gate exists for is the one showing a mark and nothing else, where a reader has only
            # the glyph to go on.
            if GLYPH.sub("", inner).strip():
                continue
            total += 1
            a = ARIA.search(tag)
            if not a:
                unnamed.append(f"{name}: icon-only <button>{inner[:8]}</button> has no accessible name")
                continue
            for g in set(glyphs):
                meanings[g].add(a.group(1).strip())

    clashes = []
    for g, labels in meanings.items():
        dis = sorted(l for l in labels if DISMISS.search(l))
        des = sorted(l for l in labels if DESTROY.search(l))
        if dis and des:
            clashes.append(f"{g!r} means both dismiss ({dis[0][:34]}) and destroy ({des[0][:34]})")

    print(f"  icon-only buttons: {total} | distinct glyphs: {len(meanings)} | unnamed: {len(unnamed)} "
          f"| glyph clashes: {len(clashes)}")
    fails = unnamed + clashes
    if fails:
        print(f"FAIL icon-meaning-registry - {len(fails)} problem(s):")
        for x in fails[:12]:
            print("    - " + x)
        if len(fails) > 12:
            print(f"    ... and {len(fails) - 12} more")
        print("    An icon-only button's accessible name comes from aria-label, then CONTENT, then")
        print("    title - so a `title` behind a glyph is never announced, and on touch it never shows.")
        print("    And a glyph that both dismisses and destroys will eventually destroy by reflex: use")
        print("    the platform's delete glyph (audit-log.html:790 maps delete to a wastebasket).")
        return 1
    print(f"PASS icon-meaning-registry - all {total} icon-only buttons are named, and no glyph both "
          f"dismisses and destroys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
