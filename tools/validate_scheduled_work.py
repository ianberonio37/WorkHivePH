#!/usr/bin/env python3
"""validate_scheduled_work.py - scheduled work is real: it fires, a double fire leaves one effect, its failure reaches a person.

The OWN scheduled-work lens (2026-10-26), one row per (job, ask) for the 18 jobs measured live on seed day. What it found:
  - no person could see a job fail: cron's run history and pg_net's answers were read by nothing (production's 16 HTTP
    jobs failed for weeks), and an HTTP job is "succeeded" to cron whatever its function answers
  - three jobs did their work again when fired twice: the monthly holding fee charged sellers twice, the size snapshot
    wrote two points a day, the nightly AI eval doubled its rows and its model spend
  - two of the 18 no longer exist: cleanup_expired_memory was never scheduled (agent-memory-retention does it) and
    nightly-analytics-cache was unscheduled, its table unread by any page or function

LIVE (local stack; every probe runs inside a transaction that is rolled back):
  fires     each lens job is scheduled and active, its last run is inside its own period (or, for a job whose period is
            longer than the 7 days of history kept, its own command runs clean now)
  double    a double fire leaves one effect: retention jobs delete a planted old row once and spare a young one; the
            holding fee charges a planted reservation once; the snapshot keeps one row a day; the outbox reconciler and
            availability reconciler change nothing the second time; ai_quality_log refuses a second row for one run
  surfaced  a failure planted for the job (a failed run in cron's history; for an HTTP job a 401 from its function) is
            named failing by public.founder_scheduled_work(), the console's own read, for a platform admin
  wiring    every HTTP job's call is wrapped by private.note_scheduled_call; the settle job is scheduled; a non-admin is refused
STATIC: the console draws the panel; ai-eval-runner skips a fixture its run already graded (teeth: the tree at 1045f447).

    python tools/validate_scheduled_work.py                 the gate
    python tools/validate_scheduled_work.py --evidence      also write .tmp/scheduled_work_evidence.json, one entry per (job, ask)
    python tools/validate_scheduled_work.py --self-test     static teeth
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
PGUSER = "supabase_admin"   # cron.job_run_details takes a planted run only from a superuser (runid_seq)
CONSOLE = "founder-console.html"
RUNNER = "supabase/functions/ai-eval-runner/index.ts"
LISTING = "3a7aeb84-1ba5-4bb6-8c5c-f51192c57580"

# jobs measured live on seed day -> how a double fire is proven. 'plant' rows are inserted, the command fired twice.
RETENTION = {
    "achievement-xp-log-purge": ("public.achievement_xp_log", "earned_at", "120 days",
        "insert into public.achievement_xp_log (worker_name, achievement_id, xp_earned, source_action, earned_at) "
        "values ('__own_probe__', 'probe', 1, 'probe', {ts})"),
    "analytics-events-retention": ("public.analytics_events", "created_at", "420 days",
        "insert into public.analytics_events (event_name, created_at) values ('__own_probe__', {ts})"),
    "client-errors-retention": ("public.client_errors", "created_at", "120 days",
        "insert into public.client_errors (context, message, created_at) values ('__own_probe__', 'probe', {ts})"),
    "wh-traces-retention": ("public.wh_traces", "created_at", "120 days",
        "insert into public.wh_traces (trace_id, route, created_at) values ('__own_probe__' || md5(random()::text), '__own_probe__', {ts})"),
    "cron-history-retention": ("cron.job_run_details", "end_time", "10 days",
        "insert into cron.job_run_details (jobid, command, status, return_message, start_time, end_time) "
        "values (0, '__own_probe__', 'succeeded', '__own_probe__', {ts}, {ts})"),
}
RETENTION_MARK = {"public.achievement_xp_log": "worker_name", "public.analytics_events": "event_name",
                  "public.client_errors": "context", "public.wh_traces": "route", "cron.job_run_details": "command"}
SWEEPS = ["listing-holding-fee-monthly", "ops-db-size-snapshot-daily", "service-availability-reconcile-1min",
          "service-outbox-drain-1min", "service-outbox-reconcile-1min"]
EVAL = [f"ai-eval-daily-{s}" for s in ("analytics", "asset-brain", "logbook-voice", "project", "report-voice", "shift")]
GONE = {"cleanup_expired_memory": "never scheduled: its cron.schedule is commented out in 20260516000001; agent-memory-retention purges agent_memory",
        "nightly-analytics-cache": "unscheduled after 20260425000001; hive_analytics_cache holds 0 rows and no page or function reads it"}
LENS = list(RETENTION) + SWEEPS + EVAL
PERIOD = {"* * * * *": "10 minutes"}


def psql(sql: str) -> tuple[list[list[str]], str]:
    r = subprocess.run(["docker", "exec", "-i", "-e", "PGPASSWORD=postgres", DB, "psql", "-h", "127.0.0.1", "-U", PGUSER, "-d", "postgres", "-At", "-F", "\x1f", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if r.returncode != 0:
        return [], (r.stderr or "").strip()[:300]
    rows = [ln.split("\x1f") for ln in (r.stdout or "").splitlines()
            if ln.strip() and not re.match(r"^(BEGIN|ROLLBACK|INSERT \d+ \d+|UPDATE \d+|DELETE \d+|SELECT \d+|SET|RESET|DO)$", ln.strip())]
    return rows, ""


def period_of(schedule: str) -> str:
    if schedule in PERIOD:
        return PERIOD[schedule]
    f = schedule.split()
    if f[2] != "*":
        return "32 days"
    if f[4] != "*":
        return "8 days"
    if f[1] == "*":
        return "2 hours"
    return "26 hours"


ADMIN = ("select auth_uid from public.marketplace_platform_admins where auth_uid is not null order by auth_uid limit 1")


def as_admin(sql_inside: str) -> str:
    # the claims are set BEFORE the role switch: authenticated cannot read the admins table to find the subject
    return (f"select set_config('request.jwt.claims', json_build_object('sub', ({ADMIN})::text, 'role', 'authenticated')::text, true) is not null;\n"
            "set local role authenticated;\n" + sql_inside + "\nreset role;")


def fires(job: str, sched: dict) -> dict:
    s = sched.get(job)
    if not s:
        return {"ok": False, "why": "not scheduled"}
    if s["active"] != "t":
        return {"ok": False, "why": "scheduled but paused"}
    per = period_of(s["schedule"])
    rows, err = psql(f"select status, return_message, start_time from cron.job_run_details where jobid = {s['jobid']} "
                     f"and start_time > now() - interval '{per}' order by runid desc limit 1;")
    if rows and rows[0][0] == "succeeded":
        return {"ok": True, "how": f"ran on schedule {rows[0][2][:19]}: {rows[0][1][:60]}", "period": per}
    if per in ("32 days", "8 days") or not rows:
        # its period is longer than the history kept, or it has not come round yet: its own command runs clean now
        out, err = psql(f"begin;\n{s['command'].rstrip().rstrip(';')};\nrollback;")
        return {"ok": not err, "how": "its own command ran clean (rolled back): " + (err or "ok"), "period": per}
    return {"ok": False, "why": f"its last run in {per} was {rows[0][0]}: {rows[0][1][:120]}"}


def double_retention(job: str, sched: dict) -> dict:
    table, col, age, plant = RETENTION[job]
    mark = RETENTION_MARK[table]
    cmd = sched[job]["command"].rstrip().rstrip(";")
    sql = (f"begin;\n{plant.format(ts=f'now() - interval {chr(39)}{age}{chr(39)}')};\n{plant.format(ts='now()')};\n"
           f"do $p$ declare n1 int; n2 int; begin\n  {cmd};\n  get diagnostics n1 = row_count;\n  {cmd};\n"
           f"  get diagnostics n2 = row_count;\n  raise notice 'own_probe % %', n1, n2;\nend $p$;\n"
           f"select count(*) filter (where {col} < now() - interval '1 day'), count(*) filter (where {col} >= now() - interval '1 day') "
           f"from {table} where {mark} like '__own_probe__%';\nrollback;")
    r = subprocess.run(["docker", "exec", "-i", "-e", "PGPASSWORD=postgres", DB, "psql", "-h", "127.0.0.1", "-U", PGUSER, "-d", "postgres", "-At", "-v", "ON_ERROR_STOP=1"], input=sql,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    m = re.search(r"own_probe (\d+) (\d+)", r.stderr or "")
    left = [ln for ln in (r.stdout or "").splitlines() if "|" in ln]
    if r.returncode != 0 or not m or not left:
        return {"ok": False, "why": (r.stderr or "no result")[:200]}
    old_left, young_left = (int(x) for x in left[-1].split("|"))
    n1, n2 = int(m.group(1)), int(m.group(2))
    ok = old_left == 0 and young_left == 1 and n2 == 0 and n1 >= 1
    return {"ok": ok, "how": f"planted one row past the window and one inside it: fire 1 deleted {n1}, fire 2 deleted {n2}; "
                             f"old left {old_left}, young left {young_left}"}


def double_sweep(job: str) -> dict:
    if job == "listing-holding-fee-monthly":
        rows, err = psql("begin;\ninsert into public.credit_reservations (id, listing_id, seller_name, hive_id, amount, state, created_at) "
                         f"select '00000000-0000-4000-8000-00000000f0f1', l.id, l.seller_name, l.hive_id, 100, 'held', now() "
                         f"from public.marketplace_listings l where l.id = '{LISTING}';\n"
                         "select public.sweep_listing_holding_fee()::text;\nselect public.sweep_listing_holding_fee()::text;\n"
                         f"select count(*), coalesce(sum(amount), 0) from public.service_credit_ledger where entry_type = 'holding_fee' and ref_id = '{LISTING}' "
                         "and date_trunc('month', created_at at time zone 'UTC') = date_trunc('month', now() at time zone 'UTC');\n"
                         "select amount from public.credit_reservations where id = '00000000-0000-4000-8000-00000000f0f1';\nrollback;")
        if err or len(rows) < 4:
            return {"ok": False, "why": err or "the probe returned too little"}
        n, total = int(rows[2][0]), float(rows[2][1])
        return {"ok": n == 1 and abs(float(rows[3][0]) - 98.0) < 0.001,
                "how": f"a held 100-credit reservation on a live listing, swept twice: {n} fee row(s) totalling {total:.2f}, "
                       f"reservation left {float(rows[3][0]):.2f} (one 2% charge = 98.00)"}
    if job == "ops-db-size-snapshot-daily":
        rows, err = psql("begin;\nselect public.snapshot_db_size();\nselect public.snapshot_db_size();\n"
                         "select count(*) from public.ops_db_size_history where (captured_at at time zone 'UTC')::date = (now() at time zone 'UTC')::date;\nrollback;")
        n = int(rows[-1][0]) if rows and not err else -1
        return {"ok": n == 1, "how": f"fired twice: {n} snapshot row(s) for today" if n >= 0 else err}
    if job == "service-availability-reconcile-1min":
        rows, err = psql("begin;\nupdate public.service_providers set availability = 'on_job' where id = (select sp.id from public.service_providers sp "
                         "where not exists (select 1 from public.service_requests r where r.matched_provider_id = sp.id "
                         "and r.status in ('accepted','en_route','on_site','in_progress')) limit 1);\n"
                         "select public.reconcile_provider_availability();\nselect public.reconcile_provider_availability();\nrollback;")
        if err or len(rows) < 2:
            return {"ok": False, "why": err or "no provider to plant"}
        a, b = int(rows[-2][0]), int(rows[-1][0])
        return {"ok": a >= 1 and b == 0, "how": f"a provider left on_job with no live job: fire 1 freed {a}, fire 2 freed {b}"}
    if job == "service-outbox-drain-1min":
        rows, err = psql("begin;\nupdate public.service_outbox set status = 'done' where status in ('pending', 'in_flight');\n"
                         "insert into public.service_outbox (consumer, payload, status, next_attempt_at) values ('own-probe', '{}'::jsonb, 'pending', now() - interval '1 minute');\n"
                         "select (public.drain_service_outbox(20))->>'sent';\nselect (public.drain_service_outbox(20))->>'sent';\n"
                         "select count(*) from public.service_outbox where consumer = 'own-probe' and status = 'in_flight';\nrollback;")
        if err or len(rows) < 3:
            return {"ok": False, "why": err or "the probe returned too little"}
        return {"ok": rows[-3][0] == "1" and rows[-2][0] == "0" and rows[-1][0] == "1",
                "how": f"one pending message, drained twice: sent {rows[-3][0]} then {rows[-2][0]}; in flight {rows[-1][0]}"}
    if job == "service-outbox-reconcile-1min":
        rows, err = psql("begin;\nupdate public.service_outbox set status = 'done' where status in ('pending', 'in_flight');\n"
                         "insert into net._http_response (id, status_code, content, created) values (-424242, 200, 'ok', now());\n"
                         "insert into public.service_outbox (consumer, payload, status, request_id, next_attempt_at) values ('own-probe', '{}'::jsonb, 'in_flight', -424242, now());\n"
                         "select public.reconcile_service_outbox()::text;\nselect public.reconcile_service_outbox()::text;\n"
                         "select status from public.service_outbox where consumer = 'own-probe';\nrollback;")
        if err or len(rows) < 3:
            return {"ok": False, "why": err or "the probe returned too little"}
        return {"ok": rows[-1][0] == "done" and rows[-3][0] != rows[-2][0],
                "how": f"one in-flight message answered 200, reconciled twice: {rows[-3][0]} then {rows[-2][0]}; it ends {rows[-1][0]}"}
    return {"ok": False, "why": "no probe"}


def double_eval(_job: str) -> dict:
    rows, err = psql("begin;\ninsert into public.ai_quality_log (agent_id, question_id, question_text, run_id, run_at, outcome) "
                     "values ('own-probe', 'q1', 'probe', '00000000-0000-4000-8000-0000000e0a10', now(), 'graded');\n"
                     "insert into public.ai_quality_log (agent_id, question_id, question_text, run_id, run_at, outcome) "
                     "values ('own-probe', 'q1', 'probe', '00000000-0000-4000-8000-0000000e0a10', now(), 'graded');\nrollback;")
    refused = "duplicate key" in err or "23505" in err
    return {"ok": refused, "how": "a second row for one run, agent and question is refused (" + ("23505" if refused else err or "accepted") + "); "
                                  "the runner skips a fixture its run already graded"}


def surfaced(job: str, sched: dict) -> dict:
    jid = sched[job]["jobid"]
    plant = (f"insert into cron.job_run_details (jobid, command, status, return_message, start_time, end_time) "
             f"values ({jid}, '__own_probe__', 'failed', 'ERROR: __own_probe__ planted failure', now(), now());")
    if job in EVAL:
        plant += (f"\ninsert into private.scheduled_calls (jobname, fn, request_id, called_at, status_code, error, settled_at) "
                  f"values ('{job}', 'ai-eval-runner', -1, now() + interval '1 second', 401, 'Unauthorized (__own_probe__)', now());")
    rows, err = psql("begin;\n" + plant + "\n" + as_admin(
        f"select last_status, coalesce(last_message, ''), coalesce(last_call_status::text, ''), coalesce(last_call_error, '') "
        f"from public.founder_scheduled_work() where jobname = '{job}';") + "\nrollback;")
    if err or not rows:
        return {"ok": False, "why": err or "the console read did not list the job"}
    st, msg, cs, ce = rows[-1]
    ok = st == "failed" and "__own_probe__" in msg and (job not in EVAL or (cs == "401" and "__own_probe__" in ce))
    return {"ok": ok, "how": f"planted a failed run{' and a 401 from ai-eval-runner' if job in EVAL else ''}: the console read says "
                             f"last run {st} ({msg[:50]}){'; call answered ' + cs if cs else ''}"}


def wiring() -> list[str]:
    bad = []
    rows, err = psql("select count(*) filter (where command ~* 'net\\.http_post\\(' and command not ilike '%note_scheduled_call%' "
                     "and command not ilike '%relay_embedding_outbox%' and command not ilike '%drain_service_outbox%'), "
                     "count(*) filter (where jobname = 'scheduled-calls-settle' and active) from cron.job;")
    if err:
        return [f"cron.job could not be read: {err}"]
    if rows and rows[0][0] != "0":
        bad.append(f"{rows[0][0]} HTTP job(s) call a function without recording the call (note_scheduled_call)")
    if rows and rows[0][1] != "1":
        bad.append("the scheduled-calls-settle job is not scheduled and active")
    rows, err = psql("begin;\nset local role authenticated;\nselect set_config('request.jwt.claims', '{\"sub\":\"00000000-0000-0000-0000-0000000000aa\",\"role\":\"authenticated\"}', true) is not null;\n"
                     "select count(*) from public.founder_scheduled_work();\nrollback;")
    if "Only a platform admin" not in err:
        bad.append("founder_scheduled_work answered someone who is not a platform admin")
    return bad


def static_findings(console: str, runner: str) -> list[str]:
    out = []
    if not ('id="scheduled-work"' in console and "function renderScheduledWork" in console and "rpc('founder_scheduled_work')" in console):
        out.append("the console does not draw scheduled work from founder_scheduled_work")
    if not re.search(r"alreadyGraded[\s\S]{0,600}\.filter\(\(q\) => !alreadyGraded\.has", runner):
        out.append("ai-eval-runner asks a fixture again that its run already graded")
    return out


def self_test() -> int:
    cur = static_findings((ROOT / CONSOLE).read_text(encoding="utf-8", errors="replace"), (ROOT / RUNNER).read_text(encoding="utf-8"))
    old = [subprocess.run(["git", "show", f"1045f447:{p}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
           for p in (CONSOLE, RUNNER)]
    red = static_findings(*old)
    print(f"  {'PASS' if not cur else 'FAIL'} the tree holds both static facts {cur or ''}")
    print(f"  {'PASS' if len(red) == 2 else 'FAIL'} teeth: the tree at 1045f447 fails {len(red)}/2")
    ok = not cur and len(red) == 2
    print(("PASS" if ok else "FAIL") + " scheduled-work self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    print("scheduled-work (OWN): a scheduled job fires, a double fire leaves one effect, its failure reaches a person")
    bad = static_findings((ROOT / CONSOLE).read_text(encoding="utf-8", errors="replace"), (ROOT / RUNNER).read_text(encoding="utf-8"))
    rows, err = psql("select jobname, jobid, schedule, active, replace(command, chr(10), ' ') from cron.job;")
    if err:
        print(f"  SKIP - the local database could not be read ({err[:120]})")
        for b in bad:
            print(f"  - {b}")
        return 1 if bad else 0
    sched = {r[0]: {"jobid": r[1], "schedule": r[2], "active": r[3], "command": r[4]} for r in rows}
    bad += wiring()
    evidence = {}
    for job in LENS:
        e = {"fires": fires(job, sched)}
        e["double"] = (double_retention(job, sched) if job in RETENTION else double_eval(job) if job in EVAL else double_sweep(job))
        e["surfaced"] = surfaced(job, sched) if job in sched else {"ok": False, "why": "not scheduled"}
        evidence[job] = e
        miss = [k for k, v in e.items() if not v.get("ok")]
        print(f"  {'ok  ' if not miss else 'FAIL'} {job}" + (f" - {', '.join(m + ': ' + e[m].get('why', e[m].get('how', ''))[:110] for m in miss)}" if miss else ""))
        bad += [f"{job} {m}" for m in miss]
    for job, why in GONE.items():
        evidence[job] = {"gone": why}
        print(f"  gone {job} - {why}")
    if "--evidence" in sys.argv:
        out = ROOT / ".tmp" / "scheduled_work_evidence.json"
        out.write_text(json.dumps(evidence, indent=1), encoding="utf-8")
        print(f"  evidence: {out.relative_to(ROOT)}")
    for b in bad:
        if " " not in b.split(" ", 1)[0] and b.split(" ", 1)[0] in LENS:
            continue
        print(f"  - {b}")
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
