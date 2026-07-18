"""
Cron Schedule Integrity Validator — WorkHive Platform
======================================================
pg_cron jobs are silent failure points. A cron that fires into a renamed /
deleted function returns an HTTP error to net.http_post, which is logged
nowhere user-visible. The data the cron was supposed to refresh just goes
stale; nobody notices until a customer asks why a report is from last month.

This validator parses every uncommented `cron.schedule(...)` call across
supabase/migrations/, extracts the URL + body + schedule, and cross-checks
each one against the deployed edge functions and the scheduled-agents fan-out
table. Same shape as validate_idempotency / silo-monitor / audit-log-coverage.

  Layer 1 — Cron job target exists
    1.  Every cron URL of shape /functions/v1/<name> resolves to
        supabase/functions/<name>/index.ts on disk
    [FAIL] Renamed/deleted function leaves cron firing into the void.

  Layer 2 — scheduled-agents fan-out routing
    2.  Every report_type sent by a cron job to /scheduled-agents is
        registered in the function's `runners` dispatch table.
    [FAIL] Cron fires; scheduled-agents returns 400 "Unknown report_type".

  Layer 3 — Cron config drift (hardcoded URLs + placeholder keys)
    3.  No cron URL hardcodes a project-id host instead of using
        current_setting('app.supabase_functions_url') — breaks on project move.
    4.  No cron block contains an unfilled placeholder bearer token
        (YOUR_PROJECT / YOUR_SERVICE_ROLE_KEY / SERVICE_ROLE_KEY / SUPABASE_CRON_SERVICE_KEY)
        — cron would 401 against the function.
    [WARN] Both — cron may still work in the live project (where the host
    matches and the secret is rotated in pg_cron job table) but the migration
    file is misleading for a fresh deploy.

  Layer 4 — Schedule sanity
    5.  Each cron expression has 5 standard fields and no sub-minute frequency.
    6.  No duplicate job names across the migration set (last-writer-wins).
    [WARN] sub-minute schedules + duplicate names; commented-out blocks pass
    automatically (they don't run).

Usage:  python validate_cron_schedule_integrity.py
Output: cron_schedule_integrity_report.json
"""
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT           = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(ROOT, "supabase", "migrations")
FUNCTIONS_DIR  = os.path.join(ROOT, "supabase", "functions")
SCHEDULED_AGENTS_PATH = os.path.join(FUNCTIONS_DIR, "scheduled-agents", "index.ts")

# Placeholder bearer-token strings that should never reach a deployed cron job.
# Match conservatively — only flag the specific tokens we've seen in this repo's
# migration set; user-defined identifiers won't accidentally match.
PLACEHOLDER_KEYS = [
    "YOUR_PROJECT",
    "YOUR_SERVICE_ROLE_KEY",
    "SERVICE_ROLE_KEY",  # bare, not the env-var reference current_setting('app.service_role_key')
    "SUPABASE_CRON_SERVICE_KEY",
]

# Hosts that are project-id specific. The portable alternative is
# current_setting('app.supabase_functions_url') which is set per-project.
HARDCODED_HOST_PATTERN = re.compile(
    r"https?://([a-z0-9]{20})\.supabase\.co", re.IGNORECASE
)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _strip_block_comments(sql: str) -> str:
    """Remove `/* ... */` blocks so commented-out cron.schedule blocks don't
    register as active. Line-prefix `-- ...` comments are stripped per-line
    in the caller via line-by-line filtering."""
    return re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)


def _strip_line_comments(sql: str) -> str:
    """Drop lines that start with '--' (after whitespace). Cron blocks are
    sometimes documented as commented-out templates; those should not parse."""
    out: list[str] = []
    for line in sql.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("--"):
            continue
        out.append(line)
    return "\n".join(out)


def _list_migration_files() -> list[str]:
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    out: list[str] = []
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".sql"):
            continue
        if fname.endswith("_baseline.sql"):
            continue  # pg_dump snapshot, different dialect
        out.append(os.path.join(MIGRATIONS_DIR, fname))
    return out


# ── Cron block extraction ─────────────────────────────────────────────────────

# Matches both `SELECT cron.schedule(...)` and `PERFORM cron.schedule(...)`
# (the latter appears inside DO $$ ... $$ EXCEPTION blocks). Captures up to
# the matching ');'.
CRON_SCHEDULE_RE = re.compile(
    r"(?:SELECT|PERFORM)\s+cron\.schedule\s*\(\s*(.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
JOB_NAME_RE   = re.compile(r"^\s*'([^']+)'\s*,", re.DOTALL)
SCHEDULE_RE   = re.compile(r",\s*'([^']+)'\s*,", re.DOTALL)
URL_RE        = re.compile(r"url\s*:?=\s*'([^']+)'", re.IGNORECASE)
URL_CONCAT_RE = re.compile(
    r"current_setting\(\s*''app\.supabase_functions_url''\s*\)\s*\|\|\s*''(/[^']+)''",
    re.IGNORECASE,
)
# Body can appear in two forms:
#   (a) Top-level cron in $$ ... $$ literal:    body := '{"report_type":"foo"}'
#   (b) Nested cron inside DO $$ ... $$ block:  body := ''{"report_type":"foo"}''
# In (b) the entire 3rd argument to cron.schedule() is itself a SQL string, so
# its inner single quotes are doubled. Match either single or double single
# quotes around the body literal.
BODY_RE        = re.compile(r"body\s*:?=\s*'{1,2}([^']+)'{1,2}", re.IGNORECASE | re.DOTALL)
REPORT_TYPE_RE = re.compile(r'"report_type"\s*:\s*"([\w-]+)"')


def _extract_cron_jobs() -> list[dict]:
    """Walk every migration file, drop comments, parse each cron.schedule(...)
    block. Returns list of {file, job_name, schedule, url_path, report_type,
    raw_block} dicts.

    Dedup model: pg_cron is last-writer-wins per job_name (re-running
    cron.schedule('foo', ...) overwrites the previous schedule for 'foo').
    Migrations apply in filename order, so we keep the last definition by file
    order. This way a new portable-URL migration naturally supersedes an older
    placeholder-URL migration without needing an explicit exempt list."""
    raw_jobs: list[dict] = []
    for path in _list_migration_files():
        raw = _read(path)
        cleaned = _strip_line_comments(_strip_block_comments(raw))
        for match in CRON_SCHEDULE_RE.finditer(cleaned):
            block = match.group(1)
            jm = JOB_NAME_RE.match(block)
            if not jm:
                continue
            job_name = jm.group(1)
            sm = SCHEDULE_RE.search(block)
            schedule = sm.group(1) if sm else None

            # URL: either a literal url := 'https://...' OR a current_setting
            # concat of shape current_setting('app.supabase_functions_url') || '/scheduled-agents'.
            # In dollar-quoted ($$ ... $$) blocks, single quotes are literal;
            # in PERFORM blocks inside DO $$ they're escaped as '' inside the
            # outer single-quoted string. Try both shapes.
            url_path = None
            um = URL_RE.search(block)
            if um:
                url_full = um.group(1)
                pm = re.search(r"/functions/v1/([\w-]+)", url_full)
                if pm:
                    url_path = pm.group(1)
            else:
                cm = URL_CONCAT_RE.search(block)
                if cm:
                    pm = re.search(r"/([\w-]+)$", cm.group(1))
                    if pm:
                        url_path = pm.group(1)

            # Report type (only meaningful when url_path == 'scheduled-agents')
            report_type = None
            bm = BODY_RE.search(block)
            if bm:
                rm = REPORT_TYPE_RE.search(bm.group(1))
                if rm:
                    report_type = rm.group(1)

            raw_jobs.append({
                "file":        os.path.relpath(path, ROOT),
                "job_name":    job_name,
                "schedule":    schedule,
                "url_path":    url_path,    # None = SQL-only job (e.g. DELETE)
                "report_type": report_type,
                "raw_block":   block,
            })

    # Dedup by job_name keeping the last definition (file order = apply order).
    # This mirrors pg_cron's actual last-writer-wins behavior so the validator
    # reflects what the live cron.job table holds, not a historical sum of all
    # ever-defined schedules.
    deduped: dict[str, dict] = {}
    for job in raw_jobs:
        deduped[job["job_name"]] = job
    return list(deduped.values())


# ── Layer 1: Function existence ──────────────────────────────────────────────

def check_function_existence(jobs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for job in jobs:
        path = job.get("url_path")
        if not path:
            continue  # SQL-only job (e.g. DELETE), no function to check
        fn_dir = os.path.join(FUNCTIONS_DIR, path)
        fn_index = os.path.join(fn_dir, "index.ts")
        if os.path.isfile(fn_index):
            continue
        issues.append({
            "check": "cron_function_exists",
            "job":   job["job_name"],
            "file":  job["file"],
            "reason": (
                f"Cron job '{job['job_name']}' ({job['file']}) targets "
                f"/functions/v1/{path} but supabase/functions/{path}/index.ts "
                f"does not exist. The cron will fire silently (HTTP 404 logged "
                f"nowhere user-visible) and the data this job was supposed to "
                f"refresh will go stale. Either deploy the function, rename the "
                f"cron URL, or unschedule via cron.unschedule('{job['job_name']}')."
            ),
        })
    return issues


# ── Layer 5: cron-honesty — a function that CLAIMS a cron must have one ───────
# The reverse of Layer 1. A function whose header comment asserts a pg_cron trigger
# must have a matching cron.schedule in a migration; otherwise it silently never runs
# and its output ages as if fresh. Found in the Asset/Alert/Shift PDDA arc (2026-07-12):
# amc-orchestrator + failure-signature-scan claimed crons that lived only in the manual
# enable_amc_cron.sql (hard-coded prod URL), so every fresh env left them unarmed
# (F12/F13). Armed via 20260712000014_arm_intelligence_crons.sql.
CRON_CLAIM_RE = re.compile(
    r"(called by pg_cron|triggered by pg_cron|pg_cron (daily|weekly|nightly|hourly)|"
    r"cron[- ]scheduled|scheduled by pg_cron|runs (daily|nightly|weekly) via (pg_)?cron)",
    re.IGNORECASE,
)
# A header that also documents manual/on-demand invocation resolves the ambiguity (exempt).
CRON_MANUAL_OK_RE = re.compile(
    r"(manual(ly)?[- ]only|on[- ]demand|invoked manually|or manually via|client[- ]invoked)",
    re.IGNORECASE,
)


def check_cron_claim_armed(jobs: list[dict]) -> list[dict]:
    """Every edge function whose header claims a cron trigger must be scheduled by a migration."""
    issues: list[dict] = []
    scheduled_targets = {j.get("url_path") for j in jobs if j.get("url_path")}
    if not os.path.isdir(FUNCTIONS_DIR):
        return issues
    for entry in sorted(os.listdir(FUNCTIONS_DIR)):
        idx = os.path.join(FUNCTIONS_DIR, entry, "index.ts")
        if not os.path.isfile(idx):
            continue
        header = "\n".join(_read(idx).splitlines()[:60])
        if not CRON_CLAIM_RE.search(header):
            continue
        if CRON_MANUAL_OK_RE.search(header):
            continue  # claim describes intended ops; fn is legitimately invoked another way
        if entry in scheduled_targets:
            continue
        issues.append({
            "check": "cron_claim_armed",
            "job":   entry,
            "file":  f"supabase/functions/{entry}/index.ts",
            "reason": (
                f"Function '{entry}' header claims a pg_cron trigger, but NO migration "
                f"schedules /functions/v1/{entry}. It will silently never run and its output "
                f"ages as if fresh (cron-honesty gap, F13 class). Add a cron.schedule in a "
                f"migration using the portable current_setting('app.supabase_functions_url') "
                f"pattern, or update the header if the function is manual/on-demand only."
            ),
        })
    return issues


# ── Layer 2: scheduled-agents fan-out routing ────────────────────────────────

RUNNERS_RE = re.compile(
    # Anchor on `{` (the body opener) rather than `=` — the type signature
    # contains both `=` (in `=>` arrows) and `>` chars, so an `=`/`>` based
    # lookahead picks the wrong delimiter. The body literal is the first `{`
    # after the `runners` keyword and contains no nested `{` (one-key-per-line
    # function references), so `[^}]+` cleanly captures it.
    r"const\s+runners[^{]*\{([^}]+)\}",
    re.DOTALL,
)
RUNNER_KEY_RE = re.compile(r"^\s*(\w+)\s*:", re.MULTILINE)


def _scheduled_agents_runner_keys() -> set[str]:
    src = _read(SCHEDULED_AGENTS_PATH)
    if not src:
        return set()
    m = RUNNERS_RE.search(src)
    if not m:
        return set()
    return set(RUNNER_KEY_RE.findall(m.group(1)))


def check_scheduled_agents_routing(jobs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    keys = _scheduled_agents_runner_keys()
    if not keys:
        return [{
            "check": "scheduled_agents_routing",
            "reason": (
                f"Could not parse `runners` registry in {os.path.relpath(SCHEDULED_AGENTS_PATH, ROOT)} "
                f"— validator can't verify cron→handler routing. Either the runners "
                f"object was renamed or its shape changed; update RUNNERS_RE."
            ),
        }]
    for job in jobs:
        if job.get("url_path") != "scheduled-agents":
            continue
        rt = job.get("report_type")
        if rt is None:
            issues.append({
                "check": "scheduled_agents_routing",
                "job":   job["job_name"],
                "file":  job["file"],
                "reason": (
                    f"Cron job '{job['job_name']}' POSTs to /scheduled-agents "
                    f"but the body does not include a report_type field. The "
                    f"function will return 400 'Missing required field: "
                    f"report_type' on every fire. Add `\"report_type\": \"...\"` "
                    f"to the body JSON."
                ),
            })
            continue
        if rt in keys:
            continue
        issues.append({
            "check": "scheduled_agents_routing",
            "job":   job["job_name"],
            "file":  job["file"],
            "reason": (
                f"Cron job '{job['job_name']}' POSTs report_type='{rt}' to "
                f"/scheduled-agents but '{rt}' is NOT in the function's runners "
                f"dispatch table (registered: {sorted(keys)}). Cron fires; "
                f"function returns 400 'Unknown report_type: {rt}'. Either add "
                f"a runner branch in scheduled-agents/index.ts or fix the cron body."
            ),
        })
    return issues


# ── Layer 3: Config drift (hardcoded host + placeholder keys) ────────────────

def check_cron_config_drift(jobs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for job in jobs:
        block = job.get("raw_block", "")
        # Hardcoded project-id host
        host_match = HARDCODED_HOST_PATTERN.search(block)
        if host_match:
            issues.append({
                "check": "cron_config_drift", "skip": True,
                "job":   job["job_name"], "file":  job["file"],
                "reason": (
                    f"Cron job '{job['job_name']}' hardcodes Supabase host "
                    f"'{host_match.group(1)}.supabase.co' in the URL. This breaks "
                    f"on project clone (e.g. customer self-host or staging-vs-prod). "
                    f"Use current_setting('app.supabase_functions_url') instead, "
                    f"matching the pattern in 20260505000002_project_knowledge.sql."
                ),
            })
        # Unfilled placeholder bearer
        for ph in PLACEHOLDER_KEYS:
            if ph in block:
                issues.append({
                    "check": "cron_config_drift", "skip": True,
                    "job":   job["job_name"], "file":  job["file"],
                    "reason": (
                        f"Cron job '{job['job_name']}' contains placeholder "
                        f"'{ph}' in the bearer header — looks like an unfilled "
                        f"deploy template. The cron will fire and the function "
                        f"will reject the request with 401. Replace with "
                        f"`current_setting('app.service_role_key')` (auto-set by "
                        f"Supabase) or rotate the actual service-role key into "
                        f"pg_cron job storage post-deploy."
                    ),
                })
                break  # one placeholder finding per job is enough
    return issues


# ── Layer 4: Schedule sanity ─────────────────────────────────────────────────

def check_schedule_sanity(jobs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    seen_names: dict[str, str] = {}
    for job in jobs:
        # Duplicate names
        if job["job_name"] in seen_names:
            issues.append({
                "check": "schedule_sanity", "skip": True,
                "job": job["job_name"], "file": job["file"],
                "reason": (
                    f"Duplicate cron job name '{job['job_name']}' across "
                    f"{seen_names[job['job_name']]} and {job['file']}. pg_cron "
                    f"silently keeps the last-written schedule, so one of these "
                    f"is dead code. Rename one or unschedule the obsolete entry."
                ),
            })
        else:
            seen_names[job["job_name"]] = job["file"]

        sched = job.get("schedule") or ""
        fields = sched.split()
        if len(fields) != 5:
            issues.append({
                "check": "schedule_sanity", "skip": True,
                "job": job["job_name"], "file": job["file"],
                "reason": (
                    f"Cron job '{job['job_name']}' has schedule '{sched}' "
                    f"({len(fields)} fields, expected 5: minute hour day month dow). "
                    f"pg_cron will reject this — the cron job never starts."
                ),
            })
            continue
        # Sub-minute frequency catch — '* * * * *' = every minute, fine in
        # principle but suspicious for the kind of work this platform schedules.
        # Flag it as a sanity check, not a hard block.
        if sched.strip() == "* * * * *":
            issues.append({
                "check": "schedule_sanity", "skip": True,
                "job": job["job_name"], "file": job["file"],
                "reason": (
                    f"Cron job '{job['job_name']}' runs every minute "
                    f"(schedule '* * * * *'). For this platform that's almost "
                    f"certainly wrong — the cheapest scheduled function still "
                    f"hits the database. Re-check the schedule and pick the "
                    f"largest interval that meets the requirement."
                ),
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "cron_function_exists",
    "scheduled_agents_routing",
    "cron_config_drift",
    "schedule_sanity",
    "cron_claim_armed",
]
CHECK_LABELS = {
    "cron_function_exists":     "L1  Every cron URL targets a deployed edge function",
    "scheduled_agents_routing": "L2  Every cron report_type is registered in scheduled-agents runners",
    "cron_config_drift":        "L3  No hardcoded project host or placeholder bearer in cron blocks  [WARN]",
    "schedule_sanity":          "L4  Cron expressions are 5-field, no duplicate names, no sub-minute  [WARN]",
    "cron_claim_armed":         "L5  Every fn that CLAIMS a cron trigger is scheduled by a migration",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nCron Schedule Integrity Validator (5-layer)"))
    print("=" * 60)

    jobs = _extract_cron_jobs()
    print(f"  Parsed {len(jobs)} active cron job(s) across {len(_list_migration_files())} migration file(s).\n")

    all_issues: list[dict] = []
    all_issues += check_function_existence(jobs)
    all_issues += check_scheduled_agents_routing(jobs)
    all_issues += check_cron_config_drift(jobs)
    all_issues += check_schedule_sanity(jobs)
    all_issues += check_cron_claim_armed(jobs)

    # Per-check pass/warn/fail formatting (mirror the validator family idiom)
    by_check: dict[str, list[dict]] = defaultdict(list)
    for i in all_issues:
        by_check[i["check"]].append(i)

    n_pass = n_warn = n_fail = 0
    for name in CHECK_NAMES:
        items = by_check.get(name, [])
        warns = [i for i in items if i.get("skip")]
        fails = [i for i in items if not i.get("skip")]
        label = CHECK_LABELS[name]
        if not items:
            print(f"  \033[92mPASS\033[0m  {label}")
            n_pass += 1
        elif not fails:
            print(f"  \033[93mSKIP\033[0m  {label}")
            n_warn += 1
        else:
            print(f"  \033[91mFAIL\033[0m  {label}")
            n_fail += 1

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")

    report = {
        "validator":  "cron_schedule_integrity",
        "jobs_seen":  len(jobs),
        "summary":    {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "jobs":       [{k: v for k, v in j.items() if k != "raw_block"} for j in jobs],
        "issues":     [i for i in all_issues if not i.get("skip")],
        "warnings":   [i for i in all_issues if i.get("skip")],
    }
    out = os.path.join(ROOT, "cron_schedule_integrity_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
