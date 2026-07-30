#!/usr/bin/env python3
"""
validate_cron_health.py  --  LIVE-tier LOCK for the "unattended pg_cron job silently fails" class.

A scheduled job that errors every run is invisible: no user sees it, no page breaks, the failure
sits only in cron.job_run_details. Found live 2026-07-07: job 24 (hard_delete_expired_soft_deletes,
the soft-delete retention cron) had 28 consecutive `column "deleted_at" does not exist` failures —
so expired soft-deleted rows were never purged — while nothing surfaced.

This gate reads the LATEST run of each active cron job and FAILS if it ended in a REAL CODE error.
It EXCLUDES ONE non-code failure mode so it doesn't cry wolf:
  - transient scheduler hiccups: "job startup timeout"

★ THE `app.supabase_functions_url` EXCLUSION WAS REMOVED (2026-07-29) — and it had been hiding a
  total outage. Nine jobs (ai-eval-daily, amc-brief-0600pht, batch-risk-scoring-daily,
  failure-digest-weekly, failure-signature-scan-daily, ml-retrain-weekly, pm-overdue-daily,
  predictive-weekly, project-risk-weekly) were failing 100% of runs — 27 of 29 failures in a 7-day
  window shared that single message — so the ENTIRE background-automation layer was dead while this
  gate reported green. The exclusion was reasonable-looking ("prod sets that GUC, local doesn't") and
  that is exactly what made it dangerous: a failure class excluded forever is a feature never
  verified. The GUC is now SET on the local DB (`ALTER DATABASE postgres SET
  app.supabase_functions_url` / `app.service_role_key`, as supabase_admin — the postgres role is not
  superuser), proven by firing a dead job's exact command and getting HTTP 200 back. So the correct
  posture flipped: make it runnable locally, then let a real failure RED. If this fires with that
  message again, the GUC is genuinely missing — set it, don't re-exclude it.
Real code errors that ARE flagged: relation/column/function does not exist, syntax error, etc.

Live-tier (skip_if_fast); SKIPS cleanly (exit 0) if the DB is down or pg_cron isn't installed.

Usage:  python tools/validate_cron_health.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = a job's latest run failed with a code error (or self-test failure).
"""
import sys, json, subprocess, re

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-F", "\t", "-c"]

# Failure messages that are NOT code bugs (env/transient) -> excluded.
EXCLUDE_RES = [
    re.compile(r"job startup timeout", re.I),
    # The app.supabase_functions_url exclusion lived here and hid 9 jobs failing 100% of runs.
    # The GUC is set locally now; a recurrence is a REAL outage and must red. See the module docstring.
]


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=45)
        if r.returncode != 0:
            return None
        return r.stdout or ""
    except Exception:
        return None


def latest_runs():
    """Return list of (jobid, status, message) for each active job's most recent run, or None if unavailable."""
    # cron.job_run_details may not exist if pg_cron absent -> psql returns None
    out = psql("""
      WITH latest AS (
        SELECT DISTINCT ON (jobid) jobid, status, coalesce(return_message,'') AS msg
        FROM cron.job_run_details ORDER BY jobid, start_time DESC)
      SELECT j.jobid, coalesce(l.status,'(no runs)'), coalesce(l.msg,'')
      FROM cron.job j LEFT JOIN latest l ON l.jobid=j.jobid
      WHERE j.active ORDER BY j.jobid;""")
    if out is None:
        return None
    rows = []
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 3:
            rows.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return rows


def is_excluded(msg):
    return any(rx.search(msg) for rx in EXCLUDE_RES)


def analyze(rows):
    viols = []
    for jobid, status, msg in rows:
        if status == "failed" and not is_excluded(msg):
            viols.append({"jobid": jobid, "message": msg[:100]})
    return viols


def selftest():
    rows = [
        ("11", "succeeded", "DELETE 0"),
        ("24", "failed", 'ERROR:  column "deleted_at" does not exist'),   # real bug -> FLAG
        # Was excluded as "local env" until 2026-07-29, while 9 jobs failed 100% of runs behind it.
        # Now a REAL outage and MUST be flagged - this case is the regression test for that.
        ("20", "failed", 'ERROR:  unrecognized configuration parameter "app.supabase_functions_url"'),
        ("19", "failed", "job startup timeout"),                          # transient -> skip
        ("30", "failed", 'ERROR:  relation "public.gone" does not exist'), # real bug -> FLAG
        ("31", "(no runs)", ""),                                          # never ran -> skip
    ]
    v = analyze(rows)
    got = {x["jobid"] for x in v}
    expect = {"20", "24", "30"}
    ok = got == expect
    print("  selftest", "PASS" if ok else "FAIL", "-> flagged jobids:", sorted(got), "expected:", sorted(expect))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("cron-health selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    rows = latest_runs()
    if rows is None:
        msg = "pg_cron / local DB unavailable — cron-health check skipped"
        print(json.dumps({"skipped": True, "note": msg}) if as_json else "  SKIP: " + msg)
        return 0
    viols = analyze(rows)
    if as_json:
        print(json.dumps({"jobs": len(rows), "violations": viols, "count": len(viols)}, indent=2))
    else:
        print(f"cron-health (no active pg_cron job's latest run failed with a code error) [{len(rows)} active jobs]")
        if not viols:
            print(f"  PASS: no cron job failing with a code error (env/transient failures excluded)")
        else:
            print(f"  FAIL: {len(viols)} cron job(s) whose latest run failed with a CODE error:")
            for v in viols:
                print(f"    job {v['jobid']}: {v['message']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
