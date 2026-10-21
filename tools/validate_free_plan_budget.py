"""validate_free_plan_budget.py - BRH 9 (2026-10-21): the platform stays on the free plans of both hosts.

Ian, 2026-10-21: "you know that my platform always free ... I am not upgrading to pro, can you just be proactive and do
appropriately what is needed for my platform." Supabase Free holds a 500 MB database; measured on production, 77 MB
of its 134 MB was pg_cron's run history (443,228 runs, ~5,800 a day, nothing removing any), and five more operational
tables grew with every use and were never purged. Vercel Hobby holds 10 GB of deployments, which deploy-payload bounds
(each build's upload, 40 MB at most).

STATIC  F1 every operational table (OPERATIONAL) has a scheduled purge in a migration - cron.schedule(...) whose command
           deletes from it with a window, or (PURGED_BY_FUNCTION) a scheduled function whose latest definition does -
           or stands in PENDING_PURGE, which may only shrink (a pending table that has gained its purge is a stale entry
           and fails, so the list can never hide one). An audit trail (AUDIT_KEPT) is the opposite: the privacy policy
           keeps audit logs AUDIT_YEARS years, so a scheduled purge inside that window fails;
        F3 no list read ships an inline photo (select * or naming photo, on logbook / inventory and their truth views):
           photos live in Storage since BRH 9 AB (2026-10-21), and a list reads every column but photo (whRowCols).
           The measurement is free_plan_evidence.photo_reads - shared with photos-in-storage, which holds the rest.
        F4 what Vercel stores stays under STORE_SHARE of the free 10 GB: the payload every build uploads now
           (deploy_payload) times the builds the project keeps - the greater of its keep-newest count and the busiest
           30 days of production builds in the CADENCE_DAYS before the record was read (free_plan_evidence.json, the
           retention as Vercel's dashboard showed it). On 2026-10-21 the dashboard drew 9.90 of 10 GB for six days:
           the 612.7 MB builds of the old denylist, kept for 30 days. Either lever alone breaks it - the denylist's
           payload, or April's cadence (639 builds in 30 days) even at today's 20.5 MB.
        F5 Supabase Free pauses a project after 7 days of low activity, which takes every page down: a scheduled
           workflow (.github/workflows) asks production a REST question at least every KEEPALIVE_MAX_DAYS days.
LIVE    F2 each purge F1 found is a job the local database has active (cron.job, read-only); a function purge is a
           function the database holds with that delete, called by an active job; an audit table is still read by its
           audit view (if the view stops reading it, the exemption is stale and fails).
SELF-TEST (--self-test): the cron purge taken out of its migration, the telemetry purges taken out of theirs, the
        ai_cost_log delete taken out of its function, a 90-day purge scheduled on the audit trail, a stale pending
        entry, a new photo-shipping read, the denylist's payload, April's build cadence, an audit view that no longer
        reads its table - each caught; the clean run is green.

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
OPERATIONAL = ["cron.job_run_details", "public.wh_traces", "public.analytics_events", "public.ai_cost_log",
               "public.client_errors"]
# purged by a function a scheduled job calls rather than by a delete written in the job: {table: function}.
# hard_delete_expired_soft_deletes() removes AI cost records after 365 days (20260707000007; job hard-delete-soft-expired)
PURGED_BY_FUNCTION = {"public.ai_cost_log": "hard_delete_expired_soft_deletes"}
# audit trails the privacy policy keeps ("ISO audit logs ... 10 years"): {table: the audit view that reads it}.
# automation_log was measured as growing with no purge (BRH498) - true, and by design: it is v_audit_unified's source
AUDIT_KEPT = {"public.automation_log": "v_audit_unified"}
AUDIT_YEARS = 10
# measured without a purge on 2026-10-21 (free_plan_evidence.json); all closed the same day (20261015998000), so the
# list is empty and may stay so
PENDING_PURGE: set[str] = set()
PHOTO_READS_BASELINE = 0   # BRH 9 AB: was 23 - fourteen of them writes that return no rows, nine real reads
EVIDENCE = ROOT / "free_plan_evidence.json"
WORKFLOWS = ROOT / ".github" / "workflows"
KEEPALIVE_MAX_DAYS = 6  # Supabase Free pauses a project after 7 days of low activity
STORE_SHARE = 0.10      # of the free allowance, for every build the project keeps
CADENCE_DAYS = 90       # the recent cadence: pushes go out in batches at the owner's say (April pushed every commit)
# a scheduled job's command in any quoting a migration uses: $$...$$, a tagged $cron$...$cron$, or '...'
PURGE = re.compile(r"cron\.schedule\(\s*'[^']+'\s*,\s*'[^']+'\s*,\s*(?:\$(?P<tag>[A-Za-z_]*)\$(?P<cmd>.*?)\$(?P=tag)\$"
                   r"|'(?P<sq>(?:[^']|'')*)')", re.S | re.I)


def _cmd(m: re.Match) -> str:
    return m.group("cmd") if m.group("cmd") is not None else m.group("sq").replace("''", "'")


WINDOWED_DELETE = r"delete\s+from\s+{t}\s+where\s+[\w.]+\s*<\s*now\(\)\s*-\s*interval\s*'([^']+)'"


def _qualified(t: str) -> str:
    t = t.lower()
    return t if "." in t else "public." + t


def _days(interval: str) -> float:
    """'90 days' / '365 days' / '10 years' / '48 hours' -> days."""
    m = re.match(r"\s*(\d+)\s*(year|month|week|day|hour|minute)", interval, re.I)
    if not m:
        return 0.0
    per = {"year": 365.0, "month": 30.0, "week": 7.0, "day": 1.0, "hour": 1 / 24, "minute": 1 / 1440}
    return int(m.group(1)) * per[m.group(2).lower()]


def latest_function_body(migrations: dict[str, str], fn: str) -> tuple[str, str] | None:
    """(migration, body) of the LAST migration that (re)defines public.<fn> - the definition the database runs."""
    found = None
    head = re.compile(r"create\s+(?:or\s+replace\s+)?function\s+(?:public\.)?" + re.escape(fn) + r"\s*\(", re.I)
    for name, text in sorted(migrations.items()):
        for m in head.finditer(text):
            tag = re.search(r"\bas\s+(\$[A-Za-z_]*\$)", text[m.end():], re.I)
            if not tag:
                continue
            start = m.end() + tag.end()
            end = text.find(tag.group(1), start)
            if end > 0:
                found = (name, text[start:end])
    return found


def purged_in(migrations: dict[str, str]) -> dict[str, str]:
    """{table: the migration that schedules its purge}, from every cron.schedule whose command deletes with a window,
    and every PURGED_BY_FUNCTION table whose function's latest definition deletes it with a window and is scheduled."""
    out = {}
    scheduled = ""
    for name, text in sorted(migrations.items()):
        for m in PURGE.finditer(text):
            scheduled += _cmd(m) + "\n"
            for d in re.finditer(WINDOWED_DELETE.format(t=r"([\w.]+)"), _cmd(m), re.I):
                out[_qualified(d.group(1))] = name
    for table, fn in PURGED_BY_FUNCTION.items():
        body = latest_function_body(migrations, fn)
        bare = table.split(".")[-1]
        if (body and re.search(WINDOWED_DELETE.format(t=r"(?:public\.)?" + re.escape(bare)), body[1], re.I)
                and re.search(r"\b" + re.escape(fn) + r"\s*\(", scheduled, re.I)):
            out[table] = body[0]
    return out


def audit_purges(migrations: dict[str, str]) -> list[str]:
    """Scheduled purges of an AUDIT_KEPT table inside the audit window the privacy policy states."""
    out = []
    for name, text in sorted(migrations.items()):
        for m in PURGE.finditer(text):
            for table in AUDIT_KEPT:
                bare = table.split(".")[-1]
                for d in re.finditer(WINDOWED_DELETE.format(t=r"(?:public\.)?" + re.escape(bare)), _cmd(m), re.I):
                    if _days(d.group(1)) < AUDIT_YEARS * 365:
                        out.append(f"F1 {table} is an audit trail the privacy policy keeps {AUDIT_YEARS} years, and {name} "
                                   f"schedules its purge after {d.group(1)}")
    return out


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def live_state() -> dict | None:
    """What the local database runs: active job commands, each PURGED_BY_FUNCTION function's body, each audit view."""
    jobs = _psql("select command from cron.job where active")
    if jobs is None:
        return None
    fns = {fn: _psql(f"select prosrc from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
                     f"where n.nspname = 'public' and p.proname = '{fn}'") or "" for fn in PURGED_BY_FUNCTION.values()}
    views = {v: _psql(f"select pg_get_viewdef('public.{v}'::regclass)") or "" for v in AUDIT_KEPT.values()}
    return {"jobs": jobs, "fns": fns, "views": views}


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


def cron_gap_days(expr: str) -> float | None:
    """The longest gap in days between a 5-field cron's runs, for the shapes a keep-alive uses; None when unknown."""
    f = expr.split()
    if len(f) != 5 or f[3] != "*":
        return None
    dom, dow = f[2], f[4]
    if dom == "*" and dow == "*":
        return 1.0
    if dow == "*":
        m = re.fullmatch(r"\*/(\d+)", dom)
        return float(m.group(1)) if m else None    # day N of a month restarts at 1: a gap is never longer than N
    if dom == "*":
        days = set()
        for part in dow.split(","):
            r = re.fullmatch(r"(\d)(?:-(\d))?", part)
            if not r:
                return None
            lo, hi = int(r.group(1)), int(r.group(2) or r.group(1))
            days |= set(range(lo, hi + 1))
        days = sorted(d % 7 for d in days)
        return float(max((days[(i + 1) % len(days)] - d) % 7 or 7 for i, d in enumerate(days)))
    return None


def keepalive(workflows: dict[str, str] | None = None) -> list[str]:
    """F5: some scheduled workflow asks production a REST question at least every KEEPALIVE_MAX_DAYS days."""
    files = workflows if workflows is not None else {p.name: p.read_text(encoding="utf-8", errors="replace")
                                                     for p in sorted(WORKFLOWS.glob("*.y*ml"))}
    best = None
    for name, text in files.items():
        if "/rest/v1/" not in text:
            continue
        for c in re.findall(r"cron:\s*['\"]([^'\"]+)['\"]", text):
            g = cron_gap_days(c)
            if g is not None and (best is None or g < best[0]):
                best = (g, name, c)
    if best is None:
        return ["F5 no scheduled workflow asks production a REST question - Supabase Free pauses a project after 7 days "
                "of low activity, and a paused project takes every page down"]
    if best[0] > KEEPALIVE_MAX_DAYS:
        return [f"F5 {best[1]} asks production every {best[0]:g} days ({best[2]}) - over {KEEPALIVE_MAX_DAYS}; the Free plan "
                "pauses a project after 7 idle days"]
    return []


def check(migrations: dict[str, str] | None = None, pending: set | None = None, photo_reads: int | None = None,
          live: bool = True, payload: float | None = None, evidence: dict | None = None,
          state: dict | None = None, workflows: dict[str, str] | None = None) -> list[str]:
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
    issues += audit_purges(migrations)
    if live:
        st = state if state is not None else live_state()
        if st is None:
            issues.append("F2 LIVE could not read the local cron jobs")
        else:
            blob = st["jobs"].lower()
            for t in OPERATIONAL:
                bare = t.split(".")[-1]
                fn = PURGED_BY_FUNCTION.get(t)
                if t not in purged:
                    continue
                if fn:
                    if not re.search(r"\b" + re.escape(fn) + r"\s*\(", blob):
                        issues.append(f"F2 {t}'s purge runs in {fn}(), and no active job calls it")
                    elif not re.search(WINDOWED_DELETE.format(t=r"(?:public\.)?" + re.escape(bare)), st["fns"].get(fn, ""), re.I):
                        issues.append(f"F2 {fn}() in the local database no longer deletes {t} by age")
                elif not re.search(WINDOWED_DELETE.format(t=r"(?:[\w]+\.)?" + re.escape(bare)), blob, re.I):
                    issues.append(f"F2 {t}'s purge ({purged[t]}) is not an active job in the local database")
            for t, view in AUDIT_KEPT.items():
                if t.split(".")[-1] not in st["views"].get(view, ""):
                    issues.append(f"F2 {view} no longer reads {t} - it is no longer the audit trail AUDIT_KEPT exempts; "
                                  f"move it to OPERATIONAL and give it a purge")
    n = photo_read_count() if photo_reads is None else photo_reads
    if n > PHOTO_READS_BASELINE:
        issues.append(f"F3 {n} list reads ship an inline photo column (allowed {PHOTO_READS_BASELINE}) - a read selects "
                      "the image; read whRowCols('<source>') (every column but photo) or the columns the list shows")
    ev = evidence if evidence is not None else json.loads(EVIDENCE.read_text(encoding="utf-8"))
    mb = payload_mb() if payload is None else payload
    builds, why = kept_builds(ev)
    allowance = float((ev.get("vercel") or {}).get("allowance_gb") or 10) * 1024
    if mb * builds > STORE_SHARE * allowance:
        issues.append(f"F4 {mb:.1f} MB a build x {builds} builds kept ({why}) = {mb * builds / 1024:.2f} GB - over "
                      f"{STORE_SHARE:.0%} of the free {allowance / 1024:.0f} GB of Deployment Storage")
    issues += keepalive(workflows)
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
    tel_mig = "20261015998000_free_telemetry_retention.sql"
    mut = dict(migs)
    mut[tel_mig] = re.sub(r"select cron\.schedule\(.*?\);", "", migs[tel_mig], flags=re.S)
    got = {i.split()[1] for i in check(mut, live=False, payload=mb) if i.startswith("F1 public.")}
    if got != {"public.wh_traces", "public.client_errors", "public.analytics_events"}:
        fails.append(f"mutant 'the telemetry purges taken out of their migration' caught {sorted(got)}")
    body = latest_function_body(migs, PURGED_BY_FUNCTION["public.ai_cost_log"])
    mut = dict(migs)
    mut[body[0]] = migs[body[0]].replace(body[1], re.sub(r"(?is)delete\s+from\s+(?:public\.)?ai_cost_log\s+where[^;]*;",
                                                         "-- (mutant) no ai_cost_log purge\n", body[1]))
    if not any(i.startswith("F1 public.ai_cost_log") for i in check(mut, live=False, payload=mb)):
        fails.append("mutant 'the ai_cost_log delete taken out of its function' was not caught")
    mut = dict(migs)
    mut["29991231000000_mutant.sql"] = ("select cron.schedule('automation-log-retention', '0 5 * * *', "
                                        "$$ delete from public.automation_log where created_at < now() - interval '90 days' $$);")
    if not any("audit trail" in i for i in check(mut, live=False, payload=mb)):
        fails.append("mutant 'a 90-day purge scheduled on the audit trail' was not caught")
    flows = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in sorted(WORKFLOWS.glob("*.y*ml"))}
    unscheduled = {n: re.sub(r"(?m)^\s*-\s*cron:.*$", "", t) for n, t in flows.items()}
    if not any(i.startswith("F5") for i in check(live=False, payload=mb, workflows=unscheduled)):
        fails.append("mutant 'the keep-alive's schedule taken out' was not caught")
    slow = {n: re.sub(r"cron:\s*'23 3 \*/2 \* \*'", "cron: '23 3 */9 * *'", t) for n, t in flows.items()}
    if not any(i.startswith("F5") and "every 9 days" in i for i in check(live=False, payload=mb, workflows=slow)):
        fails.append("mutant 'a keep-alive every 9 days' was not caught")
    if cron_gap_days("0 6 * * 1,4") != 4.0 or cron_gap_days("0 6 * * 1-5") != 3.0:
        fails.append("cron_gap_days misreads a weekday list")
    st = live_state()
    if st is not None:
        st_mut = dict(st, views={v: "select 1" for v in st["views"]})
        if not any(i.startswith("F2") and "no longer reads" in i for i in check(payload=mb, state=st_mut)):
            fails.append("mutant 'an audit view that no longer reads its table' was not caught")
        st_mut = dict(st, fns={f: "begin return 0; end" for f in st["fns"]})
        if not any(i.startswith("F2") and "no longer deletes" in i for i in check(payload=mb, state=st_mut)):
            fails.append("mutant 'the live function without its ai_cost_log delete' was not caught")
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
        print("SELF-TEST PASS (12 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
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
          f"{len(PENDING_PURGE)} pending; {len(AUDIT_KEPT)} audit trail kept ({', '.join(AUDIT_KEPT)}); "
          f"photo-shipping reads {PHOTO_READS_BASELINE}; Vercel keeps "
          f"{mb:.1f} MB x {builds} builds = {mb * builds / 1024:.2f} GB of the free 10 GB" if not issues
          else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
