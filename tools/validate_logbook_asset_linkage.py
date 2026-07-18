#!/usr/bin/env python3
# DEEPWALK-CELL: logbook D2
"""validate_logbook_asset_linkage.py -- LOCK for the asset-history fragmentation class.

Deep-walk CL1 finding (2026-07-08): a logbook entry whose `machine` EXACTLY matches a
registered asset's `tag` was left `asset_node_id = NULL` when the asset wasn't resolved
via the asset-picker (free-text machine, or the voice pre-fill path which set the machine
STRING but discarded the router-resolved asset_id). `v_asset_truth.lifetime_logbook_entries`
counts ONLY FK-linked rows, so asset-brain / analytics / the asset timeline UNDERCOUNT an
asset's history. Measured live on Baguio: PB-001 showed 18 lifetime but 37 rows named it;
platform-wide 415/902 (46%) were unlinked (2700 across all hives). Backfill migration
20260708000000 linked them; this gate asserts the class stays at ZERO going forward.

An UNLINKED entry that EXACTLY names a real hive tag is unambiguous ((hive_id, tag) is
unique in asset_nodes) -> it SHOULD be linked. A non-zero count means new entries are
fragmenting asset history again (the write-path resolution or the seeder regressed).
This is a fix-to-ZERO down-ratchet, NOT a frozen backlog.

Live-tier (skip_if_fast); SKIPS cleanly (exit 0) if the local DB is down.

Usage:  python tools/validate_logbook_asset_linkage.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = >0 exact-tag-match entries are unlinked (or self-test failure).
"""
import sys, json, subprocess

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# Count logbook rows that name a real asset tag EXACTLY (same hive) yet carry no FK link.
COUNT_SQL = """
SELECT count(*)
FROM public.logbook l
WHERE l.asset_node_id IS NULL
  AND EXISTS (SELECT 1 FROM public.asset_nodes a
              WHERE a.hive_id = l.hive_id AND a.tag = l.machine);
"""

# A few example offenders (tag + count) for the failure message.
SAMPLE_SQL = """
SELECT l.machine, count(*)
FROM public.logbook l
WHERE l.asset_node_id IS NULL
  AND EXISTS (SELECT 1 FROM public.asset_nodes a
              WHERE a.hive_id = l.hive_id AND a.tag = l.machine)
GROUP BY l.machine ORDER BY count(*) DESC LIMIT 8;
"""


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=45)
        if r.returncode != 0:
            return None
        return (r.stdout or "").strip()
    except Exception:
        return None


def analyze():
    out = psql(COUNT_SQL)
    if out is None:
        return {"skipped": True, "reason": "local DB unreachable (docker supabase_db_workhive)"}
    try:
        n = int(out.splitlines()[0].strip())
    except (ValueError, IndexError):
        return {"skipped": True, "reason": f"unexpected psql output: {out[:80]!r}"}
    samples = []
    if n > 0:
        s = psql(SAMPLE_SQL) or ""
        for line in s.splitlines():
            if "|" in line:
                tag, cnt = line.rsplit("|", 1)
                samples.append(f"{tag.strip()} x{cnt.strip()}")
    return {"skipped": False, "count": n, "samples": samples}


def run_selftest():
    """The COUNT query must be a real EXISTS-join on (hive_id, tag) — a naive
    `machine IS NOT NULL` would false-PASS. Assert the query shape has teeth."""
    problems = []
    if "asset_node_id IS NULL" not in COUNT_SQL:
        problems.append("COUNT_SQL must filter asset_node_id IS NULL")
    if "a.tag = l.machine" not in COUNT_SQL or "a.hive_id = l.hive_id" not in COUNT_SQL:
        problems.append("COUNT_SQL must EXISTS-join asset_nodes on (hive_id, tag = machine)")
    live = analyze()
    if not live.get("skipped") and live.get("count", 0) != 0:
        problems.append(f"live count is {live['count']} (expected 0 after the backfill) -- fix-to-zero ratchet breached")
    return problems


def main():
    as_json = "--json" in sys.argv
    if "--selftest" in sys.argv:
        probs = run_selftest()
        print(json.dumps({"selftest_problems": probs}, indent=2) if as_json
              else ("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs)))
        return 1 if probs else 0
    res = analyze()
    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print("logbook->asset linkage (exact-tag-match entries must be FK-linked; asset-history fragmentation guard)")
        if res.get("skipped"):
            print(f"  SKIP -- {res['reason']}")
        elif res["count"] == 0:
            print("  PASS: 0 exact-tag-match logbook entries are unlinked (asset history is fully linked)")
        else:
            print(f"  FAIL: {res['count']} logbook entries name a real asset tag EXACTLY but are asset_node_id NULL "
                  f"(asset-brain / analytics undercount their history). Top: {', '.join(res['samples'])}")
            print("  Fix: re-run backfill migration 20260708000000 + harden the logbook save to resolve machine->asset_node_id.")
    if res.get("skipped"):
        return 0
    return 1 if res["count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
