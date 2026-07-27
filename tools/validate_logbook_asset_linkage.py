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

# ── LG8 (2026-07-28): the OTHER lineage direction — the knowledge mirror ─────────────────────
# fault_knowledge mirrors corrective entries into the RAG corpus via logbook_id, but that column
# had NO foreign key (the table's only FK was hive_id). Deleting an entry therefore left its
# knowledge row behind, still embedded and still retrievable, citing an entry that no longer
# exists. Measured 21 dangling rows against the "529/529 valid" reading of 2026-07-12.
# Migration 20260728000001 added the FK with ON DELETE CASCADE (the knowledge is DERIVED from the
# entry, so a retracted entry must not leave a citable ghost). This asserts the constraint is still
# there and still cascades, because a later migration could drop it and nothing else would notice.
FK_SQL = """
SELECT pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'public.fault_knowledge'::regclass AND contype = 'f'
  AND conname = 'fault_knowledge_logbook_id_fkey';
"""

# ── LG8 sweep (2026-07-28): the POLYMORPHIC mirror, which cannot take a foreign key ──────────
# project_links is (link_type, link_id text), so no FK is available to protect it the way
# fault_knowledge now is. Measured during the sibling sweep: logbook / pm_completion /
# inventory_item links are all currently valid, but ALL 12 link_type='asset' rows are dangling.
# They hold legacy ids of the form 'asset-9fbe0f6f4022' and the legacy `assets` table no longer
# EXISTS (to_regclass returns null) -- the Phase 5b/5c assets->asset_nodes migration never carried
# project_links across, so those 12 project<->asset links have been permanently broken since. They
# still carry a label, so a project page renders an asset name that resolves to nothing.
#
# Not repaired here on purpose: matching by (hive_id, label) resolves only 5 of the 12 to a single
# asset; the other 7 match 2-3 assets each. Guessing the majority would look like a repair while
# leaving most of them wrong -- the same reason the auth_uid backfill skipped ambiguous names.
# So this holds the line instead: FORWARD-ONLY at the measured count, which detects any NEW
# dangling link immediately while leaving the disposition of the existing 12 to a human.
DANGLING_LINKS_SQL = """
SELECT
  (SELECT count(*) FROM project_links pl WHERE pl.link_type='logbook'
     AND NOT EXISTS (SELECT 1 FROM logbook t WHERE t.id = pl.link_id))
+ (SELECT count(*) FROM project_links pl WHERE pl.link_type='pm_completion'
     AND NOT EXISTS (SELECT 1 FROM pm_completions t WHERE t.id::text = pl.link_id))
+ (SELECT count(*) FROM project_links pl WHERE pl.link_type='inventory_item'
     AND NOT EXISTS (SELECT 1 FROM inventory_items t WHERE t.id::text = pl.link_id));
"""
# The known, pre-existing asset-link breakage is excluded from the ratchet above and asserted
# separately, so it can never silently GROW either.
DANGLING_ASSET_LINKS_SQL = """
SELECT count(*) FROM project_links pl WHERE pl.link_type='asset'
  AND NOT EXISTS (SELECT 1 FROM asset_nodes t WHERE t.id::text = pl.link_id);
"""
ASSET_LINK_BASELINE = 12

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
    fkdef = (psql(FK_SQL) or "").strip()

    def _int(sql):
        out = psql(sql)
        try:
            return int((out or "").splitlines()[0].strip())
        except (ValueError, IndexError):
            return None

    return {"skipped": False, "count": n, "samples": samples,
            "knowledge_fk": fkdef,
            "knowledge_fk_ok": bool(fkdef) and "ON DELETE CASCADE" in fkdef.upper(),
            "dangling_links": _int(DANGLING_LINKS_SQL),
            "dangling_asset_links": _int(DANGLING_ASSET_LINKS_SQL)}


def run_selftest():
    """The COUNT query must be a real EXISTS-join on (hive_id, tag) — a naive
    `machine IS NOT NULL` would false-PASS. Assert the query shape has teeth."""
    problems = []
    if "asset_node_id IS NULL" not in COUNT_SQL:
        problems.append("COUNT_SQL must filter asset_node_id IS NULL")
    if "a.tag = l.machine" not in COUNT_SQL or "a.hive_id = l.hive_id" not in COUNT_SQL:
        problems.append("COUNT_SQL must EXISTS-join asset_nodes on (hive_id, tag = machine)")
    if "fault_knowledge_logbook_id_fkey" not in FK_SQL or "pg_constraint" not in FK_SQL:
        problems.append("FK_SQL must read the real constraint definition from pg_constraint "
                        "by name -- otherwise the knowledge-mirror check has nothing to assert")
    live = analyze()
    if not live.get("skipped") and live.get("count", 0) != 0:
        problems.append(f"live count is {live['count']} (expected 0 after the backfill) -- fix-to-zero ratchet breached")
    if not live.get("skipped") and not live.get("knowledge_fk_ok"):
        problems.append("fault_knowledge.logbook_id is missing its ON DELETE CASCADE FK to logbook "
                        "(migration 20260728000001)")
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
        if not res.get("skipped"):
            if res.get("knowledge_fk_ok"):
                print("  PASS: fault_knowledge.logbook_id is FK'd to logbook ON DELETE CASCADE "
                      "(a deleted entry cannot leave a citable ghost in the RAG corpus)")
            else:
                print("  FAIL: fault_knowledge.logbook_id has no ON DELETE CASCADE foreign key to logbook "
                      f"(found: {res.get('knowledge_fk') or 'no constraint'}). A deleted entry orphans its "
                      "knowledge row, which stays embedded and retrievable citing an entry that no longer exists.")
                print("  Fix: re-apply migration 20260728000001_fault_knowledge_logbook_fk.sql.")
            dl, dal = res.get("dangling_links"), res.get("dangling_asset_links")
            if dl == 0:
                print("  PASS: 0 dangling project_links to logbook / pm_completion / inventory_item "
                      "(polymorphic link_id cannot take an FK, so this is the guard)")
            elif dl is not None:
                print(f"  FAIL: {dl} project_links point at a logbook / pm_completion / inventory_item row "
                      "that no longer exists. A project shows a link whose target is gone.")
            if dal is not None and dal > ASSET_LINK_BASELINE:
                print(f"  FAIL: dangling asset project_links GREW {ASSET_LINK_BASELINE} -> {dal}")
            elif dal is not None and dal == ASSET_LINK_BASELINE:
                print(f"  NOTE: {dal} asset project_links are dangling (known, pre-existing: the "
                      "assets->asset_nodes migration never carried project_links across, and the legacy "
                      "table is gone). Held forward-only; repair is a data decision, 7 of 12 are ambiguous.")
    if res.get("skipped"):
        return 0
    bad = (res["count"] > 0
           or not res.get("knowledge_fk_ok")
           or (res.get("dangling_links") or 0) > 0
           or (res.get("dangling_asset_links") or 0) > ASSET_LINK_BASELINE)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
