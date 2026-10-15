#!/usr/bin/env python3
"""validate_kept_copy_says_so.py - a page answered from the copy kept on a past visit says that is what it is (SL CA4,
2026-10-16).

Walked offline with the worker allowed: a learn article and a calculator, answered from the kept copy, rendered in full and
said NOTHING - no sign the network was gone, that this was a saved copy, or how old it was. The logbook said "you are
offline" four ways and never that the page itself was the copy from the last visit. Only the worker knows it answered from
the kept copy, so the fix lives in two files and this gate holds both halves:

  sw.js            1. the network-first navigation branch answers a failed fetch from the cache THROUGH _keptNav
                   2. _keptNav marks the HTML <meta name="wh-kept-copy" content=...> and adds /offline-banner.js to a page
                      that does not load it
                   3. /offline-banner.js is precached (SHELL_FILES), so the script it adds is there offline
  offline-banner.js 4. it reads the mark and says "This is the copy of this page saved on this device ..." in the offline bar

    python tools/validate_kept_copy_says_so.py              # the gate
    python tools/validate_kept_copy_says_so.py --self-test  # fixtures + teeth on sw.js / offline-banner.js at 08cb9598
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_LINE = re.compile(r"(?m)(?<![:\"'`\\/])//[^\n]*$")


def _code(src: str) -> str:
    return _LINE.sub("", _BLOCK.sub(" ", src))


def check(sw: str, banner: str) -> list[str]:
    s, b = _code(sw), _code(banner)
    problems = []
    if not re.search(r"cached\s*&&\s*_req\.mode\s*===\s*'navigate'\s*\?\s*_keptNav\(cached\)", s):
        problems.append("sw.js: the network-first navigation branch does not answer a failed fetch through _keptNav - "
                        "a kept copy would be served unmarked")
    m = re.search(r"const\s+_keptNav\s*=(.*?)\n};", s, re.S)
    body = m.group(1) if m else ""
    if 'name="wh-kept-copy"' not in body:
        problems.append("sw.js: _keptNav does not mark the HTML with <meta name=\"wh-kept-copy\">")
    if "/offline-banner.js" not in body:
        problems.append("sw.js: _keptNav does not add /offline-banner.js to a page that lacks it - pages without the bar "
                        "would stay silent")
    shell = re.search(r"const\s+SHELL_FILES\s*=\s*\[(.*?)\];", s, re.S)
    if not shell or "'/offline-banner.js'" not in shell.group(1):
        problems.append("sw.js: /offline-banner.js is not precached, so the script _keptNav adds is missing offline")
    if 'meta[name="wh-kept-copy"]' not in b:
        problems.append("offline-banner.js: the bar never reads the worker's wh-kept-copy mark")
    if "copy of this page saved on this device" not in b:
        problems.append("offline-banner.js: no sentence says this is the copy of the page saved on this device")
    return problems


def main() -> int:
    sw = (ROOT / "sw.js").read_text(encoding="utf-8", errors="replace")
    banner = (ROOT / "offline-banner.js").read_text(encoding="utf-8", errors="replace")
    problems = check(sw, banner)
    if problems:
        for p in problems:
            print(f"FAIL kept-copy-says-so: {p}")
        return 1
    print("PASS kept-copy-says-so - a navigation answered from the kept copy is marked by the worker and the offline bar "
          "says it is the copy saved on this device, with when; the bar's script is precached")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    sw = ("const SHELL_FILES = [\n  '/index.html',\n  '/offline-banner.js',\n];\n"
          "const _keptNav = (res) => {\n  const mark = '<meta name=\"wh-kept-copy\" content=\"' + at + '\">'"
          " + '<script src=\"/offline-banner.js\" defer></script>';\n};\n"
          "x.catch(() => caches.match(_req).then(cached => (cached && _req.mode === 'navigate' ? _keptNav(cached) : cached)))")
    banner = ("var m = document.querySelector('meta[name=\"wh-kept-copy\"]');\n"
              "return 'You are offline. This is the copy of this page saved on this device ' + when;")
    t("the fixed pair passes", check(sw, banner) == [])
    t("a branch that hands back the cached copy unmarked fails",
      any("_keptNav" in p for p in check(sw.replace("_keptNav(cached)", "_forNav(cached)"), banner)))
    t("a mark without the added script fails",
      any("/offline-banner.js to a page" in p for p in check(sw.replace("'<script src=\"/offline-banner.js\" defer></script>'", "''"), banner)))
    t("a bar that does not read the mark fails",
      any("never reads" in p for p in check(sw, banner.replace('meta[name="wh-kept-copy"]', 'meta[name="x"]'))))
    t("a commented-out branch does not count",
      any("_keptNav" in p for p in check(sw.replace("x.catch", "// x.catch"), banner)))
    old_sw = subprocess.run(["git", "show", "08cb9598:sw.js"], cwd=ROOT, capture_output=True)
    old_b = subprocess.run(["git", "show", "08cb9598:offline-banner.js"], cwd=ROOT, capture_output=True)
    teeth = check(old_sw.stdout.decode("utf-8", "replace"), old_b.stdout.decode("utf-8", "replace")) \
        if old_sw.returncode == 0 and old_b.returncode == 0 else []
    t(f"teeth: sw.js + offline-banner.js as committed in 08cb9598 fail ({len(teeth)} problems)", len(teeth) >= 4)
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
