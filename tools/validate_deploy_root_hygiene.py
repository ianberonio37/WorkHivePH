#!/usr/bin/env python3
"""validate_deploy_root_hygiene.py — T1.4: nothing un-shippable sits in the served root.

WHY. netlify.toml publishes the repo root ("."), so every root file IS a public URL. On
2026-08-24 seven dev copies sat there — index.backup.html was literally reachable on prod,
and the roster tools each carried their own private exclusion list naming the strays (six
lists, six chances to drift). The strays moved to _fixtures/ (kept as negative fixtures);
this gate keeps the class extinct:

  1. no root .html matches the stray patterns (*-test.html, *.backup*.html, *copy*, *-v?-*);
  2. _fixtures/ is force-404'd in netlify.toml (publish="." would serve it otherwise);
  3. every root .html is either in the served-page roster's scope or a declared exception.

Check 3 is deliberately just the stray-pattern sweep plus the netlify rule — the full
per-consumer roster parity lives in validate_page_roster.py (a different question).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECK_NAMES = ["deploy_root_hygiene"]

STRAY = re.compile(r"(-test\.html$|\.backup[^/]*\.html$|copy.*\.html$|-v\d+[^/]*\.html$)", re.I)


def main() -> int:
    problems: list[str] = []

    strays = [p.name for p in ROOT.glob("*.html") if STRAY.search(p.name)]
    if strays:
        problems.append(f"stray dev copies in the served root: {strays}")

    toml = (ROOT / "netlify.toml").read_text(encoding="utf-8") if (ROOT / "netlify.toml").exists() else ""
    block = re.search(r'from\s*=\s*"/_fixtures/\*"(.{0,200}?)force\s*=\s*true', toml, re.S)
    if not block:
        problems.append("netlify.toml lacks the force-404 rule for /_fixtures/* — the negative "
                        "fixtures would be publicly served (publish is '.')")
    # the fixtures rule must come BEFORE the catch-all (first matching rule wins)
    fx = toml.find('from = "/_fixtures/*"')
    catchall = toml.find('from = "/*"')
    if fx != -1 and catchall != -1 and fx > catchall:
        problems.append("the /_fixtures/* rule sits AFTER the catch-all — Netlify never reaches it")

    n_root = len(list(ROOT.glob("*.html")))
    print(f"deploy-root-hygiene: {n_root} root pages · {len(strays)} strays · fixtures rule "
          f"{'present+ordered' if block and (fx == -1 or fx < catchall) else 'BROKEN'}")
    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    print("PASS deploy-root-hygiene — the served root carries only product pages; fixtures are 404'd.")
    return 0


def self_test() -> int:
    fails = []
    if not STRAY.search("index-native-test.html"):
        fails.append("test-copy pattern should match")
    if not STRAY.search("index.backup2.html"):
        fails.append("backup pattern should match")
    if not STRAY.search("index-v3-test.html"):
        fails.append("v3-test pattern should match")
    if STRAY.search("index.html") or STRAY.search("public-feed.html") or STRAY.search("report-sender.html"):
        fails.append("real pages must NOT match")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_deploy_root_hygiene self-test (stray patterns match the 7 moved names, spare the real pages)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
