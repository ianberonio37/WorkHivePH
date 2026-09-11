#!/usr/bin/env python3
"""backfill_skill_profiles - give every active member a skills record, whatever hive they joined through.

WHY THIS EXISTS (2026-09-09). The J25 journey - new hire -> skills -> certified - reported "the chain is
empty in this hive" for three verticals, and the reason was not the journey: Dela Cruz Delivery Fleet,
Ramos Jeepney Line and Tan Delivery Vans have members and ZERO skill_profiles, while all three plant hives
have one per member. The vehicle-seed arc created its hives through a path that never called
seeders/skill_matrix.py, which only runs when a hive is first built.

It is not only a fixture gap. A driver in a fleet hive has no skills record at all, so skillmatrix.html and
achievements.html are empty for them for ever, and nothing on the platform can say what that person is
qualified to do - on a platform whose whole pitch is that it knows.

The five disciplines are CANONICAL and must match skill-content.js (Mechanical, Electrical,
Instrumentation, Facilities Management, Production Lines); the seeder's own comment warns not to invent
others, because prescriptive.py maps everything back to these five. The primary skill is chosen from the
same list the seeder uses - "Rotating Equipment" (engines) and "Hydraulics & Pneumatics" (brakes, tipping
gear) are as true of a jeepney as of a pump, which is why a vehicle hive needs no vocabulary of its own.

Deterministic, never random: the choice is a hash of the worker's name, so re-running produces the same
profile and a diff of the database is empty rather than noisy. Only members with NO profile are touched.

    python tools/backfill_skill_profiles.py --check     # report the gap, write nothing
    python tools/backfill_skill_profiles.py             # fill it
"""
import hashlib
import io
import json
import os
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
CHECK = "--check" in sys.argv

# canonical - must match skill-content.js DISCIPLINES (the seeder's own warning)
DISCIPLINES = ["Mechanical", "Electrical", "Instrumentation", "Facilities Management", "Production Lines"]
PRIMARY_SKILLS = [
    "Rotating Equipment", "MV Switchgear", "PLC Programming", "Hydraulics & Pneumatics",
    "Refrigeration & HVAC", "Welding & Fabrication", "Steam Systems",
    "Vibration Analysis", "Process Safety", "Boiler Operation",
]
# a vehicle hive's people are mechanics of a different machine, not of a different trade
VEHICLE_SKILLS = ["Rotating Equipment", "Hydraulics & Pneumatics", "Welding & Fabrication"]


def psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
        input=sql, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def seeded(name: str, pool: list) -> str:
    h = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)
    return pool[h % len(pool)]


def targets_for(name: str) -> dict:
    """Four of the five disciplines, at levels 1-5, stable for this person."""
    h = int(hashlib.sha256(("t" + name).encode("utf-8")).hexdigest(), 16)
    picked = {}
    for i, d in enumerate(DISCIPLINES):
        if len(picked) == 4:
            break
        if (h >> (i * 3)) & 1 or len(picked) + (len(DISCIPLINES) - i) <= 4:
            picked[d] = ((h >> (i * 5)) % 5) + 1
    return picked


def main() -> int:
    if not psql("SELECT 1;"):
        print("SKIP backfill-skill-profiles - local database not reachable")
        return 0

    rows = [r for r in psql(
        "SELECT m.worker_name || '|' || h.name || '|' || coalesce(m.auth_uid::text, '') "
        "FROM hive_members m JOIN hives h ON h.id = m.hive_id "
        "WHERE m.status = 'active' "
        "AND NOT EXISTS (SELECT 1 FROM skill_profiles s WHERE s.worker_name = m.worker_name) "
        "GROUP BY m.worker_name, h.name, m.auth_uid ORDER BY h.name, m.worker_name;"
    ).split("\n") if r.strip()]

    if not rows:
        print("PASS backfill-skill-profiles - every active member already has a skills record")
        return 0

    print(f"  {len(rows)} active member(s) with no skill profile:")
    for r in rows:
        name, hive = r.split("|")[0], r.split("|")[1]
        print(f"    {name:<24} {hive}")
    if CHECK:
        print("\n  --check: nothing written. Re-run without it to fill the gap.")
        return 1

    written = 0
    for r in rows:
        parts = r.split("|")
        name, hive, auth = parts[0], parts[1], (parts[2] if len(parts) > 2 else "")
        pool = VEHICLE_SKILLS if any(w in hive.lower() for w in ("fleet", "jeepney", "vans", "delivery")) else PRIMARY_SKILLS
        primary = seeded(name, pool)
        tg = json.dumps(targets_for(name)).replace("'", "''")
        auth_sql = f"'{auth}'::uuid" if auth else "NULL"
        out = psql(
            "INSERT INTO skill_profiles (worker_name, primary_skill, targets, auth_uid) VALUES ("
            f"'{name.replace(chr(39), chr(39) * 2)}', '{primary}', '{tg}'::jsonb, {auth_sql}) "
            "ON CONFLICT DO NOTHING RETURNING worker_name;")
        if out:
            written += 1
            print(f"    + {name:<24} {primary}")

    left = psql("SELECT count(*) FROM hive_members m WHERE m.status = 'active' "
                "AND NOT EXISTS (SELECT 1 FROM skill_profiles s WHERE s.worker_name = m.worker_name);")
    print(f"\nOK backfill-skill-profiles - wrote {written} profile(s); {left} active member(s) still without one. "
          "skillmatrix and achievements now have something to say about every person on the platform.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
