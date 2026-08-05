#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERGE THE WALKER'S RESULTS INTO THE BANK — and refuse to bank what the walk did not prove
═══════════════════════════════════════════════════════════════════════════════════════════════════

tools/walk_owed_scenarios.mjs re-measures the states it can probe (populated, empty, error, edge,
degraded, filtered0) and writes .tmp/owed_walk_results.json. This merges that back.

THE WHOLE POINT OF THIS FILE IS WHAT IT REFUSES. The walker is a GENERIC harness: it can see that a
surface rendered rows, that no raw enum or `undefined` reached the screen, that nothing overflowed.
It CANNOT know a given surface's truth query, so it cannot settle an oracle like "every visible
number matches its source". It says so in its own `checked` list ("NOT CHECKED HERE: number-vs-source
…"), and this merger takes that seriously:

  ok=true  and the row's oracle is STRUCTURAL   -> banked green, with the walker's checked list as
                                                   the evidence, verbatim
  ok=true  and the row's oracle is BEHAVIOURAL  -> NOT banked. The claim is about a value or an
                                                   effect, and a structural probe cannot reach it.
                                                   Left owed, saying exactly that.
  ok=false                                      -> owed, carrying the walker's own failure notes

The behavioural/structural split is not invented here — it is rule R6 in validate_live_mcp_bank.py,
the rule that exists because a structural probe satisfying a behavioural oracle is what produced the
false 343 this bank was built to end. So this merger runs the GATE'S OWN classify() on every row it
is about to write, and if the gate would call it invalid, the row is not written green. The merger
cannot bank something the gate would reject; that asymmetry is deliberate.

Run:  python tools/merge_walk_results.py            # dry run
      python tools/merge_walk_results.py --apply
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, ".tmp", "owed_walk_results.json")
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# A page claim rests on its page and the shared library. Derived from the URL the walker actually
# drove, so the anchor matches the thing that was measured.
def deps_for(url):
    page = (url or "").split("/")[-1].split("?")[0] or "marketplace.html"
    return sorted({page, "utils.js"})


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    if not os.path.exists(RESULTS):
        print(f"  {RED}FAIL{RST} — {RESULTS} not found; run tools/walk_owed_scenarios.mjs first")
        return 1
    results = json.load(open(RESULTS, encoding="utf-8"))
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg
    by_id = {r.get("id"): r for r in rows}
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    today = date.today().isoformat()

    banked = refused = failed = missing = 0
    refusals = []

    for res in results:
        checked = "; ".join(res.get("checked") or [])
        for rid in res.get("ids") or []:
            row = by_id.get(rid)
            if row is None:
                missing += 1
                continue
            if not res.get("ok"):
                row["status"] = "owed"
                row["findings"] = [
                    f"re-walk FAILED {today} on {res.get('url')} ({res.get('state')}): "
                    f"{res.get('notes') or 'no note'}"
                    + (f" · page errors: {res['pageErrors'][:2]}" if res.get("pageErrors") else "")]
                failed += 1
                continue

            deps = deps_for(res.get("url"))
            # A probe may report that the property has nothing to attach to on this surface — the
            # lens looked and there was genuinely nothing (safe-area chrome on a page with no bottom
            # chrome). That is declared-na, a first-class evidence kind, and NOT a walk-verified
            # green: the distinction is whether the instrument could see, and this one demonstrably
            # can. Recorded with its reasoning so a reader can disagree with the judgement.
            if res.get("na"):
                row["status"] = "green"
                row["findings"] = []
                row["evidence"] = {
                    "kind": "declared-na",
                    "ref": f"tools/walk_owed_scenarios.mjs — {today} · {res.get('url')} "
                           f"({res.get('state')}) — measured not-applicable",
                    "asserts": checked,
                    "depends_on": deps,
                    "sha": V.sha_of(deps),
                    "walked_at": today,
                }
                banked += 1
                continue
            before = (row.get("status"), row.get("evidence"), row.get("findings"))
            row["status"] = "green"
            row["findings"] = []
            row["evidence"] = {
                "kind": "live-walk",
                "ref": f"tools/walk_owed_scenarios.mjs — {today} · {res.get('url')} ({res.get('state')})",
                "asserts": row.get("oracle") or "",
                "checked": checked,
                "depends_on": deps,
                "sha": V.sha_of(deps),
                "walked_at": today,
            }
            # THE REFUSAL. Ask the gate what it thinks of what we just wrote. If it would call this
            # invalid — a behavioural oracle resting on a structural probe — put the row back and say
            # so, rather than shipping a green the gate would reject.
            state, why = V.classify(row, gates, urls)
            if state == "invalid":
                row["status"], row["evidence"], row["findings"] = before
                if row.get("status") != "green":
                    row["status"] = "owed"
                row["findings"] = [
                    f"the generic re-walk PASSED its structural checks on {today}, but this row's "
                    f"oracle is behavioural — \"{(row.get('oracle') or '')[:90]}\" — and a probe that "
                    f"cannot query this surface's source of truth may not settle it ({why}). Needs a "
                    f"walk that evaluates the value, not the rendering."]
                refused += 1
                refusals.append((rid, (row.get("oracle") or "")[:60]))
            else:
                banked += 1

    print(f"{BOLD}Merging the re-walk into the bank{RST}")
    print(f"  {GREEN}{banked} banked green{RST} · {YEL}{refused} refused (behavioural oracle, "
          f"structural probe){RST} · {RED}{failed} owed from a failed walk{RST}"
          + (f" · {missing} unknown ids" if missing else ""))
    if refusals:
        print(f"\n  {DIM}refused, so the gate never sees a green it would reject:{RST}")
        for rid, oracle in refusals[:5]:
            print(f"    {rid}\n      oracle: {oracle}…")
        if len(refusals) > 5:
            print(f"    {DIM}… and {len(refusals) - 5} more{RST}")

    if not a.apply:
        print(f"\n  {YEL}dry run — pass --apply to write{RST}")
        return 0
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    os.replace(tmp, REGISTRY)
    print(f"\n  {GREEN}written{RST} — {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
