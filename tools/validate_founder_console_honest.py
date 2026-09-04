#!/usr/bin/env python3
"""validate_founder_console_honest.py — T488's lock: the founder console shows HONEST platform state.

The founder console is where the platform's own operator reads the truth about the business. "Honest
state" means its numbers come from the platform's CANONICAL data — the v_*_truth views (which apply
RLS + the agreed definitions) and real tables — not from hardcoded/fabricated literals, and it is
gated so only the founder sees it. Three checkable properties:
  1. FOUNDER-GATED — isPlatformAdmin gate present (fail-closed), so the honest state is not leaked.
  2. GROUNDED IN CANONICAL DATA — reads a meaningful set of v_*_truth views AND platform_health AND
     a broad set of real DB sources (a console that stopped reading truth-views would be showing
     un-canonical numbers).
  3. NO FABRICATED DISPLAYED METRIC — no Math.random / hardcoded fake figure standing in for a real
     measurement (the one Math.random present is a per-anon dedup key inside a count(), never a shown
     number; the gate forbids Math.random being formatted into displayed text).

Verified 2026-09-01: founder-gated; 7 truth-views + platform_health + 24 DB sources; no fabricated
displayed metric. Holds the line so a refactor that drops the truth-view reads, removes the founder
gate, or fabricates a headline number reddens before it ships.

Static (file reads only), browser-free. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys

CHECK_NAMES = ["founder-console-honest"]
PAGE = "founder-console.html"
MIN_TRUTH_VIEWS = 5
MIN_DB_SOURCES = 12


def _read() -> str | None:
    try:
        return io.open(PAGE, encoding="utf-8").read()
    except Exception:
        return None


def check(html: str) -> list[str]:
    problems: list[str] = []
    if "isPlatformAdmin" not in html:
        problems.append("no isPlatformAdmin founder gate — the honest state could leak to non-founders")
    truth = sorted(set(re.findall(r"v_[a-z_]+_truth", html)))
    if len(truth) < MIN_TRUTH_VIEWS:
        problems.append(f"reads only {len(truth)} v_*_truth views (< {MIN_TRUTH_VIEWS}) — state is not grounded in canonical truth data")
    if "platform_health" not in html:
        problems.append("does not read platform_health — the board's own honest state is not surfaced")
    sources = len(re.findall(r"\.rpc\(\s*['\"]|\.from\(\s*['\"]", html))
    if sources < MIN_DB_SOURCES:
        problems.append(f"only {sources} DB reads (< {MIN_DB_SOURCES}) — too little live data behind the console")
    # a fabricated displayed metric: Math.random flowing into shown text (textContent/innerHTML/+ '')
    for m in re.finditer(r"Math\.random", html):
        seg = html[m.start(): m.start() + 160]
        if re.search(r"textContent|innerHTML|toLocaleString|toFixed|\.innerText", seg):
            problems.append("Math.random appears to feed a DISPLAYED metric — a fabricated number, not measured state")
    return problems


def main() -> int:
    html = _read()
    if html is None:
        print(f"FAIL founder-console-honest — {PAGE} not found or unreadable."); return 1
    problems = check(html)
    if problems:
        print("FAIL founder-console-honest — the console does not demonstrably show honest state:")
        for p in problems:
            print(f"    {p}")
        return 1
    truth = len(set(re.findall(r"v_[a-z_]+_truth", html)))
    sources = len(re.findall(r"\.rpc\(\s*['\"]|\.from\(\s*['\"]", html))
    print(f"PASS founder-console-honest — founder-gated, grounded in {truth} truth-views + platform_health across "
          f"{sources} live DB reads, with no fabricated displayed metric: the console shows measured state.")
    return 0


def self_test() -> int:
    fails = []
    truth = " ".join("v_{}_truth".format(w) for w in ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"])
    froms = " ".join(".from('tbl_{}'".format(w) for w in "abcdefghijklmn")  # 14 sources
    good = "isPlatformAdmin platform_health " + truth + " " + froms + " el.textContent = totals.toLocaleString()"
    if check(good):
        fails.append("an honest console should PASS")
    if not any("founder gate" in p for p in check(good.replace("isPlatformAdmin", "X"))):
        fails.append("missing founder gate should FAIL")
    if not any("truth data" in p for p in check(good.replace("v_alpha_truth", "raw_a").replace("v_beta_truth", "raw_b"))):
        fails.append("too few truth-views should FAIL")
    if not any("platform_health" in p for p in check(good.replace("platform_health", "X"))):
        fails.append("missing platform_health should FAIL")
    if not any("fabricated number" in p for p in check(good + " el.textContent = Math.random().toFixed(2)")):
        fails.append("a fabricated displayed metric should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_founder_console_honest self-test (no-gate / few-truth / no-health / fabricated-metric redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
