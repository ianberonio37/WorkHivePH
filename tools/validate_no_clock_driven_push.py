#!/usr/bin/env python3
"""no-clock-driven-push — T109: why this platform needs no quiet hours YET (2026-08-26).

T109 asks whether notifications respect human time. The honest answer measured
on 2026-08-25 was that no quiet-hours machinery exists anywhere — and, crucially,
that nothing CLAIMS it, so the platform is silent rather than lying. This gate
turns that from an observation into a guarded property, because the reason the
absence is currently harmless is structural and easy to lose:

  EVERY push producer is EVENT-DRIVEN. All of them fire from a person acting — a
  mention, a reply, a best answer, an assignment, an approval decision, a report,
  a submission, a service completion. NOT ONE is clock-driven. A phone therefore
  cannot buzz at 3am unless somebody in that hive acted at 3am, which on a
  round-the-clock plant is a night shift and is legitimate news.

That is what makes "no quiet hours" defensible today. The day a scheduled digest,
a nightly summary, or a cron-driven reminder ships, it stops being defensible
immediately: a clock-driven push CHOOSES its own hour, and choosing 3am for
someone is exactly what quiet hours exist to prevent.

THE ASSERTION. No cron job may invoke anything that enqueues a user push —
neither a database function that calls enqueue_user_push (checked transitively,
one hop, since fanout_completion_push is itself called by a trigger) nor an edge
function that does. The drain is exempt BY NAME and for a reason: notify-push
DELIVERS what was already enqueued, it does not decide anything, and it must run
every minute or nothing arrives at all.

★THIS GATE IS MEANT TO FIRE ONE DAY. When someone builds the digest T106 records
as a scoped future decision, this goes red — and the red is the point: it forces
the quiet-hours question to be answered before the first scheduled push reaches a
phone, rather than after. The fix is then not to delete the gate but to add the
quiet-window logic and record it here.

Usage: python tools/validate_no_clock_driven_push.py
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

# The delivery drain: it sends what is already queued and decides nothing. It MUST run on a clock.
DRAIN_EXEMPT = {"notify-push", "service-outbox-drain-1min"}


def psql(sql: str):
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "")[:200])
    return [l for l in (r.stdout or "").strip().splitlines() if l.strip()]


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP no-clock-driven-push — docker absent (cron.job and pg_proc are the oracle)")
        return 0
    try:
        # direct producers, then one hop out: anything that calls a producer is also a producer
        direct = set(psql(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.prosrc ~ 'enqueue_user_push' AND p.proname <> 'enqueue_user_push'"))
        producers = set(direct)
        if direct:
            pat = "|".join(sorted(re.escape(x) for x in direct))
            producers |= set(psql(
                "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                f"WHERE n.nspname = 'public' AND p.prosrc ~ '{pat}' AND p.proname <> 'enqueue_user_push'"))
        jobs = psql("SELECT jobname || E'\\t' || schedule || E'\\t' || replace(command, E'\\n', ' ') FROM cron.job")
    except Exception as e:
        print(f"SKIP no-clock-driven-push — database not reachable ({str(e)[:80]})")
        return 0

    # edge functions that push, from source
    edge_pushers = {Path(f).parent.name for f in glob.glob(str(ROOT / "supabase" / "functions" / "*" / "index.ts"))
                    if re.search(r"enqueue_user_push|notify-push",
                                 io.open(f, encoding="utf-8", errors="replace").read())}

    print(f"  db push producers : {len(producers)} ({', '.join(sorted(producers))})")
    print(f"  edge push callers : {', '.join(sorted(edge_pushers)) or 'none'}")
    print(f"  cron jobs         : {len(jobs)}")

    offenders = []
    for row in jobs:
        parts = row.split("\t")
        if len(parts) < 3:
            continue
        name, schedule, command = parts[0].strip(), parts[1].strip(), parts[2]
        if name in DRAIN_EXEMPT:
            continue
        hit = sorted({p for p in producers if re.search(rf"\b{re.escape(p)}\b", command)})
        hit += sorted({e for e in edge_pushers if e not in DRAIN_EXEMPT and f"/{e}" in command})
        if hit:
            offenders.append(f"{name} ({schedule}) invokes {', '.join(hit)}")

    if offenders:
        print("FAIL no-clock-driven-push — a SCHEDULED job now enqueues a user push:")
        for o in offenders:
            print("    - " + o)
        print("    A clock-driven push CHOOSES its own hour, so 'no quiet hours' stops being")
        print("    defensible the moment one exists. Answer T109's quiet-window question first:")
        print("    a per-user window + timezone, and an urgency tier that may pierce it.")
        return 1

    print("PASS no-clock-driven-push — every push producer is event-driven, so a phone can only "
          "buzz when someone acted; quiet hours remain an honest absence rather than a missing guard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
