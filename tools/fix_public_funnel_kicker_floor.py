"""
fix_public_funnel_kicker_floor.py — the public funnel's two kickers, below the floor on 95 pages.
=================================================================================================
MEASURED, 2026-09-16 (design-lens sweep of the detector baseline). Two byte-identical rules are
copied into every public learn article and every calculator page:

    .pill { ... font-size: 0.65rem; ... letter-spacing: 0.05em; text-transform: uppercase; }
    .cta-box .cta-eyebrow { ... font-size: 0.7rem; ... text-transform: uppercase; letter-spacing: 0.1em; }

  .pill      10.4px, on 95 files (35 learn articles + 60 calculator pages)
  .cta-eyebrow 11.2px, on 27 learn articles

Both sit below the platform's own 12px functional-text floor, and together they are the source of
the learn corpus's `undersized-ui-text` (35 files, one each) and `all-caps-body` (25) findings.

WHY UPPERCASE GOES TOO, and this is the part worth measuring rather than asserting. A short all-caps
kicker above a heading is legitimate typography. These are not that. Across the corpus:

    pill instances 38 · length min 2, median 32, p90 38, max 44 · 74% over 20 characters
    longest: "Project Manager · Template + 6-step playbook"    (44)
             "Engineering Design · Standards-referenced"        (41)
             "Integrations · SAP, Maximo, OPC-UA, MQTT"         (40)
    eyebrow: "The platform this guide is about" (32), "The tool this guide is about" (28)

A 44-character descriptive phrase set in 10.4px uppercase with 0.05em of extra tracking is the exact
case the craft floor names: uppercase removes the word shapes a reader recognises, and wide tracking
pulls apart the letters that remain. This is the same call already made on logbook/inventory/
integrations' `.wh-label`, for the same reason. The handful of genuinely badge-shaped pills ("P1",
"P2", "P3") are written in capitals in the SOURCE, so they render identically either way.

WHO READS THESE. Both rules live only on public pages - the learn articles and the calculators - which
are the search-arrival surfaces. The reader is an anonymous visitor on a phone who has never seen this
product before, and the pill is the first line of context they get under the title.

Learn and tools pages are NOT precached (sw.js reaches them through the cache-on-visit path), so this
needs no CACHE_NAME bump; the offline-shell gate is unaffected.

Idempotent: matches the exact old rule, so a second run finds nothing. Re-runnable.

Usage:  python tools/fix_public_funnel_kicker_floor.py [--check] [--self-test]
  --check      report what WOULD change, write nothing (exit 1 if changes are pending)
  --self-test  prove the patcher on fixtures, touching no real file
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from served_page_set import served_pages as _served_pages   # ONE definition of the page set


PILL_OLD = (".pill { display: inline-block; font-size: 0.65rem; font-weight: 700; padding: 3px 10px; "
            "border-radius: 100px; letter-spacing: 0.05em; text-transform: uppercase; }")
PILL_NEW = (".pill { display: inline-block; font-size: 0.75rem; font-weight: 700; padding: 3px 10px; "
            "border-radius: 100px; letter-spacing: 0.02em; }")

EYE_OLD = (".cta-box .cta-eyebrow { color: #F7A21B; font-size: 0.7rem; font-weight: 800; "
           "text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }")
EYE_NEW = (".cta-box .cta-eyebrow { color: #F7A21B; font-size: 0.75rem; font-weight: 800; "
           "letter-spacing: 0.02em; margin-bottom: 8px; }")

PAIRS = ((PILL_OLD, PILL_NEW, "pill"), (EYE_OLD, EYE_NEW, "eyebrow"))


def targets():
    """Every public funnel page: the learn articles and the calculator pages."""
    return _served_pages(ROOT)


def patch(text: str):
    n = {}
    for old, new, name in PAIRS:
        c = text.count(old)
        if c:
            text = text.replace(old, new)
            n[name] = c
    return text, n


def main() -> int:
    check = "--check" in sys.argv
    if "--self-test" in sys.argv:
        return self_test()

    changed, counts = [], {"pill": 0, "eyebrow": 0}
    for p in targets():
        t = p.read_text(encoding="utf-8", errors="replace")
        new, n = patch(t)
        if not n:
            continue
        changed.append((p, n))
        for k, v in n.items():
            counts[k] += v
        if not check:
            p.write_text(new, encoding="utf-8")

    verb = "WOULD lift" if check else "lifted"
    print("public-funnel kickers: %s %d .pill and %d .cta-eyebrow rule(s) to the 12px floor "
          "across %d file(s)." % (verb, counts["pill"], counts["eyebrow"], len(changed)))
    if changed:
        for p, n in changed[:4]:
            print("   %s  %s" % (p.relative_to(ROOT).as_posix(), n))
        if len(changed) > 4:
            print("   ... and %d more" % (len(changed) - 4))
    if check and changed:
        return 1
    return 0


def self_test() -> int:
    """Prove the patcher both ways without touching a real file."""
    ok = True

    got, n = patch("<style>%s</style>" % PILL_OLD)
    if n.get("pill") != 1 or "0.75rem" not in got or "uppercase" in got:
        print("FAIL: the pill rule was not lifted"); ok = False

    got2, n2 = patch("<style>%s</style>" % EYE_OLD)
    if n2.get("eyebrow") != 1 or "0.75rem" not in got2 or "uppercase" in got2:
        print("FAIL: the eyebrow rule was not lifted"); ok = False

    # idempotent: a patched file offers nothing on a second pass
    _, n3 = patch(got)
    if n3:
        print("FAIL: not idempotent - a second run changed an already-patched rule"); ok = False

    # a rule that merely LOOKS similar is left alone, because the match is exact
    near = ".pill { display: inline-block; font-size: 0.65rem; font-weight: 600; }"
    _, n4 = patch(near)
    if n4:
        print("FAIL: matched a rule that is not the template"); ok = False

    print("self-test: %s" % ("PASS - lifts both rules, is idempotent, and ignores a near-miss" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
