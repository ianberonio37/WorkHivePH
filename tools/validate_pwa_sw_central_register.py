#!/usr/bin/env python3
"""validate_pwa_sw_central_register.py — T44's lock instrument: the service worker registers CENTRALLY from
the shell (nav-hub.js, loaded on every page) at a DERIVED root — so an installed PWA has its offline shell
on every page, and the registration path is not the hardcoded '/workhive/' that 404s in production.

T44's install-reality walk found the hole: exactly ONE root-scope serviceWorker.register existed, on
report-sender.html (a supervisor page a field worker may never open), so an installed app had no shell
precache, no offline-fallback navigation, and serviceWorker.ready hung forever on every other page. And
that one registration hardcoded '/workhive/sw.js' — the LOCAL tester prefix prod does not serve — so it
404'd exactly where it ships. Fix: nav-hub.js (the shell) registers the worker with whSwRoot() ('/workhive/'
local, '/' prod), guarded. This gate locks it so the offline shell cannot silently regress to one page or a
prod-404 path — the '_headers/prefix is prod-only behaviour' + 'declared but never wired' classes.

Assertions on nav-hub.js (each refutable — see the self-test):
  1. THE DERIVED ROOT — a whSwRoot() helper (so the scope is environment-derived, not hardcoded).
  2. CENTRAL REGISTRATION — navigator.serviceWorker.register(root + 'sw.js', { scope: root }) using that
     derived root (not a literal '/workhive/sw.js').

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "nav-hub.js"

CHECK_NAMES = ["pwa-sw-central-register"]

_WHSWROOT = re.compile(r"function\s+whSwRoot\s*\(|whSwRoot\s*=\s*function|const\s+whSwRoot\s*=")
_REGISTER_DERIVED = re.compile(r"""serviceWorker\.register\(\s*root\s*\+\s*['"]sw\.js['"]|serviceWorker\.register\(\s*whSwRoot\(\)""")
_HARDCODED = re.compile(r"""serviceWorker\.register\(\s*['"]/workhive/sw\.js['"]""")
# 3. NO PAGE REGISTERS A LITERAL PATH (2026-10-16, found by the CA1 walk). T44 made nav-hub.js the owner but left
# report-sender.html's own register('/sw.js') beside it - the same worker in production, but under the local /workhive/
# prefix a SECOND registration at another URL and scope, whose activate deleted the first one's cache. This gate read
# only nav-hub.js, so it never saw the page. Any register() in a shipped page or script must take the derived root
# (root + 'sw.js' / whSwRoot() / a variable built from it), never a quoted path.
_LITERAL = re.compile(r"""serviceWorker\.register\(\s*['"`]""")
_BLOCK_COMMENTS = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)
_LINE_COMMENTS = re.compile(r"""(?m)(?<![:"'`\\/])//[^\n]*$""")


def literal_registrations(src: str) -> int:
    return len(_LITERAL.findall(_LINE_COMMENTS.sub("", _BLOCK_COMMENTS.sub(" ", src))))


def shipped_sources() -> list[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    import deploy_payload as dp  # the deploy's own matcher: what production serves
    return sorted(f for f in dp.shipped() if f.endswith((".html", ".js")))


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not _WHSWROOT.search(src):
        problems.append("no whSwRoot() helper — the SW scope is not environment-derived (a hardcoded root "
                        "404s in prod or misses the local scope).")
    if not _REGISTER_DERIVED.search(src):
        problems.append("the shell does not register the SW with the derived root (register(root+'sw.js')) "
                        "— the offline shell is not wired centrally on every page.")
    if _HARDCODED.search(src):
        problems.append("the SW registration hardcodes '/workhive/sw.js' — the local-tester prefix prod "
                        "does not serve; it will 404 exactly where it ships.")
    return problems


def main() -> int:
    if not SHELL.exists():
        print("FAIL pwa-sw-central-register: nav-hub.js not found"); return 1
    problems = check(SHELL.read_text(encoding="utf-8", errors="replace"))
    for f in shipped_sources():
        n = literal_registrations((ROOT / f).read_text(encoding="utf-8", errors="replace"))
        if n:
            problems.append(f"{f} registers the service worker with a literal path ({n}x) - a second registration "
                            f"beside nav-hub.js's derived one wherever the path differs; use whSwRoot().")
    if problems:
        print("FAIL pwa-sw-central-register — the offline shell is not registered centrally with a derived root:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS pwa-sw-central-register — nav-hub.js registers the service worker on every page at a derived "
          "root (whSwRoot), so the offline shell works everywhere and the path does not 404 in prod; no shipped page "
          "or script registers a literal path beside it.")
    return 0


def self_test() -> int:
    fails = []
    good = "function whSwRoot(){return location.pathname.startsWith('/workhive/')?'/workhive/':'/';}\n const root=whSwRoot(); navigator.serviceWorker.register(root + 'sw.js', { scope: root });"
    if check(good):
        fails.append("the real derived-root central registration should PASS")
    if not any("whSwRoot" in p for p in check("navigator.serviceWorker.register('/sw.js');")):
        fails.append("missing whSwRoot should FAIL")
    if not any("register the SW with the derived root" in p for p in check("function whSwRoot(){return '/';} doNothing();")):
        fails.append("whSwRoot present but no register(root+...) should FAIL")
    if not any("hardcodes" in p for p in check("function whSwRoot(){return '/';} const root=whSwRoot(); navigator.serviceWorker.register('/workhive/sw.js', {scope:root});")):
        fails.append("a hardcoded /workhive/sw.js register should FAIL")
    if literal_registrations("navigator.serviceWorker.register('/sw.js').catch(() => {});") != 1:
        fails.append("a page registering a literal '/sw.js' should be counted")
    if literal_registrations("reg = await navigator.serviceWorker.register(_swRoot + 'sw.js', { scope: _swRoot });"
                             "// navigator.serviceWorker.register('/old.js')") != 0:
        fails.append("a derived-root register and a commented literal should not be counted")
    import subprocess
    old = subprocess.run(["git", "show", "683ecea5:report-sender.html"], cwd=ROOT, capture_output=True)
    if old.returncode != 0 or literal_registrations(old.stdout.decode("utf-8", "replace")) != 1:
        fails.append("teeth: report-sender.html as shipped in 683ecea5 (its own register('/sw.js')) should be caught")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_pwa_sw_central_register self-test (missing whSwRoot / no-derived-register / hardcoded-path / a page's literal register() redden; teeth on report-sender 683ecea5)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
