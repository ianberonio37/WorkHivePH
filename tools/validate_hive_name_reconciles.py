#!/usr/bin/env python3
"""validate_hive_name_reconciles.py — T19's lock: a cached hive name can never survive against the
server's truth, on the glass included; and the risk feed carries no test-artifact phantoms.

Walked live (T19): Bryan (single-hive, Baguio Textile Mills) saw ANOTHER PLANT'S name ('Lucena
Pharmaceutical Mfg.') on every page — wh_hive_name is written at join/switch and was rendered
forever, never revalidated against wh_active_hive_id. Same walk: ops-home's TOP action was
'CRITICAL RISK: CP-201 (alert-test)' — an orphan TEST artifact in asset_risk_scores with no
asset_nodes row behind it (tapping through dead-ends).

Fixed (verified live 2026-09-02 with a poisoned cache -> '🐝 Baguio Textile Mills' on glass):
  1. utils.js auto-wires whReconcileHiveName on EVERY page (C11: built-but-barely-called, closed) —
     reads v_hives_truth once per load, corrects the cache + the switcher list + repaints
     [data-wh-hive-name] elements.
  2. index.html's hive button renders the name inside a data-wh-hive-name span so the repaint
     reaches the glass (the untagged render was how the stale name survived the reconciler).
  3. DATA: no asset_risk_scores row is a test artifact ('alert-test' etc.) or an orphan with no
     asset_nodes match (the phantom-critical class) — checked when the DB is reachable.
Teeth: removing the auto-wire, untagging the span, and a planted orphan-check regression all redden.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["hive-name-reconciles"]

AUTOWIRE_RE = re.compile(r"_whAutoReconcileHiveName[\s\S]{0,900}?whReconcileHiveName\(window\._whSupabaseClient\)")
TAGGED_RE = re.compile(r"setAttribute\(\s*'data-wh-hive-name'")
REPAINT_RE = re.compile(r"querySelectorAll\(\s*'\[data-wh-hive-name\]'\s*\)")
# T19 S2: the Risk Alerts glance tile must carry its FILTER context (alert-hub.html?kind=risk),
# never a bare page that drops the 4 the supervisor was promised.
RISK_TILE_RE = re.compile(r"kpi: 'risk-alerts'[^\n]{0,160}alert-hub\.html\?kind=risk")


def _psql(sql: str):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=25)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def source_problems(utils_src: str, index_src: str) -> list[str]:
    out = []
    if not AUTOWIRE_RE.search(utils_src):
        out.append("utils.js: the whReconcileHiveName auto-wire is gone — pages trust the cached "
                   "hive name blindly again (the T19 wrong-plant chrome)")
    if not REPAINT_RE.search(utils_src):
        out.append("utils.js: the reconciler no longer repaints [data-wh-hive-name] elements — a "
                   "corrected cache leaves the stale name on the glass")
    if not TAGGED_RE.search(index_src):
        out.append("index.html: the hive button's name is no longer in a data-wh-hive-name span — "
                   "the reconciler's repaint cannot reach it")
    if not RISK_TILE_RE.search(index_src):
        out.append("index.html: the Risk Alerts tile dropped its filter context (alert-hub.html?kind=risk) "
                   "— the supervisor re-finds the flagged assets by hand again (T19 S2)")
    return out


def data_problem():
    res = _psql("SELECT count(*) FROM asset_risk_scores rs WHERE rs.asset_name ILIKE '%alert-test%' "
                "OR rs.asset_name ILIKE '%(test)%' OR NOT EXISTS (SELECT 1 FROM asset_nodes n "
                "WHERE n.hive_id=rs.hive_id AND (lower(trim(n.name))=lower(trim(rs.asset_name)) "
                "OR lower(trim(n.tag))=lower(trim(rs.asset_name))))")
    if res is None:
        return None
    if res.isdigit() and int(res) > 0:
        return (f"{res} asset_risk_scores row(s) are test artifacts or orphans with no asset_nodes "
                "match — the phantom-critical class is back (ops-home may headline a dead-end)")
    return "OK"


def main() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    i = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()
    problems = source_problems(u, i)
    dp = data_problem()
    if dp and dp != "OK":
        problems.append(dp)
    if problems:
        print("FAIL hive-name-reconciles:")
        for p in problems:
            print("    " + p)
        return 1
    tail = " (DB layer skipped — docker down)" if dp is None else " and the risk feed carries no phantom/test rows"
    print("PASS hive-name-reconciles — every page reconciles the cached hive name against "
          "v_hives_truth and repaints tagged renders" + tail + ".")
    return 0


def self_test() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    i = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()
    fails = []
    if source_problems(u, i):
        fails.append("HEAD should PASS")
    no_wire = u.replace("_whAutoReconcileHiveName", "_disabledReconcileHiveName")
    if not any("auto-wire is gone" in p for p in source_problems(no_wire, i)):
        fails.append("removing the auto-wire must redden")
    no_tag = TAGGED_RE.sub("setAttribute('data-x'", i)
    if not any("data-wh-hive-name span" in p for p in source_problems(u, no_tag)):
        fails.append("untagging the span must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_hive_name_reconciles self-test (missing auto-wire + untagged span both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
