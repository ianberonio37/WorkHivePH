#!/usr/bin/env python3
"""Every success path of an XP-earning action must name the award (T17).

★THE DEFECT THIS LOCKS. A pm_completions insert pays XP through trg_pm_achievement, and
submitCompletion() has TWO terminal success paths: one when the worker also mirrors the work to
the logbook and one when they do not. The first announced ' · +N XP'; the second was silent. Same
action, same trigger, same award, two different receipts — decided by an unrelated toggle
("also log this to the logbook"), which has nothing to do with earning.

That is the sibling-drift shape this codebase keeps meeting: a fix lands on the path someone
walked and not on the one beside it. So the rule is not "a page mentions XP somewhere" — it is
that EVERY success branch of the earning action carries the award, which is only durable if they
all call ONE helper. Two inline copies would pass a mention-count check and drift again.

★AND THE RECEIPT MUST READ THE LEDGER, NEVER RECOMPUTE IT. The trigger's rule lives in SQL
(20 XP, +20 more for a detailed entry). A JavaScript copy would be a second source of truth for a
number the worker is being shown as fact, so the helper reads achievement_xp_log back by
source_id. It is RLS-scoped to the reader's own rows, which is verified live: a row the signed-in
worker owns returns ' · +60 XP' and another worker's returns '' — so the receipt cannot leak or
overstate. A failed read returns '' as well, making the receipt quieter but never wrong.

TEETH: synthetic negatives — a silent sibling, an inline copy instead of the helper, and a helper
that invents a number instead of reading the ledger.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (page, function that performs the earning write, helper it must route every receipt through)
SURFACES = [
    ("pm-scheduler.html", "submitCompletion", "_xpNoteFor"),
]

# A BALANCED SCAN, not a regex window. The first cut used `showToast\(...[^)]*` and stopped at the
# first ')' — which lands INSIDE the message text ("...Analytics (SMRP)."), so it never saw the
# `+ await _xpNoteFor(...)` that follows and reported two already-fixed paths as silent. A matcher
# that stops at a bracket the COPY happens to contain is measuring punctuation, not code.
def success_calls(body: str) -> list:
    out = []
    for m in re.finditer(r"showToast\(", body):
        i = m.end()
        depth, j = 1, i
        while j < len(body) and depth:
            if body[j] == "(":
                depth += 1
            elif body[j] == ")":
                depth -= 1
            j += 1
        call = body[i: j - 1]
        if "✓" in call[:80]:          # a success receipt, not a refusal
            out.append(call)
    return out


# The dedup-upgrade path turns an existing DEFERRAL into a completion with an UPDATE, and
# trg_pm_achievement fires on INSERT — so no award is paid there and a receipt that claimed one
# would be inventing it. Exempted by REASON, not by silence.
EXEMPT = ["it replaces this morning"]


def body_of(src: str, fn: str) -> str:
    """The function's text, bounded by the NEXT top-level declaration rather than a char window."""
    m = re.search(rf"async function {re.escape(fn)}\s*\(", src)
    if not m:
        return ""
    rest = src[m.start():]
    nxt = re.search(r"\n(?:async )?function \w+\s*\(", rest[10:])
    return rest[: 10 + nxt.start()] if nxt else rest[:20000]


def audit(src: str, fn: str, helper: str) -> list:
    out = []
    body = body_of(src, fn)
    if not body:
        return [f"{fn}() not found - re-point this gate rather than trusting its silence"]

    # 1) the helper exists and READS the ledger rather than computing an award
    hm = re.search(rf"async function {re.escape(helper)}\s*\([^)]*\)\s*\{{(.*?)\n\}}", src, re.S)
    if not hm:
        out.append(f"{helper}() is missing - each receipt would carry its own copy of the rule")
    else:
        hbody = hm.group(1)
        if "achievement_xp_log" not in hbody:
            out.append(f"{helper}() does not read achievement_xp_log - a receipt must claim what "
                       f"the ledger holds, not a number recomputed from the trigger's rule")
        if "reversed_at" not in hbody:
            out.append(f"{helper}() does not exclude reversed awards - a reversed award would still be claimed")

    # 2) EVERY success receipt in the earning function routes through it
    hits = [h for h in success_calls(body) if not any(e in h for e in EXEMPT)]
    silent = [h for h in hits if helper not in h]
    if not hits:
        out.append(f"no success receipt found in {fn}() - the gate would be vacuous")
    for s in silent:
        out.append(f"a success path in {fn}() does not name the award: {re.sub(chr(10), ' ', s)[:74]}")
    return out


def selftest() -> int:
    src = io.open(ROOT / "pm-scheduler.html", encoding="utf-8").read()
    cases = [
        ("the real surface is clean", src, 0),
        ("a silent sibling is caught",
         src.replace("showToast('✓ PM done → PM compliance recomputed on Hive + Analytics (SMRP).'\n      + await _xpNoteFor(compData.id), 5000);",
                     "showToast('✓ PM done → PM compliance recomputed on Hive + Analytics (SMRP).', 5000);"), 1),
        ("a helper that invents a number is caught",
         re.sub(r"\.from\('achievement_xp_log'\)", ".from('nothing_real')", src), 1),
        ("a helper that counts reversed awards is caught",
         src.replace(".is('reversed_at', null)", ""), 1),
    ]
    bad = 0
    for name, s, want in cases:
        f = audit(s, "submitCompletion", "_xpNoteFor")
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {name} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    findings = []
    for page, fn, helper in SURFACES:
        p = ROOT / page
        if not p.exists():
            findings.append(f"{page} is gone - re-point this gate")
            continue
        for f in audit(io.open(p, encoding="utf-8").read(), fn, helper):
            findings.append(f"{page}: {f}")
    print("earning-moment-is-announced - every success path of an XP-earning action names the award")
    print(f"  surfaces checked: {len(SURFACES)}")
    if findings:
        print("\nFAIL - an earning moment fires invisibly on at least one path:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every success receipt routes through the ledger-reading helper.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
