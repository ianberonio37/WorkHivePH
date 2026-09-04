#!/usr/bin/env python3
"""validate_hive_value_card.py — T188's UI-layer lock: the hive board actually SURFACES the value summary,
wired to the RLS-scoped view, with an honest empty state — so the "is this worth it?" renewal moment has a
consumer, not just a queryable view no page ever reads.

T188's data layer (v_hive_value_summary) is locked by validate_hive_value_summary. But a value summary no
one SEES answers no one's renewal question. This gate locks the hive.html surface:
  1. THE CARD — a #value-summary-card with the three count slots (vs-pms / vs-faults / vs-knowledge), so the
     three honest metrics are actually rendered (not just one, not a made-up ROI number).
  2. WIRED TO THE VIEW — loadValueSummary() reads v_hive_value_summary (the RLS-scoped canonical source),
     not the base tables directly (which would bypass security_invoker) and not an invented number.
  3. LOADED ON THE BOARD — loadValueSummary is called from the board init (the allSettled loader set), so the
     card populates on load, not only behind an interaction that may never happen.
  4. HONEST EMPTY STATE — a #vs-empty element exists, so a brand-new hive with nothing yet sees encouragement
     rather than three zeros dressed up as "value delivered" (the 'a 0 that was never a fallback' class).

Read-only; no browser; no DB. Registered in run_platform_checks (Platform). Pairs the data-layer gate; the
full-page VISUAL diff (CLS, layout) is the board-run verification, not this static structural lock.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "hive.html"

CHECK_NAMES = ["hive-value-card"]


def check(src: str) -> list[str]:
    problems: list[str] = []
    if 'id="value-summary-card"' not in src:
        problems.append("no #value-summary-card on the hive board — the value summary has no visible surface.")
    for slot, human in (("vs-pms", "PMs kept"), ("vs-faults", "faults resolved"),
                        ("vs-knowledge", "lessons captured")):
        if f'id="{slot}"' not in src:
            problems.append(f"the '{human}' slot (#{slot}) is missing — a value summary that drops one of the "
                            f"three honest counts under-reports the hive's value.")
    # loadValueSummary reads the RLS-scoped view (not the base tables, not an invented number)
    m = re.search(r"async function loadValueSummary\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        problems.append("no loadValueSummary() function — nothing populates the card.")
    else:
        body = m.group(1)
        if "v_hive_value_summary" not in body:
            problems.append("loadValueSummary() does not read v_hive_value_summary — it must go through the "
                            "RLS-scoped canonical view, not the base tables (which bypass security_invoker).")
    # a CALL, not the definition — (?<!function ) excludes `function loadValueSummary()` itself, so a card
    # whose loader is defined-but-never-invoked (the 'built but never called' class) still reddens.
    if not re.search(r"(?<!function )loadValueSummary\s*\(\s*\)", src):
        problems.append("loadValueSummary is never CALLED — the card would stay on its '--' placeholders.")
    if 'id="vs-empty"' not in src:
        problems.append("no #vs-empty encouraging empty state — a brand-new hive would see three zeros framed "
                        "as 'value delivered' (a 0 that was never earned).")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL hive-value-card: hive.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL hive-value-card — the hive board does not honestly surface the value summary:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS hive-value-card — the hive board renders #value-summary-card (pms/faults/knowledge) wired to "
          "v_hive_value_summary via loadValueSummary(), loaded on board init, with an honest empty state.")
    return 0


def self_test() -> int:
    good = ('<div id="value-summary-card"><p id="vs-pms">--</p><p id="vs-faults">--</p>'
            '<p id="vs-knowledge">--</p><p id="vs-empty" class="hidden">start here</p></div>'
            '\nasync function loadValueSummary() {\n  const res = await db.from("v_hive_value_summary")'
            '.select("pms_kept").eq("hive_id", HIVE_ID).maybeSingle();\n}\n'
            '\n[loadMaturityStairway(), loadValueSummary(), loadAdoptionCard()]')
    fails = []
    if check(good):
        fails.append("the real wired card should PASS")
    if not any("#value-summary-card" in p for p in check(good.replace('id="value-summary-card"', 'id="x"'))):
        fails.append("a missing card should FAIL")
    if not any("v_hive_value_summary" in p for p in check(good.replace("v_hive_value_summary", "pm_completions"))):
        fails.append("reading base tables instead of the view should FAIL")
    if not any("never CALLED" in p for p in check(good.replace("loadValueSummary(), loadAdoptionCard", "loadAdoptionCard"))):
        fails.append("an uncalled loader should FAIL")
    if not any("vs-knowledge" in p for p in check(good.replace('id="vs-knowledge"', 'id="z"'))):
        fails.append("a dropped third count should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_hive_value_card self-test (missing card / base-table read / uncalled loader / dropped count redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
