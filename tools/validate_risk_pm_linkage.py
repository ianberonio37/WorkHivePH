#!/usr/bin/env python3
"""validate_risk_pm_linkage.py — T26's lock: the risk engine's PM-overdue factor must read the
asset's REAL PM data, never emit 'No PM data linked' from a join miss.

Walked live (T26): asset-hub PB-001 showed the risk factor 'pm overdue +15% - No PM data linked to
this machine; assumed medium overdue' on the SAME screen whose header counted 'PM COMPLETED 14' —
a self-contradiction, and the risk score inflated +15% for a FALSE reason (cry-wolf). Root: the
batch-risk-scoring engine keyed pm_assets by EXACT-CASE asset_name while logbook's machine string
is usually the TAG ('PB-001') vs the display name ('Caterpillar 3516B'), AND last_anchor_date was
never SELECTED, so even a hit fell to the 'No PM data linked' default. Fixed 2026-09-02 and the
engine re-ran: PB-001 now reads 'Last PM anchor 60 days ago; partial overdue' (real data).

Lock (two layers):
  1. SOURCE (batch-risk-scoring/index.ts): last_anchor_date is selected; pmByName is keyed by BOTH
     normalized name and tag; the factor lookup uses _pmNorm(machine).
  2. DATA (when DB reachable): no live v_risk_truth row emits 'No PM data linked' for an asset that
     actually has pm_completions — the exact contradiction the walk found.
Teeth plant each pre-fix shape; DB layer skips cleanly when docker is down.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "batch-risk-scoring" / "index.ts"
CHECK_NAMES = ["risk-pm-linkage"]

SELECT_ANCHOR_RE = re.compile(r"\.select\(\s*[\"'][^\"']*last_anchor_date[^\"']*[\"']")
NAME_KEY_RE = re.compile(r"pmByName\[_pmNorm\(\s*pa\.asset_name\s*\)\]\s*=")
TAG_KEY_RE = re.compile(r"pmByName\[_pmNorm\([^\]]*tag_id[^\]]*\)\]\s*=")
LOOKUP_RE = re.compile(r"pmByName\[_pmNorm\(\s*machine\s*\)\]")
# T19 S2 severity-voice: asset-hub's verdict must LEAD with active critical/high risk (one
# narrative with ops-home's 'CRITICAL RISK - inspect now', never 'mostly healthy' over a 91% risk).
VERDICT_RE = re.compile(r"_riskHot > 0[\s\S]{0,300}?critical or high predicted risk")


def _psql(sql: str):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=25)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def source_problems(src: str) -> list[str]:
    out = []
    if not SELECT_ANCHOR_RE.search(src):
        out.append("batch-risk-scoring: pm_assets select no longer fetches last_anchor_date — every "
                   "asset falls to the 'No PM data linked' default (the T26 false factor)")
    if not (NAME_KEY_RE.search(src) and TAG_KEY_RE.search(src)):
        out.append("batch-risk-scoring: pmByName is no longer keyed by BOTH name and tag — a "
                   "tag-vs-name mismatch silently misses PM data (the join miss T26 found)")
    if not LOOKUP_RE.search(src):
        out.append("batch-risk-scoring: the pm-overdue factor no longer looks up by _pmNorm(machine)")
    try:
        ah = io.open(ROOT / "asset-hub.html", encoding="utf-8", errors="replace").read()
        if not VERDICT_RE.search(ah):
            out.append("asset-hub.html: the verdict no longer leads with active critical/high risk — "
                       "'mostly healthy' can sit over a 91% predicted risk again (T19 S2 voice mismatch)")
    except OSError:
        out.append("asset-hub.html unreadable for the verdict check")
    return out


def data_problem() -> str | None:
    # any asset with real pm_completions whose latest risk row still claims 'No PM data linked'
    sql = ("SELECT count(*) FROM v_risk_truth r WHERE r.top_factors::text ILIKE '%No PM data linked%' "
           "AND EXISTS (SELECT 1 FROM pm_completions pc JOIN pm_assets pa ON pa.id=pc.asset_id "
           "WHERE lower(trim(pa.asset_name))=lower(trim(r.asset_name)) OR lower(trim(pa.tag_id))=lower(trim(r.asset_name)))")
    res = _psql(sql)
    if res is None:
        return None  # DB down -> skip data layer
    if res.isdigit() and int(res) > 0:
        return (f"{res} live risk row(s) claim 'No PM data linked' for an asset that HAS pm_completions "
                "— the T26 self-contradiction is back in the data (re-run batch-risk-scoring)")
    return "OK"


def main() -> int:
    src = io.open(FN, encoding="utf-8", errors="replace").read()
    problems = source_problems(src)
    dp = data_problem()
    db_skipped = dp is None
    if dp and dp != "OK":
        problems.append(dp)
    if problems:
        print("FAIL risk-pm-linkage:")
        for p in problems:
            print("    " + p)
        return 1
    tail = " (DB layer skipped — docker down; source clean)" if db_skipped else " and no live risk row contradicts its PM count"
    print("PASS risk-pm-linkage — the risk engine reads real PM data by normalized name+tag" + tail + ".")
    return 0


def self_test() -> int:
    src = io.open(FN, encoding="utf-8", errors="replace").read()
    fails = []
    if source_problems(src):
        fails.append("HEAD source should PASS")
    no_anchor = SELECT_ANCHOR_RE.sub('.select("id:pm_asset_id, asset_name, tag_id, category")', src)
    if not any("last_anchor_date" in p for p in source_problems(no_anchor)):
        fails.append("removing last_anchor_date from the select must redden")
    no_tag = TAG_KEY_RE.sub("/*removed tag key*/ 0 &&", src)
    if not any("name and tag" in p for p in source_problems(no_tag)):
        fails.append("collapsing to name-only keying must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_risk_pm_linkage self-test (missing anchor-select + name-only keying both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
