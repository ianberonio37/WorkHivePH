"""
Cron Job Functional Coverage -- WorkHive Platform
====================================================
Sister to validate_cron_schedule_integrity (which checks portable URL
+ schedule string syntax). This gate checks the FUNCTIONAL contract:
every pg_cron job's target fn exists on disk, has a config.toml entry,
is rate-gated (for AI fns), and has a matching body shape.

Layer 1 -- Cron target fn exists on disk                                 [FAIL]
  Every `cron.schedule(name, schedule, $$ net.http_post('/<fn>', ...) $$)`
  references a fn whose supabase/functions/<fn>/index.ts exists.

Layer 2 -- Cron target fn has config.toml entry                          [WARN]
  Without [functions.<fn>] in config.toml the fn won't deploy.

Layer 3 -- Cron-triggered AI fns are rate-gated (informational)          [INFO]
  Cron jobs hitting AI-calling fns should have the rate gate ON --
  cron-driven calls can saturate the budget without it.

Layer 4 -- Cron schedule density per fn (informational)                  [INFO]
  Per-target-fn count of cron jobs. Helps spot over-scheduled fns.
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
CONFIG_TOML    = os.path.join("supabase", "config.toml")


CRON_OK: dict[str, str] = {
    # "fn_name": "reason"
}


SCHEDULE_RE = re.compile(
    r"""cron\.schedule\s*\(\s*['"`](?P<name>[^'"`]+)['"`]\s*,\s*
        ['"`](?P<schedule>[^'"`]+)['"`]\s*,\s*\$\$
        (?P<body>[\s\S]*?)\$\$""",
    re.VERBOSE,
)
FN_URL_RE = re.compile(r"""/functions/v1/(?P<fn>[\w-]+)""")
PORTABLE_FN_RE = re.compile(
    r"""current_setting\s*\(\s*['"]app\.supabase_functions_url['"]\s*\)
        \s*\|\|\s*['"]/(?P<fn>[\w-]+)['"]""",
    re.VERBOSE,
)


def collect_cron_jobs() -> list[dict]:
    """Last-writer-wins per job name across all migrations."""
    by_name: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in SCHEDULE_RE.finditer(sql):
            body = m.group("body")
            fn_m = FN_URL_RE.search(body) or PORTABLE_FN_RE.search(body)
            fn_name = fn_m.group("fn") if fn_m else None
            by_name[m.group("name")] = {
                "name":     m.group("name"),
                "schedule": m.group("schedule"),
                "fn":       fn_name,
                "file":     os.path.basename(path),
            }
    return list(by_name.values())


def fn_index_exists(fn: str) -> bool:
    return os.path.isfile(os.path.join(FUNCTIONS_DIR, fn, "index.ts"))


def fn_in_config(fn: str) -> bool:
    src = read_file(CONFIG_TOML) or ""
    return bool(re.search(rf"\[functions\.{re.escape(fn)}\]", src))


def fn_has_rate_gate(fn: str) -> bool:
    src = read_file(os.path.join(FUNCTIONS_DIR, fn, "index.ts")) or ""
    return "checkAIRateLimit" in src


def fn_calls_ai(fn: str) -> bool:
    src = read_file(os.path.join(FUNCTIONS_DIR, fn, "index.ts")) or ""
    return "callAI(" in src


def check_target_exists(jobs):
    issues, report = [], []
    for j in jobs:
        if not j["fn"]:
            continue
        if j["fn"] in CRON_OK:
            continue
        if fn_index_exists(j["fn"]):
            continue
        report.append({"job": j["name"], "fn": j["fn"]})
        issues.append({
            "check": "target_exists", "skip": False,
            "reason": (
                f"Cron job '{j['name']}' targets fn '{j['fn']}' but "
                f"{FUNCTIONS_DIR}/{j['fn']}/index.ts does not exist. "
                f"Either restore the fn, fix the cron URL, or unschedule."
            ),
        })
    return issues, report


def check_target_in_config(jobs):
    issues, report = [], []
    for j in jobs:
        if not j["fn"] or not fn_index_exists(j["fn"]):
            continue
        if fn_in_config(j["fn"]):
            continue
        report.append({"job": j["name"], "fn": j["fn"]})
        issues.append({
            "check": "target_in_config", "skip": True,
            "reason": (
                f"Cron job '{j['name']}' targets fn '{j['fn']}' which "
                f"has source on disk but no [functions.{j['fn']}] entry "
                f"in config.toml. The fn won't deploy."
            ),
        })
    return issues, report


def check_ai_cron_gate(jobs):
    rows = []
    for j in jobs:
        if not j["fn"] or not fn_index_exists(j["fn"]):
            continue
        if not fn_calls_ai(j["fn"]):
            continue
        rows.append({
            "job":   j["name"],
            "fn":    j["fn"],
            "gated": fn_has_rate_gate(j["fn"]),
        })
    return [], rows


def check_density(jobs):
    by_fn: dict[str, list[str]] = {}
    for j in jobs:
        if not j["fn"]:
            continue
        by_fn.setdefault(j["fn"], []).append(j["name"])
    rows = [
        {"fn": fn, "n_jobs": len(names), "names": names}
        for fn, names in sorted(by_fn.items(), key=lambda kv: -len(kv[1]))
    ]
    return [], rows


CHECK_NAMES = ["target_exists", "target_in_config", "ai_cron_gate", "density"]
CHECK_LABELS = {
    "target_exists":    "L1  Every cron target fn exists on disk                          [FAIL]",
    "target_in_config": "L2  Every cron target fn has a config.toml entry                 [WARN]",
    "ai_cron_gate":     "L3  Cron-triggered AI fns are rate-gated (informational)         [INFO]",
    "density":          "L4  Cron jobs per target fn (informational)                      [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nCron Job Functional Coverage (4-layer)"))
    print("=" * 60)
    jobs = collect_cron_jobs()
    print(f"  {len(jobs)} cron job(s) parsed (last-writer-wins per job name).\n")
    l1_i, l1_r = check_target_exists(jobs)
    l2_i, l2_r = check_target_in_config(jobs)
    l3_i, l3_r = check_ai_cron_gate(jobs)
    l4_i, l4_r = check_density(jobs)
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "cron_functional", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "target_exists": l1_r, "target_in_config": l2_r,
              "ai_cron_gate": l3_r, "density": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("cron_functional_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
