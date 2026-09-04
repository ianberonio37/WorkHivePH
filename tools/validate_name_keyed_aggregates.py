#!/usr/bin/env python3
"""name-keyed-aggregates — T127: the day two machines share a name (2026-08-26).

THE HAZARD, measured rather than imagined. Seven reliability functions group
logbook rows by the machine NAME, and none of them use asset_node_id:

  get_mtbf_by_machine     get_mttr_by_machine      get_failure_frequency
  get_downtime_pareto     get_repeat_failures      get_oee_by_machine
  compute_anomaly_signals

Names are not unique. This database already holds 24 duplicate asset names
inside a single hive — "Caterpillar 3516B" twice, "Cummins QSK60-G4" twice —
which is not a data-entry mistake but the ordinary reality of a plant that
bought two identical generators.

WHY THE NUMBERS ARE STILL RIGHT TODAY, and why that is luck rather than design:
measured on 2026-08-26, ZERO machine strings map to more than one asset_node_id,
and ZERO duplicated asset names appear in the logbook at all. Nobody has yet
logged a repair against the SECOND Caterpillar. The moment somebody does, its
failures merge into the first one's MTBF, its downtime joins the first one's
Pareto bar, and its anomalies are scored against a history that is not its own —
silently, inside numbers used to decide maintenance strategy for a machine that
might be about to fail.

WHAT THIS GATE DOES. It does not re-key those seven functions: that is a real
design change with blast radius across every analytics surface, and it deserves
to be decided rather than slipped in. It makes the failure LOUD instead of
silent, by failing the moment the hazard becomes active:

  1. no machine string in the logbook may map to more than one asset_node_id;
  2. no asset name that is duplicated inside a hive may appear as a logbook
     machine string.

Either one firing means a name-keyed aggregate has started merging two machines,
and the reliability figures on the glass have stopped being about one asset.

★A CLEAN RUN IS NOT AN ALL-CLEAR. It means the collision has not happened yet.
The 98% of logbook rows that already carry asset_node_id are what would make the
re-key cheap when it is decided.

Usage: python tools/validate_name_keyed_aggregates.py
"""
import io
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

SQL_COLLISIONS = (
    "SELECT count(*) FROM (SELECT hive_id, lower(machine) m FROM logbook "
    "WHERE machine IS NOT NULL AND asset_node_id IS NOT NULL "
    "GROUP BY 1,2 HAVING count(DISTINCT asset_node_id) > 1) a"
)
SQL_DUP_LOGGED = (
    "SELECT count(*) FROM (SELECT d.hive_id, d.n FROM "
    "(SELECT hive_id, lower(name) n FROM asset_nodes WHERE name IS NOT NULL "
    " GROUP BY 1,2 HAVING count(*) > 1) d "
    "JOIN logbook l ON l.hive_id = d.hive_id AND lower(l.machine) = d.n GROUP BY 1,2) b"
)
SQL_DUP_NAMES = (
    "SELECT count(*) FROM (SELECT hive_id, lower(name) FROM asset_nodes WHERE name IS NOT NULL "
    "GROUP BY 1,2 HAVING count(*) > 1) c"
)
SQL_FNS = (
    "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
    "WHERE n.nspname = 'public' AND p.prosrc ~* 'logbook' AND p.prosrc ~* 'group by[^;]*machine' "
    "AND p.prosrc !~* 'asset_node_id'"
)


def psql(sql: str):
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "")[:200])
    return (r.stdout or "").strip()


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP name-keyed-aggregates — docker absent (the database is the oracle)")
        return 0
    try:
        collisions = int(psql(SQL_COLLISIONS) or 0)
        dup_logged = int(psql(SQL_DUP_LOGGED) or 0)
        dup_names = int(psql(SQL_DUP_NAMES) or 0)
        name_keyed_fns = int(psql(SQL_FNS) or 0)
    except Exception as e:
        print(f"SKIP name-keyed-aggregates — database not reachable ({str(e)[:80]})")
        return 0

    print(f"  name-keyed reliability functions : {name_keyed_fns}")
    print(f"  duplicate asset names in a hive  : {dup_names}")
    print(f"  machine strings -> >1 asset      : {collisions}")
    print(f"  duplicated names seen in logbook : {dup_logged}")

    if name_keyed_fns == 0:
        print("PASS name-keyed-aggregates — no reliability function groups by machine name any more; "
              "the hazard this gate watches for cannot occur. Retire it, or re-point it if the "
              "functions were renamed rather than re-keyed.")
        return 0

    if collisions or dup_logged:
        print("FAIL name-keyed-aggregates — a name-keyed aggregate has started MERGING TWO MACHINES.")
        if collisions:
            print(f"    {collisions} machine string(s) in the logbook now map to more than one asset.")
        if dup_logged:
            print(f"    {dup_logged} duplicated asset name(s) now appear as a logbook machine string.")
        print("    MTBF, MTTR, downtime Pareto, repeat-failure and anomaly figures for those names are")
        print("    now computed over two assets' histories and presented as one machine's. Re-key the")
        print("    seven functions on asset_node_id (98% populated) with a name fallback, or split the")
        print("    colliding names — but do not leave the numbers on the glass as they are.")
        return 1

    print(f"PASS name-keyed-aggregates — {name_keyed_fns} functions still key on a non-unique name, and "
          f"{dup_names} duplicate names exist, but none has been logged against yet. Not an all-clear: "
          f"a clean run means the collision has not happened, not that it cannot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
