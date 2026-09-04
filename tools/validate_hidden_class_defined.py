#!/usr/bin/env python3
"""
validate_hidden_class_defined.py — a page that hides an element with `class="hidden"` must actually
load a stylesheet that DEFINES `.hidden`.

WHY (found live 2026-07-24, marketplace deepwalk J9): walking the first-time-seller dashboard as a
worker with no marketplace_sellers row, a dead "Load More" button sat under an empty inquiry list.
`#seller-load-more-wrap` carried `class="hidden"` and the JS toggled that class correctly, but
marketplace-seller.html links only tokens.css, which had no such rule -- so the element was
permanently visible. Six live pages were in that state (asset-hub, audit-log, community,
marketplace-admin, marketplace-seller, shift-brain).

The trap that makes this easy to ship and hard to see:
  * `wh-tw.css` (the self-hosted Tailwind subset) DOES define `.hidden{display:none}`, so the class
    works on every page that links it -- which is most of them. The pattern therefore looks correct
    everywhere you happen to check.
  * components.css has a `.hidden` rule, but it is SCOPED to `.action-card .ac-cta.hidden`. Grepping
    for ".hidden" in the stylesheets finds it and wrongly suggests coverage.
  * An ID-selector base style (`#toast{display:flex}`) OUTRANKS a `.hidden` class, so some elements
    are unaffected either way and hide by opacity instead. Those are not bugs.

So this gate resolves the class the way the browser does: only a rule whose selector is exactly
`.hidden` (optionally in a selector list) counts as defining it.

Static + offline. Self-test: `--selftest`. Forward-only: any page with an undefined `.hidden` FAILs.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# Backups / generated copies are not shipped surfaces.
SKIP_DIRS  = {".emoji_bak", ".hexvar_bak", ".leftover_bak", ".tmp", "radbak", "radbak2", "learn", "node_modules"}
# Design prototypes and kept-for-reference backups: not linked from the app, never in the SW shell, and
# several predate the current stylesheet split. They legitimately carry an undefined .hidden; holding
# them to this gate would only pressure someone to edit a dead file. Any SHIPPED page is still checked.
SKIP_SUFFIXES = ("-test.html", ".backup.html", ".backup2.html")

USES_HIDDEN = re.compile(r'class\s*=\s*"(?:[^"]*\s)?hidden(?:\s[^"]*)?"')
LINKED_CSS  = re.compile(r'<link[^>]+href="([^"]+\.css)"', re.I)


def defines_general_hidden(css: str) -> bool:
    """True only when a rule's selector is EXACTLY `.hidden` (alone or in a comma list).

    `.action-card .ac-cta.hidden` is a descendant/compound selector and must NOT count: it only ever
    applied to one component's CTA, which is exactly why the general case went unnoticed."""
    css = re.sub(r"/\*(?![\"']).*?\*/", " ", css, flags=re.S)          # strip comments (they mention .hidden)
    for m in re.finditer(r"([^{}]+)\{", css):
        for sel in m.group(1).split(","):
            if sel.strip() == ".hidden":
                return True
    return False


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan():
    css_cache: dict[str, bool] = {}

    def css_defines(name: str) -> bool:
        if name not in css_cache:
            p = ROOT / name.lstrip("./")
            css_cache[name] = defines_general_hidden(_read(p)) if p.exists() else False
        return css_cache[name]

    findings, checked = [], 0
    for page in sorted(ROOT.glob("*.html")):
        if page.name.endswith(SKIP_SUFFIXES) or any(part in SKIP_DIRS for part in page.parts):
            continue
        src = _read(page)
        if not USES_HIDDEN.search(src):
            continue
        checked += 1
        # Either an inline <style> in the page, or one of its linked local stylesheets.
        if defines_general_hidden(" ".join(re.findall(r"<style[^>]*>(.*?)</style>", src, re.S))):
            continue
        if any(css_defines(href) for href in LINKED_CSS.findall(src) if not href.startswith("http")):
            continue
        findings.append((page.name, len(USES_HIDDEN.findall(src))))
    return findings, checked


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    chk("bare .hidden rule counts", defines_general_hidden(".hidden { display: none; }"), True)
    chk("minified form counts", defines_general_hidden("a{b:c}.hidden{display:none}"), True)
    chk("selector-list membership counts",
        defines_general_hidden("[hidden], .hidden, .is-gone { display:none; }"), True)
    # the two shapes that made this bug invisible
    chk("SCOPED .action-card .ac-cta.hidden does NOT count",
        defines_general_hidden(".action-card .ac-cta.hidden { display:none; }"), False)
    chk("a comment mentioning .hidden does NOT count",
        defines_general_hidden("/* the .hidden utility lives elsewhere */ a{b:c}"), False)
    chk("compound .foo.hidden does NOT count", defines_general_hidden(".foo.hidden{display:none}"), False)
    # markup matcher
    chk("matches class=\"hidden\"", bool(USES_HIDDEN.search('<div class="hidden">')), True)
    chk("matches it among other classes", bool(USES_HIDDEN.search('<div class="row hidden pad">')), True)
    chk("does not match a lookalike class",
        bool(USES_HIDDEN.search('<div class="hidden-xs">')), False)
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    findings, checked = scan()
    print(f"{BOLD}.hidden class is actually defined ({checked} page(s) use it){RESET}")
    if not findings:
        print(f"  {GREEN}PASS{RESET}  every page using class=\"hidden\" loads a stylesheet that defines it")
        return 0
    for name, n in findings:
        print(f"  {RED}FAIL{RESET}  {name}: {n} element(s) use class=\"hidden\" but no loaded stylesheet "
              f"defines a general .hidden rule -> they render permanently VISIBLE")
    print(f"  Fix: link wh-tw.css/tokens.css/components.css, or add `.hidden {{ display: none; }}` to the page.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
