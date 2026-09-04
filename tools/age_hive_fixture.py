#!/usr/bin/env python3
"""T129 (2026-08-25): the aged-hive fixture — a 2-year, ~1000-entry logbook for ONE hive.

Data age changes what pages must survive: pagination at 1000, search relevance, stats bases,
export completeness, Weibull-grade failure history (T187's intelligence unlocks). This reuses
the seeder's OWN row vocabulary (problems/actions/disciplines stay platform-correct) but
widens the window to 730 days and pours the volume into one hive, tagging every row id in a
manifest so --revert removes exactly what was added.

Usage (stop any running board first — this mutates data-anchored gate subjects):
  python tools/age_hive_fixture.py --hive 084c113b-99c0-45c6-a8e8-b4b8349da46d --entries 700
  python tools/age_hive_fixture.py --revert
"""
import json
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "age_hive_fixture_manifest.json"
PSQL = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tAc"]

FAULTS = [
    ("Bearing temperature high on DE side", "Replaced 6205-2RS bearing, aligned per dial gauge", "Mechanical", "Breakdown / Corrective", 3),
    ("Belt slip audible under load", "Re-tensioned belts to OEM spec, dressed pulleys", "Mechanical", "Breakdown / Corrective", 1),
    ("Contactor chatter on start", "Replaced 32A contactor, torqued lugs", "Electrical", "Breakdown / Corrective", 2),
    ("Routine PM as scheduled", "Completed checklist per plan", "Mechanical", "Preventive Maintenance", 0),
    ("Monthly lubrication round", "Greased per OEM schedule, purged old grease", "Mechanical", "Preventive Maintenance", 0),
    ("Pre-shift walkdown", "No abnormal findings", "Mechanical", "Inspection", 0),
    ("Vibration trending check", "Recorded ISO 10816 readings; trend stable", "Mechanical", "Inspection", 0),
    ("Panel thermography scan", "No hot spots above 10C delta", "Electrical", "Inspection", 0),
    ("Seal weep at gland", "Replaced mechanical seal, flushed line", "Mechanical", "Breakdown / Corrective", 4),
    ("VFD overvoltage trip", "Checked DC bus, extended decel ramp", "Electrical", "Breakdown / Corrective", 2),
]


def q(sql: str) -> str:
    return subprocess.run(PSQL + [sql], capture_output=True, text=True, check=True).stdout.strip()


def grow(hive_id: str, entries: int):
    assets = q(f"select tag from asset_nodes where hive_id='{hive_id}' and status='approved' and tag is not null limit 40;").splitlines()
    workers = q(f"select worker_name from hive_members where hive_id='{hive_id}' and status='active';").splitlines()
    if not assets or not workers:
        print("no assets/workers found for that hive")
        return
    now = datetime.now(timezone.utc)
    ids = []
    batch = []
    for i in range(entries):
        prob, act, cat, mt, dt = random.choice(FAULTS)
        machine = random.choice(assets)
        worker = random.choice(workers)
        ts = (now - timedelta(days=random.uniform(0, 730))).isoformat()
        eid = f"aged-{now.strftime('%y%m%d')}-{i:04d}"
        ids.append(eid)
        prob_sql = prob.replace("'", "''")
        act_sql = act.replace("'", "''")
        batch.append(
            f"('{eid}','{ts}','{machine}','{mt}','{cat}','{prob_sql}','{act_sql}','Closed','{ts}','{hive_id}','{worker}',{dt})"
        )
        if len(batch) == 100 or i == entries - 1:
            q("insert into logbook (id, date, machine, maintenance_type, category, problem, action, status, closed_at, hive_id, worker_name, downtime_hours) values "
              + ",".join(batch) + ";")
            batch = []
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps({"hive_id": hive_id, "prefix": f"aged-{now.strftime('%y%m%d')}-", "count": len(ids)}, indent=2), encoding="utf-8")
    total = q(f"select count(*) from logbook where hive_id='{hive_id}';")
    print(f"aged hive {hive_id[:8]}: +{len(ids)} entries over 730d; hive logbook now {total} rows; manifest at {MANIFEST}")


def revert():
    if not MANIFEST.exists():
        print("no manifest — nothing to revert")
        return
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    q(f"delete from achievement_xp_log where source_id like '{m['prefix']}%';")
    q(f"delete from logbook where id like '{m['prefix']}%' and hive_id='{m['hive_id']}';")
    MANIFEST.unlink()
    print(f"reverted {m['count']} aged entries (and their trigger-paid XP rows)")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        hive = sys.argv[sys.argv.index("--hive") + 1] if "--hive" in sys.argv else "084c113b-99c0-45c6-a8e8-b4b8349da46d"
        n = int(sys.argv[sys.argv.index("--entries") + 1]) if "--entries" in sys.argv else 700
        grow(hive, n)
