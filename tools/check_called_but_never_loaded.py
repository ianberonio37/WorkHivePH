#!/usr/bin/env python3
"""check_called_but_never_loaded.py — a page that CALLS a platform function no file it LOADS defines.

★THE DEFECT THIS EXISTS FOR. All 60 calculator pages ended with, verbatim:

    window.WH_FIL_PAGE = { calc_how: 'Paano ito gumagana', ... };
    if (typeof whI18nApply === 'function' && window.WH_LANG === 'fil') whI18nApply(window.WH_FIL_PAGE);

`whI18nApply` is defined in exactly one file, utils.js, and NOT ONE of those 60 pages loads utils.js. The
guard `typeof whI18nApply === 'function'` reads as care and is a permanent no-op: no error, no console
warning, nothing any gate could see. A complete Filipino dictionary was written, translated, shipped and
called by every page — and reachable by none. A Filipino-first reader met English on the platform's most
public surface, and every existing check passed.

The shape generalises, which is why this is a gate and not a one-off fix: **a typeof guard around a global
turns "this file was never loaded" from a loud error into silence.** That is the same family as a lock
nothing runs and a handler built but never called — the code exists, the call exists, and the wire between
them does not. Only a check that reads BOTH sides at once can see it.

What it does: for each HTML page, collect the functions it calls that look like platform globals (whFoo,
whI18nApply, ...), collect the scripts it loads, and report any call whose definition lives in no loaded
file. Third-party and browser globals are ignored; a page that defines the function inline is fine.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# a platform global: the project's own naming, so third-party and browser APIs are out of scope by shape
CALL = re.compile(r"\b(wh[A-Z][A-Za-z0-9_]{2,}|_t)\s*\(")
DEFINE = re.compile(r"(?:function\s+(wh[A-Z][A-Za-z0-9_]{2,})|"
                    r"(?:window\.)?(wh[A-Z][A-Za-z0-9_]{2,})\s*=\s*(?:function|\(|async))")
SCRIPT_SRC = re.compile(r"<script[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
SCRIPT_INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.I | re.S)

SKIP_DIRS = ("node_modules", ".tmp", ".emoji_bak", "seo_assets", "coverage", "playwright-report")


def defined_in(path: Path) -> set:
    try:
        return {m.group(1) or m.group(2) for m in DEFINE.finditer(path.read_text(encoding="utf-8", errors="replace"))}
    except OSError:
        return set()


def self_test() -> int:
    """★PROVE IT SEES THE DEFECT AND DOES NOT INVENT ONE. A gate for silent breakage is itself easy to make
    silent: if the call pattern or the script-src pattern misses, it reports a clean platform forever.
    """
    fails = []
    calls = lambda s: {m.group(1) for m in CALL.finditer(s)}
    defs = lambda s: {m.group(1) or m.group(2) for m in DEFINE.finditer(s)}

    if "whI18nApply" not in calls("if (typeof whI18nApply === 'function') whI18nApply(window.WH_FIL_PAGE);"):
        fails.append("the real broken call is not recognised as a call")
    if "whI18nApply" not in defs("function whI18nApply(dict) {"):
        fails.append("a plain function declaration is not recognised as a definition")
    if "whFoo" not in defs("window.whFoo = function () {"):
        fails.append("a window.x = function assignment is not recognised as a definition")
    if calls("JSON.parse(x); fetch(y); querySelector(z);"):
        fails.append("a browser API is being treated as a platform global")
    if SCRIPT_SRC.findall('<script defer src="/utils.js"></script>') != ["/utils.js"]:
        fails.append("a deferred script src is not being seen as loaded")
    if SCRIPT_SRC.findall("<script>whFoo();</script>"):
        fails.append("an inline script is being read as a src")
    body = SCRIPT_INLINE.findall('<script src="/a.js"></script><script>whFoo();</script>')
    if len(body) != 1 or "whFoo" not in body[0]:
        fails.append("inline script bodies are not being separated from sourced ones")
    print("FAIL called-but-never-loaded self-test - " + "; ".join(fails) if fails
          else "self-test OK: 7 mutations, each caught - the gate can see a call, a definition and a load")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    only = None
    for i, arg in enumerate(sys.argv):
        if arg == "--page" and i + 1 < len(sys.argv):
            only = sys.argv[i + 1]

    # what every js file in the project defines
    defines = {}
    for js in glob.glob(str(ROOT / "**" / "*.js"), recursive=True):
        p = Path(js)
        if any(s in p.as_posix() for s in SKIP_DIRS):
            continue
        for name in defined_in(p):
            defines.setdefault(name, set()).add(p.name)

    pages = [only] if only else [
        f for f in glob.glob(str(ROOT / "**" / "*.html"), recursive=True)
        if not any(s in Path(f).as_posix() for s in SKIP_DIRS)
    ]

    broken = []
    for f in pages:
        p = Path(f)
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        loaded = {Path(s).name for s in SCRIPT_SRC.findall(raw)}
        inline = "\n".join(SCRIPT_INLINE.findall(raw))
        inline_defs = {m.group(1) or m.group(2) for m in DEFINE.finditer(inline)}
        for m in CALL.finditer(inline):
            name = m.group(1)
            if name in inline_defs or name == "_t":
                continue
            homes = defines.get(name)
            if not homes:
                continue                       # not a platform global we can locate; not this gate's business
            if homes & loaded:
                continue                       # a file that defines it IS loaded
            broken.append((p.relative_to(ROOT).as_posix(), name, sorted(homes)[:2]))

    by_name = {}
    for page, name, homes in broken:
        by_name.setdefault((name, tuple(homes)), []).append(page)

    print(f"pages read: {len(pages)}")
    print(f"calls to a platform function no loaded file defines: {len(broken)}")
    for (name, homes), pgs in sorted(by_name.items(), key=lambda kv: -len(kv[1])):
        print(f"\n  {name}() is called by {len(pgs)} page(s) but defined only in {', '.join(homes)}:")
        for pg in pgs[:6]:
            print(f"     {pg}")
        if len(pgs) > 6:
            print(f"     ... and {len(pgs) - 6} more")
    if not broken:
        print("  every platform call has a file that defines it among the page's own scripts")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
