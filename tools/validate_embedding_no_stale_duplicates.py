#!/usr/bin/env python3
# DEEPWALK-CELL: logbook D2
"""validate_embedding_no_stale_duplicates.py -- LOCK for the embedding re-embed-on-EDIT seesaw.

ARC DI §10.5 anti-seesaw / embedding (DI-8), 2026-07-08. A source row and its embedding in the
RAG index are ONE truth in TWO representations. logbook.html edit-in-place re-calls embed-entry
on every save incl. edits, but embed-entry did a plain `.insert()` into fault_knowledge with no
unique key on the source `logbook_id` -- so editing a logbook entry ADDED a second embedding for
the same source instead of REPLACING it, leaving a STALE duplicate in the index (semantic search
could return the pre-edit text). Fixed: migration 20260708000002 adds a UNIQUE index on
fault_knowledge(logbook_id) + embed-entry now UPSERTs on it (re-embed REPLACES).

This gate is the down-ratchet: assert 0 source entries carry >1 embedding (a re-embed that did
NOT replace) AND the unique index that enforces it still exists. NULL logbook_id rows (manual
embeds) are exempt -- Postgres keeps NULLs distinct, so they legitimately don't dedupe.

Env-independent (reads the DB directly); SKIPS cleanly (exit 0) if the local DB is down.

Usage:  python tools/validate_embedding_no_stale_duplicates.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = >0 duplicate-source embeddings or the uidx is missing.
"""
import sys, json, subprocess

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# Source entries with more than one embedding (a re-embed that duplicated instead of replaced).
DUP_SQL = """
SELECT count(*) FROM (
  SELECT logbook_id FROM public.fault_knowledge
  WHERE logbook_id IS NOT NULL
  GROUP BY logbook_id HAVING count(*) > 1
) x;
"""

SAMPLE_SQL = """
SELECT logbook_id, count(*) FROM public.fault_knowledge
WHERE logbook_id IS NOT NULL
GROUP BY logbook_id HAVING count(*) > 1
ORDER BY count(*) DESC LIMIT 8;
"""

# The unique index is what makes the invariant un-violable (embed-entry upserts on it).
IDX_SQL = """
SELECT count(*) FROM pg_indexes
WHERE tablename = 'fault_knowledge' AND indexname = 'fault_knowledge_logbook_id_uidx';
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


def _int(out):
    try:
        return int((out or "").splitlines()[0].strip())
    except (ValueError, IndexError):
        return None


def analyze():
    out = psql(DUP_SQL)
    if out is None:
        return {"skipped": True, "reason": "local DB unreachable (docker supabase_db_workhive)"}
    dups = _int(out)
    idx = _int(psql(IDX_SQL))
    if dups is None:
        return {"skipped": True, "reason": f"unexpected psql output: {out[:80]!r}"}
    samples = []
    if dups > 0:
        s = psql(SAMPLE_SQL) or ""
        for line in s.splitlines():
            if "|" in line:
                sid, cnt = line.rsplit("|", 1)
                samples.append(f"{sid.strip()} x{cnt.strip()}")
    return {"skipped": False, "dup_sources": dups, "uidx_present": (idx or 0) > 0, "samples": samples}


def run_selftest():
    problems = []
    if "HAVING count(*) > 1" not in DUP_SQL or "logbook_id IS NOT NULL" not in DUP_SQL:
        problems.append("DUP_SQL must count non-null source ids carrying >1 embedding")
    live = analyze()
    if not live.get("skipped"):
        if live.get("dup_sources", 0) != 0:
            problems.append(f"live duplicate-source embeddings = {live['dup_sources']} (expected 0)")
        if not live.get("uidx_present"):
            problems.append("fault_knowledge_logbook_id_uidx MISSING -- re-embed-on-edit can duplicate again")
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
        print("embedding re-embed-on-edit (each logbook source entry must carry exactly ONE fault_knowledge embedding; a re-embed REPLACES, not duplicates)")
        if res.get("skipped"):
            print(f"  SKIP -- {res['reason']}")
        elif res["dup_sources"] == 0:
            print(f"  PASS: 0 source entries carry a duplicate/stale embedding "
                  f"(uidx {'present' if res['uidx_present'] else 'MISSING'})")
            if not res["uidx_present"]:
                print("  WARN: data is clean but fault_knowledge_logbook_id_uidx is missing -- "
                      "apply migration 20260708000002 or edits can duplicate again.")
        else:
            print(f"  FAIL: {res['dup_sources']} logbook entries carry >1 embedding (a re-embed on edit "
                  f"duplicated instead of replacing -> stale RAG hits). Top: {', '.join(res['samples'])}")
            print("  Fix: apply migration 20260708000002 (dedupe + uidx) and ensure embed-entry UPSERTs on logbook_id.")
    if res.get("skipped"):
        return 0
    return 1 if (res["dup_sources"] > 0 or not res["uidx_present"]) else 0


if __name__ == "__main__":
    sys.exit(main())
