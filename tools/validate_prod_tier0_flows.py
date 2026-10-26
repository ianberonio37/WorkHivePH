#!/usr/bin/env python3
"""validate_prod_tier0_flows.py - the runbook's Tier-0 critical paths are walked on production after a deploy (BRH-AH, 2026-10-26).

The 2026-10-24 deploy ran none of the five Tier-0 flows: they were manual and needed a production account. With the
bench (BRH-AF), tools/post_deploy_smoke.mjs --tier=flows walks them on workhiveph.com in the bench hive and undoes its
writes, then writes post_deploy_flows_report.json. This holds that report:

  - taken against production, in the bench hive (never a real tenant)
  - flow 1 sign in; flow 2 a logbook entry through the form at phone-390 AND desktop-1280, each moved to the trash;
    flow 3 an AI action that ANSWERS (a "none of my sources returned anything" deflection is a failure); flow 4 a
    parts-staging recommendation accepted twice at once with exactly one reservation and nothing left behind;
    flow 5 the production logs over the run with no 54000 / 23505 / 5xx
STATIC (the smoke, so a revert reddens even before the next run):
  - the flows tier runs only with WH_SMOKE_HIVE, undoes flow 2 through whTrash and flow 4 by deleting what it made,
    treats an assistant deflection as a failure, and never overwrites the page report
  Teeth (--self-test): the smoke as committed at 1045f447 has no flows tier.

    python tools/validate_prod_tier0_flows.py
    python tools/validate_prod_tier0_flows.py --self-test
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "post_deploy_flows_report.json"
SMOKE = "tools/post_deploy_smoke.mjs"
PROD = "https://workhiveph.com"

FACTS = {
    "the flows tier runs only in the bench hive": lambda s: re.search(r"TIER === 'flows'[\s\S]{0,200}!BENCH_HIVE", s) is not None,
    "flow 2 is undone through whTrash": lambda s: "whTrash(db, 'logbook'" in s,
    "flow 4 removes the reservation, recommendation and part": lambda s: all(
        x in s for x in ("from('parts_staged_reservations').delete()", "from('parts_staging_recommendations').delete()",
                         "from('inventory_items').delete()")),
    "an assistant deflection fails flow 3": lambda s: "none of my sources returned" in s and "deflected" in s,
    "flow 5 reads production's logs": lambda s: "analytics/endpoints/logs" in s,
    "a flows-only run never overwrites the page report": lambda s: "if (TIER !== 'flows')" in s,
}


def findings(src: str) -> list[str]:
    return [k for k, ok in FACTS.items() if not ok(src)]


def report_findings() -> tuple[list[str], str]:
    if not REPORT.exists():
        return ["no post_deploy_flows_report.json: run the smoke against production with --tier=flows"], ""
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    if (rep.get("base") or "").rstrip("/") != PROD:
        return [f"the flows report was taken against {rep.get('base') or '?'}, not {PROD}"], rep.get("at", "")
    flows = rep.get("flows") or []
    bad = []
    seen = {(f.get("flow"), f.get("viewport")) for f in flows}
    for need in [(1, None), (2, "phone-390"), (2, "desktop-1280"), (3, None), (4, None), (5, None)]:
        if need not in seen:
            bad.append(f"flow {need[0]}{' ' + need[1] if need[1] else ''} was not walked")
    for f in flows:
        if not f.get("ok"):
            why = f.get("err") or f.get("skipped") or (json.dumps(f.get("counts")) if f.get("counts") else "not ok")
            bad.append(f"flow {f.get('flow')}{' ' + f['viewport'] if f.get('viewport') else ''}: {str(why)[:140]}")
        if f.get("flow") in (2, 4) and f.get("left"):
            bad.append(f"flow {f['flow']} left {f['left']} row(s) behind in production")
    return bad, rep.get("at", "")


def self_test() -> int:
    cur = findings((ROOT / SMOKE).read_text(encoding="utf-8", errors="replace"))
    old = subprocess.run(["git", "show", f"1045f447:{SMOKE}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
    red = findings(old)
    print(f"  {'PASS' if not cur else 'FAIL'} the smoke holds every flows fact {cur or ''}")
    print(f"  {'PASS' if len(red) >= 5 else 'FAIL'} teeth: the smoke at 1045f447 fails {len(red)}/{len(FACTS)}")
    ok = not cur and len(red) >= 5
    print(("PASS" if ok else "FAIL") + " prod-tier0-flows self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    print("prod-tier0-flows (BRH-AH): the Tier-0 critical paths walked on production after a deploy")
    bad = findings((ROOT / SMOKE).read_text(encoding="utf-8", errors="replace"))
    rb, at = report_findings()
    print(f"  report {at or '?'}")
    bad += rb
    for b in bad:
        print(f"  - {b}")
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
