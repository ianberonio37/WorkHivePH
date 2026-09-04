#!/usr/bin/env python3
"""T61 (2026-08-25): the seeded-scale fixture — grow ONE hive's roster to N members.

The people-surfaces (roster, standings, presence, assignee pickers, notification fan-out)
behave differently at 20 members than at 3, and the seeder ships ~5/hive. This grows a hive
with REALISTIC named members (layout truth needs real name lengths, not WH-FIXTURE-01) while
keeping every added row tagged in a manifest so --revert removes exactly what was added.

Membership + profile rows only (no auth users): scale walks READ these surfaces; sign-in-as
is not needed for layout/fan-out truth. A walk that must act as a member uses the core 3.

Usage:
  python tools/grow_hive_fixture.py --hive 084c113b-99c0-45c6-a8e8-b4b8349da46d --to 20
  python tools/grow_hive_fixture.py --revert
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "grow_hive_fixture_manifest.json"
PSQL = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tAc"]

NAMES = [
    "Ramon Villanueva", "Corazon Bautista", "Danilo Reyes", "Marites Ocampo",
    "Ernesto Salazar", "Luzviminda Cruz", "Rogelio Mendoza", "Teresita Aquino",
    "Federico Santos", "Remedios Garcia", "Arnel Domingo", "Josefina Ramos",
    "Crisanto Padilla", "Imelda Navarro", "Benjamin Torres", "Rosario Villegas",
    "Eduardo Manalo", "Gregoria Castillo", "Rodolfo Pascual", "Milagros Ferrer",
]


def q(sql: str) -> str:
    return subprocess.run(PSQL + [sql], capture_output=True, text=True, check=True).stdout.strip()


def grow(hive_id: str, target: int):
    current = int(q(f"select count(*) from hive_members where hive_id='{hive_id}' and status='active';"))
    need = target - current
    if need <= 0:
        print(f"hive already has {current} active members (target {target}) — nothing to add")
        return
    existing = set(q(f"select worker_name from hive_members where hive_id='{hive_id}';").splitlines())
    pool = [n for n in NAMES if n not in existing][:need]
    if len(pool) < need:
        print(f"name pool exhausted: adding {len(pool)} of {need}")
    added = []
    for name in pool:
        q("insert into hive_members (hive_id, worker_name, role, status) "
          f"values ('{hive_id}', '{name}', 'worker', 'active');")
        added.append(name)
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps({"hive_id": hive_id, "added": added}, indent=2), encoding="utf-8")
    print(f"grew hive {hive_id[:8]} {current} -> {current + len(added)} active members; manifest at {MANIFEST}")


def revert():
    if not MANIFEST.exists():
        print("no manifest — nothing to revert")
        return
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name in m["added"]:
        q(f"delete from hive_members where hive_id='{m['hive_id']}' and worker_name='{name}' and role='worker';")
    MANIFEST.unlink()
    print(f"reverted {len(m['added'])} fixture members from hive {m['hive_id'][:8]}")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        hive = sys.argv[sys.argv.index("--hive") + 1] if "--hive" in sys.argv else "084c113b-99c0-45c6-a8e8-b4b8349da46d"
        to = int(sys.argv[sys.argv.index("--to") + 1]) if "--to" in sys.argv else 20
        grow(hive, to)
