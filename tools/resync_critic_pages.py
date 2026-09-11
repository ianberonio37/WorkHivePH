#!/usr/bin/env python3
"""resync_critic_pages.py — re-point a critic row's page list at its trajectory's, for rows NOT yet walked.

★WHY (found 2026-09-11, by the guard refusing a Tier-D bank). A walk was made along the path the
TRAJECTORY declares for W3709 - "one hive's whole year", which includes project-manager and skillmatrix -
and `bank_critic_walk` refused it, because the CRITIC row for the same id declares a different path:
public-feed instead of those two. Across the registry, **332 of the 724 critic rows carrying a page list
disagree with their trajectory's**.

It is STALENESS, not a seeding bug, and the evidence says so precisely:
  * the two lists INSIDE each trajectory (`pages` and `journey.pages`) agree on 724 of 724, and
  * `critic_seed_missing.py` copies the trajectory's list faithfully at seed time.
So those critic rows were seeded from an earlier revision and the trajectories moved on afterwards.

The cost is paid by whoever walks next: reading the TRAJECTORY (the natural source - it holds the journey
definition, the archetype and the moments) produces surveys the bank then refuses, and reading the CRITIC
row walks a path the trajectory no longer claims. The trajectory is the better of the two on its face -
a hive's whole year plausibly includes its projects and its people's skills - and it is the source the
seeder already treats as authoritative, so the repair direction is critic.pages <- trajectory.pages.

★WHAT THIS REFUSES TO TOUCH, AND WHY THAT MATTERS MORE THAN THE REPAIR. A row that has already been
WALKED carries banked evidence gathered along its OLD path. Re-pointing its declaration would leave the
row claiming a journey its own findings do not cover - a silent inconsistency worse than the visible one
it replaces. So only `pending` rows are re-synced: 192 of the 332, none of which has evidence to
invalidate. The 140 already-critiqued rows keep their path AND their evidence, and are reported so the
remaining drift is a known, counted quantity rather than a surprise.

    python tools/resync_critic_pages.py              # dry run: what would change, by status
    python tools/resync_critic_pages.py --apply
    python tools/resync_critic_pages.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITIC = ROOT / "critic_registry.json"
TRAJ = ROOT / "trajectory_registry.json"

# A row is safe to re-point only while it has never been walked. Anything else owns evidence.
SAFE_STATUSES = {"pending"}


def resync(rows: list, traj_pages: dict) -> tuple[list, list]:
    """Mutate `rows`; return (repaired, skipped_because_walked). Pure, so the self-test can drive it."""
    repaired, skipped = [], []
    for r in rows:
        rid = r.get("id")
        want = traj_pages.get(rid)
        have = r.get("pages")
        if not want or not have or list(have) == list(want):
            continue
        if r.get("status") not in SAFE_STATUSES:
            skipped.append((rid, r.get("status")))
            continue
        r["pages"] = list(want)
        repaired.append(rid)
    return repaired, skipped


def _self_test() -> int:
    fails = []
    rows = [
        {"id": "A", "status": "pending", "pages": ["old.html"]},
        {"id": "B", "status": "critiqued", "pages": ["old.html"], "findings": [{"dim": "B3"}]},
        {"id": "C", "status": "pending", "pages": ["same.html"]},
    ]
    want = {"A": ["new.html"], "B": ["new.html"], "C": ["same.html"]}
    rep, skip = resync(rows, want)
    if rep != ["A"]:
        fails.append(f"only the pending, drifted row should be repaired; got {rep}")
    if rows[0]["pages"] != ["new.html"]:
        fails.append("the repaired row must take the trajectory's list")
    if rows[1]["pages"] != ["old.html"]:
        fails.append("a WALKED row must keep its path - its banked evidence covers it")
    if skip != [("B", "critiqued")]:
        fails.append(f"a walked row must be REPORTED as skipped, not silently ignored; got {skip}")
    if rows[2]["pages"] != ["same.html"]:
        fails.append("a row already in sync must not be touched")
    print("FAIL resync_critic_pages self-test - " + "; ".join(fails) if fails
          else "self-test OK: pending drift is repaired, walked rows keep their path and are reported, "
               "in-sync rows are untouched.")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    doc = json.loads(io.open(CRITIC, encoding="utf-8").read())
    rows = doc["rows"] if isinstance(doc, dict) and "rows" in doc else doc
    tdoc = json.loads(io.open(TRAJ, encoding="utf-8").read())
    tlist = tdoc["trajectories"] if isinstance(tdoc, dict) and "trajectories" in tdoc else tdoc
    traj_pages = {x.get("id"): list(x.get("pages") or []) for x in tlist}

    repaired, skipped = resync(rows, traj_pages)
    print(f"{'APPLY' if a.apply else 'DRY RUN'}: critic.pages <- trajectory.pages")
    print(f"  repaired (pending, safe)      : {len(repaired)}")
    print(f"  left alone (already WALKED)   : {len(skipped)}  by status: {dict(Counter(s for _, s in skipped))}")
    if skipped:
        print("    those rows keep their path AND their evidence - re-pointing a walked row would leave it")
        print("    claiming a journey its own findings do not cover. Remaining drift is counted, not hidden.")
    if not repaired:
        print("  nothing to repair.")
        return 0
    if not a.apply:
        print("  re-run with --apply to write critic_registry.json")
        return 0
    tmp = CRITIC.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CRITIC)
    print(f"  wrote {CRITIC.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(_self_test() if "--self-test" in sys.argv else main())
