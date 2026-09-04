#!/usr/bin/env python3
"""lang-declared - T159: the page must say which language it is in (2026-08-26).

A screen reader picks its pronunciation rules from `<html lang>`. Filipino text
announced under `lang="en"` comes out as English phonemes applied to Tagalog words -
not accented, but wrong in a way that makes the sentence unrecoverable. WCAG 3.1.1
asks for the page's language; 3.1.2 asks that a change of language be marked.

This platform is bilingual by toggle, not by URL: one page, `_t(en, fil)` at every
string, and a `wh_lang` preference. So the declaration is not a static fact set once at
build time - it has to FOLLOW the toggle, and that is the half a static audit misses.

MEASURED 2026-08-26 and the discipline is clean:
  * all 156 public pages declare <html lang> (every one "en"; no page is silent)
  * utils.js:219 sets documentElement.lang from the stored locale on EVERY page load,
    so a reader who chose Filipino gets the right declaration everywhere, including on
    pages that have no translation engine of their own
  * all three pages that WRITE wh_lang (index, analytics, analytics-report) also set
    documentElement.lang in their toggle handler, so switching mid-session updates the
    declaration without a reload

TWO ASSERTIONS:
  declared   every public page carries <html lang="...">
  follows    any page that writes the wh_lang preference must also assign
             documentElement.lang - a toggle that changes the words while leaving the
             declaration behind is worse than no toggle, because the page now asserts a
             language it is not in

★NO hreflang IS ASSERTED, and that is deliberate rather than an omission. hreflang
describes ALTERNATE URLs for the same content, and this platform has none - the locale
lives in localStorage, so /learn/x is one URL serving whichever language the reader
chose. Demanding hreflang here would be demanding a second site. Whether to publish a
Filipino public corpus at all is T159's open posture question and Ian's to answer; this
gate holds the part that is true under either answer.

Usage: python tools/validate_lang_declared.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"backup|test|^index-", re.I)

HTML_LANG = re.compile(r"<html[^>]*\blang=[\"']([^\"']+)", re.I)
WRITES_PREF = re.compile(r"localStorage\.setItem\(\s*[\"']wh_lang")
SETS_LANG = re.compile(r"documentElement\.lang\s*=")


def main() -> int:
    pages = (sorted(glob.glob(str(ROOT / "*.html")))
             + sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
             + sorted(glob.glob(str(ROOT / "tools" / "*" / "index.html")))
             + sorted(glob.glob(str(ROOT / "about" / "index.html"))))
    pages = [p for p in pages if not SKIP.search(Path(p).name)]
    if not pages:
        print("SKIP lang-declared - no pages found")
        return 0

    silent, drifting, declared = [], [], 0
    for p in pages:
        rel = Path(p).parent.name if Path(p).name == "index.html" else Path(p).name
        src = io.open(p, encoding="utf-8", errors="replace").read()
        if not HTML_LANG.search(src[:6000]):
            silent.append(rel)
        else:
            declared += 1
        if WRITES_PREF.search(src) and not SETS_LANG.search(src):
            drifting.append(rel)

    print(f"  public pages: {len(pages)} | declaring <html lang>: {declared} | "
          f"toggles that update it: {len(pages) - len(drifting)}")
    fails = ([f"{x}: no <html lang> - a screen reader has no pronunciation rule to pick" for x in silent]
             + [f"{x}: writes the wh_lang preference but never assigns documentElement.lang - the words "
                f"change and the declaration does not" for x in drifting])
    if fails:
        print(f"FAIL lang-declared - {len(fails)} page(s):")
        for x in fails[:10]:
            print("    - " + x)
        print("    Filipino text announced under lang='en' is English phonemes applied to Tagalog - not")
        print("    accented, but unrecoverable. utils.js:219 sets this from the stored locale at load;")
        print("    a page owning a toggle must do the same when the reader switches.")
        return 1
    print(f"PASS lang-declared - all {declared} public pages declare their language, and every toggle "
          f"that changes it updates the declaration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
