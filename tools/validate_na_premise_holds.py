#!/usr/bin/env python3
"""na-premise-holds - an exclusion's stated REASON must still be true (2026-08-27, T29).

Every declared_na removes a cell from the denominator, so a false one reads exactly like coverage
([[feedback_four_exclusions_shrank_the_denominator]], [[feedback_a_skipped_partition_reads_as_a_covered_one]]).
The banks carry 105 of them and each states a reason - which means most are CHECKABLE, and nothing
was checking them. The prompt was the handoff N/A found the same day: a reasoned-looking exclusion
whose premise was false, carried for weeks in the roadmap as product work.

WHAT THIS CHECKS, matching the evidence to the CLAIM:
  "no page writes / zero writes / pure render surface"  -> the page must not call
      .insert/.update/.upsert/.delete, nor an .rpc() whose NAME carries a mutating verb.
  "renders no peso/credit/money figure"                 -> the page must render no ledger-style
      money. A currency amount inside PROSE does not count: index's anon landing cites
      "replacing it costs PHP800K to PHP2.4M" as an industry statistic, which is not a figure any
      ledger backs, and the money_matches_ledger exclusion there is correct.

*THE ORACLE MUST MATCH THE CLAIM, and the first version of this audit proves why it is worth
saying. It matched "renders no peso figure" with a regex meant for "does not write", then reported
alert-hub and analytics as unearned because they call .insert - writing has nothing to do with
rendering money ([[feedback_an_oracle_that_does_not_match_the_claim]]). It also treated any
unfamiliar .rpc() name as a write, so achievements' plainly read-only my_service_provider_ids
counted against it. Corrected, the same sweep returns 28 checkable premises and 0 false ones.

*AND IT REPORTS WHAT IT COULD NOT CHECK. A gate that silently ignores the reasons it does not
understand would claim the whole exclusion set is sound while reading a third of it, which is the
same shrunk-denominator move one level up.

Self-test: `--selftest`.
"""
import glob
import io
import json
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

WRITE_OP = re.compile(r"\.(insert|update|upsert|delete)\s*\(")
RPC = re.compile(r"\.rpc\s*\(\s*['\"]([a-z0-9_]+)['\"]", re.I)
# a name must SAY it mutates; an unfamiliar name proves nothing either way
MUTATING = re.compile(r"(^|_)(set|add|create|insert|update|delete|remove|award|grant|claim|toggle"
                      r"|mark|apply|submit|approve|reject|deduct|notify|sync|ensure|deactivate"
                      r"|assign|clear|reset|record|log)($|_)", re.I)

CLAIM_NO_WRITE = re.compile(r"no (direct )?(page )?writes|zero writes|pure render surface|read-only", re.I)
CLAIM_NO_MONEY = re.compile(r"renders no (peso|credit|money)|no (peso|credit|money) figure", re.I)

# A ledger-style money figure: a CURRENCY MARK against a template hole, or a credit balance - a
# number the page got from data and put a peso sign in front of. A currency amount sitting in a
# sentence is prose, which is why index's anon landing ("replacing it costs PHP800K to PHP2.4M",
# an industry statistic) is correctly excluded.
#
# ★toFixed(2) WAS IN THIS PATTERN AND WAS WRONG, caught before anything was recorded. Two-decimal
# formatting is not a money signal: the three callsites it fired on were an animation duration
# (index:2397 "Math.random() * 2 + 4"), a risk score (asset-hub:2187) and a statistical range
# (asset-hub:2485). It manufactured two false findings against exclusions that are entirely earned.
# The signal has to be the CURRENCY, never the precision.
LEDGER_MONEY = re.compile(r"(&#8369;|₱|PHP\s*)\s*[\$\{`]|credits?\s*(balance|held|available)", re.I)


def page_facts(page: str):
    p = ROOT / f"{page}.html"
    if not p.exists():
        return None
    src = io.open(p, encoding="utf-8", errors="replace").read()
    return {
        "ops": sorted(set(m.group(1) for m in WRITE_OP.finditer(src))),
        "wrpc": sorted(set(n for n in (m.group(1) for m in RPC.finditer(src)) if MUTATING.search(n))),
        "ledger_money": bool(LEDGER_MONEY.search(src)),
    }


def classify(reason: str):
    if CLAIM_NO_WRITE.search(reason):
        return "no-write"
    if CLAIM_NO_MONEY.search(reason):
        return "no-money"
    return None


def check_one(page: str, reason: str, facts: dict):
    """Return a problem string if the page's source CONTRADICTS the stated reason."""
    kind = classify(reason)
    if not kind or not facts:
        return None
    if kind == "no-write":
        if facts["ops"] or facts["wrpc"]:
            ev = f"ops={','.join(facts['ops']) or '-'}"
            if facts["wrpc"]:
                ev += f" rpc={','.join(facts['wrpc'][:4])}"
            return f"claims it does not write, but {ev}"
    elif kind == "no-money":
        if facts["ledger_money"]:
            return "claims it renders no money figure, but it renders a data-backed amount"
    return None


def scan():
    problems, checked, unchecked = [], 0, 0
    cache = {}
    for f in sorted(glob.glob(str(ROOT / "banks" / "*_live_mcp_bank.json"))):
        page = os.path.basename(f).replace("_live_mcp_bank.json", "")
        d = json.load(io.open(f, encoding="utf-8"))
        na = d.get("declared_na") or []
        entries = na if isinstance(na, list) else [dict(v, cell=k) for k, v in na.items()]
        for e in entries:
            if not isinstance(e, dict):
                continue
            reason = str(e.get("reason") or "")
            if not classify(reason):
                unchecked += 1
                continue
            if page not in cache:
                cache[page] = page_facts(page)
            if cache[page] is None:
                unchecked += 1
                continue
            checked += 1
            bad = check_one(page, reason, cache[page])
            if bad:
                problems.append(f"{page} :: {e.get('cell', '?')} - {bad}")
    return problems, checked, unchecked


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    writes = {"ops": ["insert"], "wrpc": [], "ledger_money": False}
    clean = {"ops": [], "wrpc": [], "ledger_money": False}
    money = {"ops": [], "wrpc": [], "ledger_money": True}

    chk("a no-write claim on a writing page fails",
        bool(check_one("p", "zero writes - a pure render surface", writes)), True)
    chk("a no-write claim on a clean page passes",
        check_one("p", "zero writes - a pure render surface", clean), None)
    chk("a mutating rpc counts as a write",
        bool(check_one("p", "no direct page writes", {"ops": [], "wrpc": ["award_xp"], "ledger_money": False})), True)
    chk("an unfamiliar rpc name is NOT assumed to write",
        check_one("p", "no direct page writes", {"ops": [], "wrpc": [], "ledger_money": False}), None)
    # the exact cross-wiring the first version of this audit shipped
    chk("a money claim is not judged by writes",
        check_one("p", "the inbox renders no peso/credit figure", writes), None)
    chk("a money claim on a ledger-rendering page fails",
        bool(check_one("p", "the inbox renders no peso/credit figure", money)), True)
    chk("an unrecognised reason is out of scope", classify("covered by the CD invariants"), None)

    problems, checked, unchecked = scan()
    chk("every checkable premise in the live banks holds", problems, [])
    print(f"\n  (live: {checked} premises checked, {unchecked} not mechanically checkable)")
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    problems, checked, unchecked = scan()
    print("an exclusion's stated reason must still be true")
    print(f"  premises checked: {checked}  ·  not mechanically checkable: {unchecked}"
          f"  ·  contradicted: {len(problems)}")
    if not problems:
        print("\n  PASS - every checkable declared_na premise holds against the page source.")
        return 0
    print("\n  FAIL - these cells are excluded from the denominator on a premise the source denies:")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
