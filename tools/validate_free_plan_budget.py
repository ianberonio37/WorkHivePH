"""validate_free_plan_budget.py - BRH 9 (2026-10-21): the platform stays on the free plans of both hosts.

Ian, 2026-10-21: "you know that my platform always free ... I am not upgrading to pro, can you just be proactive and do
appropriately what is needed for my platform." Supabase Free holds a 500 MB database; measured on production, 77 MB
of its 134 MB was pg_cron's run history (443,228 runs, ~5,800 a day, nothing removing any), and five more operational
tables grew with every use and were never purged. Vercel Hobby holds 10 GB of deployments, which deploy-payload bounds
(each build's upload, 40 MB at most).

STATIC  F1 every operational table (OPERATIONAL) has a scheduled purge in a migration - cron.schedule(...) whose command
           deletes from it with a window - or stands in PENDING_PURGE, which may only shrink (a pending table that has
           gained its purge is a stale entry and fails, so the list can never hide one);
        F3 the list reads that ship an inline photo column (select * or naming photo, on logbook / inventory) are no more
           than PHOTO_READS_BASELINE, which may only fall as photos move to Storage.
        F4 what Vercel stores stays under STORE_SHARE of the free 10 GB: the payload every build uploads now
           (deploy_payload) times the builds the project keeps - the greater of its keep-newest count and the busiest
           30 days of production builds in the CADENCE_DAYS before the record was read (free_plan_evidence.json, the
           retention as Vercel's dashboard showed it). On 2026-10-21 the dashboard drew 9.90 of 10 GB for six days:
           the 612.7 MB builds of the old denylist, kept for 30 days. Either lever alone breaks it - the denylist's
           payload, or April's cadence (639 builds in 30 days) even at today's 20.5 MB.
LIVE    F2 each purge F1 found is a job the local database has active (cron.job, read-only).
SELF-TEST (--self-test): the cron purge taken out of its migration, a stale pending entry, a new photo-shipping read,
        the denylist's payload, April's build cadence - each caught; the clean run is green.

    python tools/validate_free_plan_budget.py [--self-test]
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    # reconfigure in place: a NEW wrapper here closes the one a gate importing this module made (its old wrapper is
    # dropped and collected, closing the shared buffer - "I/O operation on closed file")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations"
DB = "supabase_db_workhive"
# what the platform records about itself - never a person's work, and never an audit trail (whose stated windows stand)
OPERATIONAL = ["cron.job_run_details", "public.wh_traces", "public.analytics_events", "public.automation_log",
               "public.ai_cost_log", "public.client_errors"]
# measured without a purge on 2026-10-21 (free_plan_evidence.json); each leaves as its BRH-AA row closes
PENDING_PURGE = {"public.wh_traces", "public.analytics_events", "public.automation_log", "public.ai_cost_log",
                 "public.client_errors"}
PHOTO_READS_BASELINE = 23
EVIDENCE = ROOT / "free_plan_evidence.json"
STORE_SHARE = 0.10      # of the free allowance, for every build the project keeps
CADENCE_DAYS = 90       # the recent cadence: pushes go out in batches at the owner's say (April pushed every commit)
PURGE = re.compile(r"cron\.schedule\(\s*'[^']+'\s*,\s*'[^']+'\s*,\s*\$\$(.*?)\$\$", re.S | re.I)


def purged_in(migrations: dict[str, str]) -> dict[str, str]:
    """{table: the migration that schedules its purge}, from every cron.schedule whose command deletes with a window."""
    out = {}
    for name, text in sorted(migrations.items()):
        for m in PURGE.finditer(text):
            for d in re.finditer(r"delete\s+from\s+([\w.]+)\s+where\s+[\w.]+\s*<\s*now\(\)\s*-\s*interval", m.group(1), re.I):
                t = d.group(1).lower()
                out[t if "." in t else "public." + t] = name
    return out


def live_jobs() -> list[str] | None:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-c",
                            "select command from cron.job where active"], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        return r.stdout.splitlines() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def photo_read_count() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    from free_plan_evidence import photo_reads
    return len(photo_reads())


def payload_mb() -> float:
    sys.path.insert(0, str(ROOT / "tools"))
    import deploy_payload
    return deploy_payload.size(deploy_payload.shipped()) / 1e6


def kept_builds(ev: dict) -> tuple[int, str]:
    """The builds the project keeps under its retention: the greater of its keep-newest count and the busiest window of
    production builds (window = the retention's days) in the CADENCE_DAYS before the record was read."""
    v = ev.get("vercel") or {}
    dash = v.get("dashboard") or {}
    ret = dash.get("retention") or {"production_days": 30, "keep_newest": 10}
    span, keep = int(ret["production_days"]), int(ret["keep_newest"])
    read = dt.date.fromisoformat(dash.get("read") or ev["read"])
    per = {dt.date.fromisoformat(d): n for d, n in (v.get("builds_per_day") or {}).items()}
    best, best_end = 0, read
    for k in range(CADENCE_DAYS - span + 1):
        end = read - dt.timedelta(days=k)
        n = sum(c for d, c in per.items() if end - dt.timedelta(days=span) < d <= end)
        if n > best:
            best, best_end = n, end
    why = (f"the busiest {span} days of the {CADENCE_DAYS} before {read} ({best} production builds, to {best_end})"
           if best >= keep else f"the {keep} newest builds the project always keeps")
    return max(keep, best), why


def check(migrations: dict[str, str] | None = None, pending: set | None = None, photo_reads: int | None = None,
          live: bool = True, payload: float | None = None, evidence: dict | None = None) -> list[str]:
    migrations = migrations if migrations is not None else {p.name: p.read_text(encoding="utf-8", errors="replace")
                                                            for p in sorted(MIG.glob("*.sql"))}
    pending = PENDING_PURGE if pending is None else pending
    issues = []
    purged = purged_in(migrations)
    for t in OPERATIONAL:
        if t in purged and t in pending:
            issues.append(f"F1 {t} has its purge ({purged[t]}) and still stands in PENDING_PURGE - remove the stale entry")
        elif t not in purged and t not in pending:
            issues.append(f"F1 {t} grows with every use and no migration schedules its purge - the free 500 MB database fills")
    if live:
        jobs = live_jobs()
        if jobs is None:
            issues.append("F2 LIVE could not read the local cron jobs")
        else:
            blob = "\n".join(jobs).lower()
            for t in OPERATIONAL:
                if t in purged and not re.search(r"delete\s+from\s+" + re.escape(t.replace("public.", "")).replace("\\.", r"\.?"), blob):
                    if t.split(".")[-1] not in blob:
                        issues.append(f"F2 {t}'s purge ({purged[t]}) is not an active job in the local database")
    n = photo_read_count() if photo_reads is None else photo_reads
    if n > PHOTO_READS_BASELINE:
        issues.append(f"F3 {n} list reads ship an inline photo column (baseline {PHOTO_READS_BASELINE}) - a new read selects "
                      "the image; select the columns the list shows")
    ev = evidence if evidence is not None else json.loads(EVIDENCE.read_text(encoding="utf-8"))
    mb = payload_mb() if payload is None else payload
    builds, why = kept_builds(ev)
    allowance = float((ev.get("vercel") or {}).get("allowance_gb") or 10) * 1024
    if mb * builds > STORE_SHARE * allowance:
        issues.append(f"F4 {mb:.1f} MB a build x {builds} builds kept ({why}) = {mb * builds / 1024:.2f} GB - over "
                      f"{STORE_SHARE:.0%} of the free {allowance / 1024:.0f} GB of Deployment Storage")
    return issues


def self_test() -> list[str]:
    fails = []
    mb = payload_mb()
    clean = check(payload=mb)
    if clean:
        fails.append(f"the clean run is not green: {clean[:2]}")
    migs = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in sorted(MIG.glob("*.sql"))}
    cron_mig = "20261015997000_free_cron_history_retention.sql"
    mut = dict(migs)
    mut[cron_mig] = re.sub(r"select cron\.schedule\(.*?\);", "", migs[cron_mig], flags=re.S)
    if not any(i.startswith("F1 cron.job_run_details") for i in check(mut, live=False, payload=mb)):
        fails.append("mutant 'the cron history purge taken out of its migration' was not caught")
    if not any("stale entry" in i for i in check(None, PENDING_PURGE | {"cron.job_run_details"}, live=False, payload=mb)):
        fails.append("mutant 'a stale pending entry' was not caught")
    if not any(i.startswith("F3") for i in check(None, None, PHOTO_READS_BASELINE + 1, live=False, payload=mb)):
        fails.append("mutant 'a new photo-shipping read' was not caught")
    ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if not any(i.startswith("F4") for i in check(live=False, payload=612.7, evidence=ev)):
        fails.append("mutant 'the denylist's 612.7 MB payload' was not caught")
    burst = json.loads(json.dumps(ev))
    read = dt.date.fromisoformat(burst["vercel"]["dashboard"]["read"])
    burst["vercel"]["builds_per_day"] = {(read - dt.timedelta(days=k)).isoformat(): (22 if k < 29 else 1) for k in range(30)}
    if not any(i.startswith("F4") for i in check(live=False, payload=mb, evidence=burst)):
        fails.append("mutant 'April's cadence (639 builds in 30 days) at today's payload' was not caught")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (5 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    mb = payload_mb()
    issues = check(payload=mb)
    print("Free-plan budget (BRH 9): what the database keeps and what the pages ship stays inside the free plans")
    for i in issues:
        print("  [FAIL] " + i)
    purged = purged_in({p.name: p.read_text(encoding="utf-8", errors="replace") for p in sorted(MIG.glob("*.sql"))})
    done = [t for t in OPERATIONAL if t in purged]
    builds, _ = kept_builds(json.loads(EVIDENCE.read_text(encoding="utf-8")))
    print(f"  PASS - {len(done)} of {len(OPERATIONAL)} operational tables purge on a schedule ({', '.join(done)}); "
          f"{len(PENDING_PURGE)} pending; photo-shipping reads at most {PHOTO_READS_BASELINE}; Vercel keeps "
          f"{mb:.1f} MB x {builds} builds = {mb * builds / 1024:.2f} GB of the free 10 GB" if not issues
          else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
