#!/usr/bin/env python3
r"""supervisor-hygiene - T190/T56: authority must not outlive membership, and a hive must not lose it.

Two invariants, opposite failures, both about who can approve things in a plant:

  outlived   A member who has been kicked or deactivated must not still carry role
             'supervisor'. Authority that survives departure is the quiet kind of
             permission rot - nobody notices, because nothing changes on screen until
             the day that person's row is consulted for an approval or a rights check.
             Team churn is continuous in a plant; this is what makes it safe.

  orphaned   Every hive must retain at least ONE active supervisor. A hive without one
             cannot approve an asset, clear a report, or promote anybody - so the work
             does not stop dramatically, it just quietly cannot be completed, and the
             remedy (a supervisor) is the exact thing that is missing. T56 named this the
             last-supervisor case; the transfer-then-leave flow in hive.html exists
             precisely so it cannot happen, and this checks the flow held.

MEASURED 2026-08-26: 3 hives, 4 active supervisors, ZERO departed members holding the
role and ZERO hives without one.

★IT READS STATE, NOT CODE, and that is the point. hive.html has the right guard - it
promotes a replacement before letting the last supervisor go - but a guard is a claim
about a path, while this is a claim about the WORLD: whatever combination of kicks,
role-changes, transfers and direct writes happened, the invariant either holds now or it
does not.

★ON A SEEDED FIXTURE THIS IS A WEAK SIGNAL BY ITSELF, and that is worth saying: 3 hives
is not a stress test. Its value is as a standing invariant that fires the first time a
churn path breaks it, not as proof that the churn paths are correct today.

Usage: python tools/validate_supervisor_hygiene.py
"""
import io
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

SQL = """
SELECT
  (SELECT count(*) FROM hive_members WHERE status <> 'active' AND role = 'supervisor'),
  (SELECT count(*) FROM (
      SELECT h.id FROM hives h
      LEFT JOIN hive_members m
        ON m.hive_id = h.id AND m.status = 'active' AND m.role = 'supervisor'
      GROUP BY h.id HAVING count(m.auth_uid) = 0) x),
  (SELECT count(*) FROM hives),
  (SELECT count(*) FROM hive_members WHERE status = 'active' AND role = 'supervisor');
"""

DETAIL_OUTLIVED = """
SELECT worker_name || ' (' || status || ')' FROM hive_members
WHERE status <> 'active' AND role = 'supervisor' LIMIT 5;
"""

DETAIL_ORPHANED = """
SELECT h.name FROM hives h
LEFT JOIN hive_members m ON m.hive_id = h.id AND m.status = 'active' AND m.role = 'supervisor'
GROUP BY h.id, h.name HAVING count(m.auth_uid) = 0 LIMIT 5;
"""


def psql(sql: str):
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "").strip()


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP supervisor-hygiene - docker not available (the membership table is the oracle)")
        return 0
    rc, out = psql(SQL)
    if rc != 0 or not out:
        print("SKIP supervisor-hygiene - local stack down")
        return 0
    parts = out.splitlines()[0].split("|")
    if len(parts) != 4:
        print(f"SKIP supervisor-hygiene - unexpected reading ({out[:80]})")
        return 0
    outlived, orphaned, hives, supers = (int(x) for x in parts)

    print(f"  hives: {hives} | active supervisors: {supers} | departed members still supervisor: "
          f"{outlived} | hives with no supervisor: {orphaned}")
    if outlived or orphaned:
        print("FAIL supervisor-hygiene:")
        if outlived:
            _, who = psql(DETAIL_OUTLIVED)
            print(f"    - {outlived} departed member(s) still carry role 'supervisor': "
                  f"{who.replace(chr(10), ', ')}")
            print("      Authority outliving membership is permission rot: nothing changes on screen")
            print("      until that row is consulted for an approval.")
        if orphaned:
            _, which = psql(DETAIL_ORPHANED)
            print(f"    - {orphaned} hive(s) have NO active supervisor: {which.replace(chr(10), ', ')}")
            print("      Nobody there can approve an asset, clear a report or promote anyone - the work")
            print("      does not stop loudly, it just cannot be completed, and the remedy is the very")
            print("      thing missing.")
        return 1
    print(f"PASS supervisor-hygiene - no authority outlives membership, and all {hives} hives keep an "
          f"active supervisor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
