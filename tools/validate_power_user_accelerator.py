#!/usr/bin/env python3
"""validate_power_user_accelerator.py — T194's lock: the power user's one real accelerator (a Ctrl/Cmd+K
global search palette) genuinely EXISTS and is reachable platform-wide.

T194 ("the power user's ceiling") found that keyboard acceleration is essentially ONE shortcut — a
Ctrl/Cmd+K global search — and, separately, that the platform once pointed supervisors at a button
that did not exist (found + fixed). The honest positive to lock is that the ONE accelerator is real
and wired everywhere a power user works, not a dead binding:
  1. nav-hub.js binds Ctrl/Cmd+K;
  2. nav-hub.js loads the search-overlay palette (so the binding actually opens something); and
  3. nav-hub.js is included platform-wide (>= 20 interactive pages), so the accelerator is reachable
     from where power users actually are — not built-but-never-wired.

Static (file reads + include census), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import subprocess
import sys

CHECK_NAMES = ["power-user-accelerator"]
MIN_PAGES = 20


def _read(path: str) -> str | None:
    try:
        return io.open(path, encoding="utf-8").read()
    except Exception:
        return None


def _page_count() -> int:
    try:
        r = subprocess.run(["git", "grep", "-l", "nav-hub.js", "--", "*.html"], capture_output=True, text=True, timeout=60)
        return len([l for l in (r.stdout or "").splitlines() if l.strip() and "_fixtures" not in l and ".bak" not in l])
    except Exception:
        return -1


def check(navhub: str | None, pages: int) -> list[str]:
    problems: list[str] = []
    if navhub is None:
        problems.append("nav-hub.js not found — the platform-wide accelerator host is missing")
        return problems
    if not re.search(r"\(\s*e?v?\.?ctrlKey\s*\|\|\s*e?v?\.?metaKey\s*\)\s*&&[^;{]{0,40}key\s*===?\s*['\"][kK]['\"]", navhub):
        problems.append("nav-hub.js does not bind Ctrl/Cmd+K — the one power-user accelerator is gone")
    if "search-overlay" not in navhub:
        problems.append("nav-hub.js does not load the search-overlay palette — Ctrl/Cmd+K opens nothing (dead binding)")
    if pages == -1:
        problems.append("could not census nav-hub.js includes (no unearned pass)")
    elif 0 <= pages < MIN_PAGES:
        problems.append(f"nav-hub.js is on only {pages} pages (< {MIN_PAGES}) — the accelerator is not reachable platform-wide")
    return problems


def main() -> int:
    navhub = _read("nav-hub.js")
    pages = _page_count()
    problems = check(navhub, pages)
    if problems:
        print("FAIL power-user-accelerator — the Ctrl/Cmd+K accelerator is not real/reachable:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS power-user-accelerator — nav-hub.js binds Ctrl/Cmd+K and lazy-loads the search-overlay palette, "
          f"and is included on {pages} pages: the power user's one real accelerator exists and is reachable platform-wide.")
    return 0


def self_test() -> int:
    good = "if ((e.ctrlKey || e.metaKey) && e.key === 'k') { import('./search-overlay.js'); }"
    fails = []
    if check(good, 36):
        fails.append("a wired accelerator on 36 pages should PASS")
    if not any("does not bind" in p for p in check("if (e.key === 'j') {}", 36)):
        fails.append("no Ctrl/Cmd+K binding should FAIL")
    if not any("opens nothing" in p for p in check("if ((e.ctrlKey||e.metaKey)&&e.key==='k'){}", 36)):
        fails.append("no search-overlay load should FAIL")
    if not any("platform-wide" in p for p in check(good, 5)):
        fails.append("too few pages should FAIL")
    if not any("missing" in p for p in check(None, 36)):
        fails.append("missing nav-hub should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_power_user_accelerator self-test (no-bind / dead-binding / too-few-pages / missing redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
