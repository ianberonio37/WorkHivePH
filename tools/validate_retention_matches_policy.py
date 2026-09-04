#!/usr/bin/env python3
"""retention-matches-policy — T137: a promise to KEEP is as checkable as one to delete (2026-08-26).

The privacy policy says:

  "Compliance records (DOLE OSHS, ISO audit logs) are retained per WorkHive's
   audit-log policy of 10 years for general records and 15 years for incident
   investigations, even after individual account deletion…"

That is a retention PROMISE, and this trajectory has already caught the platform
making one it did not keep: the policy claimed a 90-day retention of voice
recordings when the product stores no audio at all, corrected to the truth.

MEASURED 2026-08-26 and the promise holds. Five retention crons exist and every
one purges a TECHNICAL or DERIVED table — achievement_xp_log, agent_memory,
embedding_cache, gateway_audit_log, hive_route_calls. NONE touches a
compliance-class record. hive_audit_log holds 9,019 rows with nothing scheduled
to remove them.

WHY THIS NEEDS A GATE RATHER THAN A NOTE. The agreement is currently an accident
of nobody having written the cron. Purging old logbook rows to save space is
exactly the sort of well-intentioned housekeeping somebody adds on a slow
afternoon — and the moment it lands, a legal document about DOLE OSHS and ISO
compliance becomes false, silently, with no user-visible symptom at all. The
records that would prove a plant's maintenance history in a regulatory dispute
are precisely the ones nobody notices missing until they are needed.

THE ASSERTION: no scheduled job may DELETE from a compliance-class table
(logbook, pm_completions, hive_audit_log) while the policy promises 10/15-year
retention. If the retention policy genuinely changes, change the policy text and
this list together — that is the point of pairing them.

★NOT ASSERTED: the exact ages. Nothing here is 10 years old yet, so a
"records older than 10 years still exist" check would be vacuous today and would
pass forever without measuring anything. What IS checkable now is that nothing is
scheduled to remove them.

Usage: python tools/validate_retention_matches_policy.py
"""
import glob
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# tables whose rows the privacy policy promises to retain for 10/15 years
COMPLIANCE_TABLES = {"logbook", "pm_completions", "hive_audit_log"}


def psql(sql: str):
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "")[:200])
    return [l for l in (r.stdout or "").strip().splitlines() if l.strip()]


def policy_still_promises() -> bool:
    """If the policy no longer makes the promise, this gate has nothing to protect."""
    for f in glob.glob(str(ROOT / "privacy-policy" / "**" / "*.html"), recursive=True):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if re.search(r"retained per WorkHive'?s audit-log policy of 10 years", src):
            return True
    return False


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP retention-matches-policy — docker absent (cron.job is the oracle)")
        return 0
    if not policy_still_promises():
        print("SKIP retention-matches-policy — the privacy policy no longer states the 10/15-year "
              "compliance retention. If that was deliberate, retire this gate; if the wording merely "
              "moved, re-point it at the new sentence.")
        return 0
    try:
        rows = psql("SELECT jobname || E'\\t' || replace(command, E'\\n', ' ') FROM cron.job "
                    "WHERE command ~* 'delete'")
    except Exception as e:
        print(f"SKIP retention-matches-policy — database not reachable ({str(e)[:80]})")
        return 0

    offenders = []
    for row in rows:
        parts = row.split("\t")
        if len(parts) < 2:
            continue
        name, cmd = parts[0].strip(), parts[1]
        for tbl in COMPLIANCE_TABLES:
            if re.search(rf"delete\s+from\s+(?:public\.)?{tbl}\b", cmd, re.I):
                offenders.append(f"{name} deletes from {tbl}")

    print(f"  scheduled jobs containing a delete : {len(rows)}")
    print(f"  compliance-class tables watched    : {', '.join(sorted(COMPLIANCE_TABLES))}")

    if offenders:
        print("FAIL retention-matches-policy — a scheduled job now purges records the privacy policy "
              "promises to keep for 10/15 years:")
        for o in offenders:
            print("    - " + o)
        print("    These are the records that would prove a plant's maintenance history in a DOLE OSHS")
        print("    or ISO dispute, and nobody notices them missing until they are needed. Either drop")
        print("    the job, or change the policy text and COMPLIANCE_TABLES here together.")
        return 1

    print("PASS retention-matches-policy — nothing is scheduled to delete a compliance-class record, "
          "so the 10/15-year promise is kept by the system and not only by the document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
