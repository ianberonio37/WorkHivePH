"""
served_page_set.py — ONE definition of "every page this platform serves".
=========================================================================
Written because the same bug appeared twice in one day, in two different tools, for the same reason:
each carried its own hand-written glob list, and each list described where the author had been LOOKING
rather than where the construct LIVES.

  * the type-floor sweep globbed `learn/*/index.html` and walked straight past `learn/index.html` -
    the learn HUB, which sits directly in the folder - whose 55 findings were one 0.65rem rule
    painting 55 category chips.
  * the callout-border sweep globbed `learn/*/index.html` only, and missed the 60 CALCULATOR pages
    that carry the identical rules from the same shared prose template: 120 borders left behind by a
    sweep that reported itself complete.

A sweep reports what it changed and never what it never looked at, so "96 borders across 54 files"
reads exactly like completion. Centralising the set is what stops the next tool repeating it: a glob
is a CLAIM about coverage, and three tools each making their own claim is three chances to be wrong.

WHAT IS IN THE SET, and why each line exists:

    *.html                  the app and root pages
    learn/*.html            the learn HUB (learn/index.html) - the line both sweeps originally missed
    tools/*.html            the tools hub, same shape
    learn/*/index.html      the 54 learn articles
    tools/*/index.html      the 60 calculator pages

WHAT IS DELIBERATELY OUT:

    seo_assets/calc_pages_staging/**   staging, not served. It is also a trap - every staged page is
                                       older than its live twin - which `prove_calc_staging_not_stale`
                                       gates. Sweeping it would make those copies NEWER than live and
                                       flip that gate green while the trap was still real, so a sweep
                                       must never touch it.
    .emoji_bak/ .leftover_bak/ .hexvar_bak/ .palette_bak/   backups
    _fixtures/  node_modules/  .tmp/                        fixtures, deps, scratch
    video_marketing_app/  test-data-seeder/                 separate apps that are not this platform

SHARED CHROME is a separate call, because a sweep over page content and a staleness check over "the
build under test" want different sets: a page's behaviour depends on utils.js, but utils.js is not a
page.

    from served_page_set import served_pages, shared_chrome
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGE_GLOBS = ("*.html", "learn/*.html", "tools/*.html", "learn/*/index.html", "tools/*/index.html")

# ★DERIVED FROM sw.js's OWN SHELL_FILES, not hand-listed (2026-09-16). The first version of this
# tuple was typed from memory and omitted `wh-icons.css` - which a critique then showed governs every
# `.ic` glyph on every page, so an edit to it changes what a walk measures while the guard says
# nothing changed. A hand-written list of "the files that matter" is the same CLAIM-about-coverage
# the glob bug was, one layer up. The service worker already maintains this list for its own reasons;
# reading it keeps the two from drifting.
def _shell_from_sw():
    sw = ROOT / "sw.js"
    if not sw.is_file():
        return ()
    import re as _re
    m = _re.search(r"const SHELL_FILES\s*=\s*\[(.*?)\]", sw.read_text(encoding="utf-8", errors="replace"), _re.S)
    if not m:
        return ()
    names = _re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))
    return tuple(n.lstrip("/") for n in names if n.endswith((".js", ".css")) and "/" not in n.lstrip("/"))


# utils.js and wayfinding.js are NOT in SHELL_FILES (utils.js is served network-first by design, see
# the v347 bump note) but every page's behaviour depends on them, so they are named explicitly.
SHARED_CHROME = tuple(sorted(set(_shell_from_sw()) | {"utils.js", "wayfinding.js"}))

EXCLUDED_PREFIXES = ("seo_assets/", ".emoji_bak/", ".leftover_bak/", ".hexvar_bak/", ".palette_bak/",
                     "_fixtures/", "node_modules/", ".tmp/", "video_marketing_app/", "test-data-seeder/",
                     ".git/")


def served_pages(root: Path | None = None):
    """Every HTML page this platform serves, de-duplicated and sorted."""
    r = root or ROOT
    out = set()
    for g in PAGE_GLOBS:
        for p in r.glob(g):
            if not p.is_file():
                continue
            rel = p.relative_to(r).as_posix()
            if rel.startswith(EXCLUDED_PREFIXES):
                continue
            out.add(p)
    return sorted(out)


def shared_chrome(root: Path | None = None):
    """The files every page's behaviour depends on. Not pages; asked for separately on purpose."""
    r = root or ROOT
    return sorted(q for q in (r / n for n in SHARED_CHROME) if q.is_file())


def _self_test() -> int:
    ok = True
    pages = served_pages()
    rels = {p.relative_to(ROOT).as_posix() for p in pages}

    # the two files each original glob missed must both be present
    for must in ("learn/index.html", "index.html"):
        if must not in rels:
            print("FAIL: %s is missing from the served set" % must); ok = False
    if not any(r.startswith("tools/") and r.endswith("/index.html") for r in rels):
        print("FAIL: the calculator pages are missing"); ok = False
    if not any(r.startswith("learn/") and r.count("/") == 2 for r in rels):
        print("FAIL: the learn articles are missing"); ok = False

    # staging must NEVER be swept - sweeping it would defeat calc-staging-not-stale
    leaked = [r for r in rels if r.startswith("seo_assets/")]
    if leaked:
        print("FAIL: staging leaked into the served set (%d): %s" % (len(leaked), leaked[:3])); ok = False
    for bad in (".emoji_bak/", "_fixtures/", "node_modules/", "video_marketing_app/"):
        if any(r.startswith(bad) for r in rels):
            print("FAIL: %s leaked into the served set" % bad); ok = False

    if len(pages) != len(set(pages)):
        print("FAIL: the set contains duplicates"); ok = False

    # the shared-chrome set must come from sw.js, not from memory - wh-icons.css was the file the
    # hand-written version forgot, and it governs every `.ic` glyph on every page
    for must in ("wh-icons.css", "tokens.css", "components.css", "nav-hub.js", "utils.js"):
        if must not in SHARED_CHROME:
            print("FAIL: %s is missing from the shared-chrome set" % must); ok = False
    if len(SHARED_CHROME) < 15:
        print("FAIL: shared chrome has only %d entries - the sw.js SHELL_FILES parse probably "
              "silently returned nothing" % len(SHARED_CHROME)); ok = False
    missing = [n for n in SHARED_CHROME if not (ROOT / n).is_file()]
    if missing:
        print("FAIL: shared chrome names files that do not exist: %s" % missing[:4]); ok = False

    print("served pages: %d · shared chrome: %d" % (len(pages), len(shared_chrome())))
    print("self-test: %s" % ("PASS - hubs included, articles and calculators included, staging and "
                             "backups excluded, no duplicates" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
