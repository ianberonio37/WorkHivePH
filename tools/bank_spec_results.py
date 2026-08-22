#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BANK REGISTRY ROWS FROM A PLAYWRIGHT SPEC'S JSON RESULT — one family at a time
═══════════════════════════════════════════════════════════════════════════════════════════════════

Three specs each settle a family of behavioural claims that no structural probe may satisfy:

  BJ-ux-journey        tests/ux-journeys.spec.ts           does the flow ADVANCE, and survive leaving?
  BC-ufai-F            tests/effect-and-agreement.spec.ts  did the effect land in the DB, and agree?
  BC-ufai-F (counts)   tests/surface-numbers.spec.ts       does each number equal its own truth query?

Rather than a bespoke script per spec, each family declares how to find its test: a title prefix
built from the row's own `state` and `surface`. A row whose test is absent from the result is left
alone — silence is not evidence — and a row whose test failed is written owed with the assertion
message, because a family does not get to bank on its siblings' passes.

Every write is re-read by the gate's own classify() before it is kept, so this cannot introduce a
green the gate would reject.

Run:  python tools/bank_spec_results.py --family BJ                 # dry run
      python tools/bank_spec_results.py --family BJ --apply
      python tools/bank_spec_results.py --family all --apply
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
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

PAGES = {
    "market": "marketplace.html", "market_svc": "marketplace.html",
    "seller": "marketplace-seller.html", "admin": "platform-actions.html",
    "profile": "marketplace-seller-profile.html", "community": "community.html",
    "public-feed": "public-feed.html",
}

# family -> how to run it, where its result lands, and how a ROW finds its TEST.
FAMILIES = {
    "BJ": {
        "category": "BJ-ux-journey",
        "spec": "tests/ux-journeys.spec.ts",
        "json": ".tmp/ux-journeys.json",
        # journey_first_run_to_value · market: ...
        "title": lambda r: f"journey_{r.get('state')} · {r.get('surface')}:",
        "states": {"first_run_to_value", "repeat_visit", "cross_surface_handoff", "abandon_resume"},
    },
    "BC": {
        "category": "BC-ufai-F",
        "spec": "tests/effect-and-agreement.spec.ts",
        "json": ".tmp/effect-and-agreement.json",
        # bc_effect_in_db + effect_visible · seller: ...   /   bc_idempotent_repeat · seller: ...
        "title": lambda r: f"bc_{r.get('state')}",
        "states": {"effect_in_db", "effect_visible", "idempotent_repeat", "cross_surface_agreement"},
    },
    "BCN": {
        "category": "BC-ufai-F",
        "spec": "tests/surface-numbers.spec.ts",
        "json": ".tmp/surface-numbers.json",
        # surface_numbers · market: every visible number matches its source of truth
        "title": lambda r: f"surface_numbers · {r.get('surface')}:",
        "states": {"count_matches_source"},
    },
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


def declared(spec_path):
    try:
        r = subprocess.run(["node", "node_modules/@playwright/test/cli.js", "test", spec_path, "--list"],
                           cwd=ROOT, capture_output=True, text=True, timeout=180)
        m = re.search(r"Total:\s*(\d+)\s*tests?", r.stdout or "")
        return int(m.group(1)) if m else None
    except Exception:
        return None


def load(path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return None
    data = json.load(open(p, encoding="utf-8"))
    specs = []
    for su in data.get("suites", []):
        flatten(su, specs)
    out = {}
    for s in specs:
        for t in s.get("tests", []):
            res = (t.get("results") or [{}])[0]
            status = t.get("status") or res.get("status")
            err = ((res.get("error") or {}).get("message") or "").replace("\n", " ").strip()
            out[s["title"]] = (status, err)
    return out


def run_family(key, reg, V, apply):
    cfg = FAMILIES[key]
    seen = load(cfg["json"])
    if seen is None:
        print(f"  {YEL}skipped {key}{RST} — {cfg['json']} not found. Run:\n"
              f"    node node_modules/@playwright/test/cli.js test {cfg['spec']} "
              f"--workers=1 --reporter=json > {cfg['json']}")
        return 0, 0
    n_declared = declared(cfg["spec"])
    if n_declared is not None and n_declared != len(seen):
        print(f"  {RED}REFUSING {key}{RST} — {cfg['spec']} declares {n_declared} tests, the result "
              f"carries {len(seen)}. A count that does not reconcile is not evidence.")
        return 0, 0

    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    today = date.today().isoformat()
    banked = failed = 0
    for row in rows:
        if row.get("category") != cfg["category"] or row.get("state") not in cfg["states"]:
            continue
        prefix = cfg["title"](row)
        title = next((t for t in seen if t.startswith(prefix)), None)
        if title is None:
            continue                                   # no test covers this row; leave it as it is
        status, err = seen[title]
        if status not in ("expected", "passed"):
            row["status"] = "owed"
            row["findings"] = [f"{cfg['spec']} FAILED {today} — {title}: {err[:400]}"]
            failed += 1
            continue
        page = PAGES.get(row.get("surface"))
        deps = sorted({page, "utils.js"}) if page else ["utils.js"]
        before = (row.get("status"), row.get("evidence"), row.get("findings"))
        row["status"] = "green"
        row["findings"] = []
        row["evidence"] = {
            "kind": "live-walk",
            # R3 requires a live-walk ref to NAME a surface URL from the bank — the row's own url.
            # Without it every row this banker wrote was gate-rejected ("0 green · 15 owed" while the
            # spec passed 3/3, measured 2026-08-21): the banker had drifted behind the gate's rule.
            "ref": f"{cfg['spec']} — {today} · {row.get('url') or ''} · {title}",
            "asserts": row.get("oracle") or "",
            "checked": (f"asserted in a real browser against the live stack; the spec fails rather "
                        f"than skips when its journey cannot be constructed, and reads its effects "
                        f"back with psql as postgres rather than from the screen that claims them"),
            "depends_on": deps,
            "sha": V.sha_of(deps),
            "walked_at": today,
        }
        st, why = V.classify(row, gates, urls)
        if st == "invalid":
            row["status"], row["evidence"], row["findings"] = before
            row["findings"] = [f"the spec passed but the gate rejects the evidence: {why}"]
            failed += 1
        else:
            banked += 1
    print(f"  {key:4} {cfg['category']:14} {GREEN}{banked} green{RST} · {RED}{failed} owed{RST} "
          f"{DIM}(from {len(seen)} tests){RST}")
    return banked, failed


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="all", choices=list(FAMILIES) + ["all"])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    V = _gate()
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    print(f"{BOLD}Banking from Playwright spec results{RST}")
    keys = list(FAMILIES) if a.family == "all" else [a.family]
    tot = sum(run_family(k, reg, V, a.apply)[0] for k in keys)
    if not a.apply:
        print(f"\n  {YEL}dry run — pass --apply to write{RST}")
        return 0
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    os.replace(tmp, REGISTRY)
    print(f"\n  {GREEN}written{RST} — {tot} rows banked green")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
