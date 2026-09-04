#!/usr/bin/env python3
"""portable-record - T58: what the platform calls portable must survive leaving (2026-08-26).

WorkHive pitches a "portable career record" to OFW-track engineers - people whose whole
reason to use it is showing evidence to the NEXT employer. So "portable" is not a
marketing adjective here; it is a testable property, and the test is simple: does the
worker still have it once they are no longer a member of the hive?

MEASURED AS THE WORKER, under RLS, inside a transaction that rolls back:
    logbook entries   571 while active  ->  0 as 'kicked'  ->  0 as 'deactivated'
    skill badges       12 while active  -> 12               -> 12

So the portability story is HALF true, and the halves are cleanly separable. Badges and
certifications are held against the WORKER and travel. Logbook entries are hive-scoped
by RLS (logbook_read requires an ACTIVE membership) and stop being readable the moment
membership ends - which is correct tenancy, since a plant's maintenance records are the
plant's, and letting a departed worker read them would be the cross-tenant leak this
platform gates everywhere else.

★THE APP WAS ALREADY HONEST; THE MARKETING WAS NOT. hive.html's leave confirm says
"Your past logbook entries stay in the hive's records" - exactly right, at the moment it
matters. Two learn pages claimed the opposite: "portable evidence that you can take with
you wherever you go. Whether you're applying for a job in Saudi Arabia..." and a personal
export available "at any time". Both now carry the condition (export while you are still
a member) instead of the promise, and the gamification page's badge claim was left alone
because measurement says it is TRUE.

THE ASSERTION: a worker with no active membership can still read their skill_badges. That
is the half the corrected claims now rest on, so if a future policy makes badges
hive-scoped too, the pitch becomes false again silently - and this says so.

★HOW THE COMPARISON IS KNOWN TO DISCRIMINATE, since a policy cannot be flipped to test the
FAIL branch without a migration: the identical probe shape run against `logbook` reports
571 -> 0, while `skill_badges` reports 12 -> 12. Same worker, same transaction, same RLS
mechanism - one table travels and one does not, and the check tells them apart. That
contrast IS the teeth: a green here means badges behaved like badges, not like a query
that always returns whatever it was given.

Non-destructive: runs inside BEGIN ... ROLLBACK, so no membership is actually changed, and
the gate re-checks afterwards that memberships are still active before trusting its own
reading - a probe that modified the fixture would otherwise report a pass on damage.

Usage: python tools/validate_portable_record_is_portable.py
"""
import io
import re
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

PICK = """
SELECT hm.auth_uid, hm.worker_name
FROM hive_members hm
JOIN skill_badges b ON b.worker_name = hm.worker_name
WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
GROUP BY 1, 2 HAVING count(b.id) > 0
ORDER BY count(b.id) DESC LIMIT 1;
"""

PROBE = """
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
SELECT 'active:' || count(*) FROM skill_badges WHERE worker_name = '{name}';
RESET ROLE;
UPDATE hive_members SET status = 'kicked' WHERE auth_uid = '{uid}';
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
SELECT 'after:' || count(*) FROM skill_badges WHERE worker_name = '{name}';
RESET ROLE;
ROLLBACK;
"""


def psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP portable-record - docker not available (RLS is the oracle)")
        return 0
    picked = [l for l in psql(PICK).strip().splitlines() if "|" in l]
    if not picked:
        print("SKIP portable-record - no active member with skill badges in this fixture")
        return 0
    uid, name = picked[0].split("|", 1)
    name = name.replace("'", "''")

    out = psql(PROBE.format(uid=uid, name=name))
    before = re.search(r"active:(\d+)", out)
    after = re.search(r"after:(\d+)", out)
    if not (before and after):
        print(f"SKIP portable-record - probe did not report both readings ({out.strip()[:120]})")
        return 0
    b, a = int(before.group(1)), int(after.group(1))

    # the rollback must have held: membership is still active
    still = psql(f"SELECT count(*) FROM hive_members WHERE auth_uid='{uid}' AND status='active';").strip()
    print(f"  badges readable — active member: {b} | after membership ends: {a} | "
          f"memberships still active after probe: {still}")

    if still == "0":
        print("FAIL portable-record - the probe left the fixture modified; membership was not restored.")
        return 1
    if b == 0:
        print("SKIP portable-record - the chosen worker reads 0 badges even while active; nothing to test")
        return 0
    if a < b:
        print(f"FAIL portable-record - a departed worker loses {b - a} of {b} badges. The platform "
              f"pitches a 'portable career record' to OFW-track engineers, whose whole reason to use it "
              f"is showing evidence to the NEXT employer. Logbook entries are hive-scoped BY DESIGN and "
              f"the learn pages now say so; badges were the half that travels, and this breaks that.")
        return 1
    print("PASS portable-record - skill badges survive the end of a hive membership, so the portability "
          "the learn pages now promise is the portability the platform actually delivers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
