#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BANK THE AZ FAILURE-INJECTION ROWS FROM THE SPEC'S OWN JSON RESULT
═══════════════════════════════════════════════════════════════════════════════════════════════════

`tests/failure-injection.spec.ts` makes each layer fail in turn — 500, 401, 403, timeout, partial,
offline, null_field — and asserts that the layer ABOVE degrades honestly. Those are exactly the
LM-AZ-failure-injection rows.

WHY THIS READS THE JSON REPORTER AND NOT THE CONSOLE. The first run of this spec printed
`20 passed (17.3m)` for a file containing 43 tests, with no failure lines and nothing accounting for
the other 23 — a truncated capture that would have banked 17 rows on a run I could not reconcile.
The JSON reporter emits one record per test with an explicit status, so the count is checkable
against the file's own inventory. This script REFUSES to bank anything if those two disagree.

  passed  -> green, kind: live-walk, ref naming the spec + the test title
  failed  -> owed, carrying the assertion message verbatim
  missing -> left alone. A row whose test did not run is not evidence either way.

Run:  python tools/bank_failure_injection.py                 # dry run
      python tools/bank_failure_injection.py --apply
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, ".tmp", "failure-injection.json")
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
SPEC = "tests/failure-injection.spec.ts"

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Which page each surface's honesty is a property of. An AZ row says "this SURFACE degraded honestly",
# so it rests on that surface's own page plus the shared library that renders the failure copy.
PAGES = {
    "market":      "marketplace.html",
    "market_svc":  "marketplace.html",
    "seller":      "marketplace-seller.html",
    "admin":       "platform-actions.html",
    "profile":     "marketplace-seller-profile.html",
    "community":   "community.html",
    "public-feed": "public-feed.html",
}


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def flatten(node, out):
    for s in node.get("specs", []):
        out.append(s)
    for su in node.get("suites", []):
        flatten(su, out)
    return out


def inventory():
    """What the spec file says it contains, asked of Playwright rather than assumed."""
    try:
        r = subprocess.run(
            ["node", "node_modules/@playwright/test/cli.js", "test", SPEC, "--list"],
            cwd=ROOT, capture_output=True, text=True, timeout=180)
        m = re.search(r"Total:\s*(\d+)\s*tests?", r.stdout or "")
        return int(m.group(1)) if m else None
    except Exception:
        return None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    if not os.path.exists(RESULTS):
        print(f"  {RED}FAIL{RST} — {RESULTS} not found. Run:\n"
              f"    node node_modules/@playwright/test/cli.js test {SPEC} "
              f"--workers=1 --reporter=json > .tmp/failure-injection.json")
        return 1

    data = json.load(open(RESULTS, encoding="utf-8"))
    specs = []
    for su in data.get("suites", []):
        flatten(su, specs)

    seen = {}
    for s in specs:
        for t in s.get("tests", []):
            res = (t.get("results") or [{}])[0]
            status = t.get("status") or res.get("status")
            err = ((res.get("error") or {}).get("message") or "").replace("\n", " ").strip()
            seen[s["title"]] = (status, err)

    total_declared = inventory()
    if total_declared is not None and total_declared != len(seen):
        print(f"  {RED}REFUSING TO BANK{RST} — the spec declares {total_declared} tests and this "
              f"result carries {len(seen)}. A partial capture read as a clean run once already; a "
              f"count that does not reconcile is not evidence.")
        return 1

    reg = json.load(open(REGISTRY, encoding="utf-8"))
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    today = date.today().isoformat()

    banked = failed = unmatched = 0
    notes = []
    for row in rows:
        if row.get("category") != "AZ-failure-injection":
            continue
        state, surface = row.get("state"), row.get("surface")
        title = next((t for t in seen if t.startswith(f"az_{state} · {surface}:")), None)
        if title is None:
            unmatched += 1
            continue
        status, err = seen[title]
        if status not in ("expected", "passed"):
            row["status"] = "owed"
            row["findings"] = [f"{SPEC} FAILED {today} — {title}: {err[:400]}"]
            failed += 1
            notes.append((title, err[:110]))
            continue

        page = PAGES.get(surface)
        deps = sorted({page, "utils.js"}) if page else ["utils.js"]
        row["status"] = "green"
        row["findings"] = []
        row["evidence"] = {
            "kind": "live-walk",
            # R3: a live-walk ref must NAME a surface URL from the bank — the same drift
            # bank_spec_results had (fixed there 2026-08-21, missed here until 28 rows sat owed
            # on "the spec passed but the gate rejects the evidence").
            "ref": f"{SPEC} — {today} · {row.get('url') or ''} · {title}",
            "asserts": row.get("oracle") or "",
            "checked": (f"the failure was INJECTED at the network layer and the interception was "
                        f"asserted to have fired, so a surface that never met the failure fails "
                        f"rather than passes; a healthy baseline was read first, so the failure "
                        f"wording found afterwards could not already have been on the page"),
            "depends_on": deps,
            "sha": V.sha_of(deps),
            "walked_at": today,
        }
        st, why = V.classify(row, gates, urls)
        if st == "invalid":
            row["status"] = "owed"
            row["findings"] = [f"the spec passed but the gate rejects the evidence: {why}"]
            failed += 1
        else:
            banked += 1

    print(f"{BOLD}Banking AZ rows from {SPEC}{RST}")
    print(f"  spec inventory: {total_declared} · results carried: {len(seen)} — reconciled")
    print(f"  {GREEN}{banked} banked green{RST} · {RED}{failed} owed{RST}"
          + (f" · {DIM}{unmatched} rows had no matching test{RST}" if unmatched else ""))
    for t, e in notes[:6]:
        print(f"    {RED}✗{RST} {t}\n      {DIM}{e}{RST}")

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
