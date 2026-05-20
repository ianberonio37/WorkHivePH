"""
pg_cron Target Existence Validator (L0, ratcheted).
=====================================================
Every `cron.schedule('name', '<cron>', $$ SQL $$)` job must reference
tables and functions that exist. After a table rename or RPC drop,
the cron job continues to fire but errors silently — no UI signal,
just a dead scheduled task burning CPU.

Detection
  Scan migrations for `cron.schedule(...)` calls. Extract the SQL
  body. Find table names (FROM, INTO, UPDATE, DELETE FROM, JOIN)
  and function names (SELECT fn(...), CALL fn(...)). Cross-check
  against canonical_registry tables + rpcs.

Output: pg_cron_target_existence_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "pg_cron_target_existence_report.json"
BASELINE_PATH = ROOT / "pg_cron_target_existence_baseline.json"

CRON_SCHEDULE_RE = re.compile(
    r"""cron\.schedule\(\s*['"](?P<name>[^'"]+)['"]\s*,\s*['"](?P<sched>[^'"]+)['"]\s*,\s*\$\$\s*(?P<body>.*?)\s*\$\$""",
    re.DOTALL | re.IGNORECASE,
)
TABLE_REF_RE = re.compile(
    r"""\b(?:FROM|INTO|UPDATE|JOIN)\s+(?:public\.)?(?P<t>[a-z_][\w]*)""",
    re.IGNORECASE,
)
FN_REF_RE = re.compile(
    r"""\b(?:SELECT|CALL|PERFORM)\s+(?:public\.)?(?P<f>[a-z_][\w]*)\s*\(""",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('pg_cron_target_existence: ...')` for coverage credit.
CHECK_NAMES = ["pg_cron_target_existence"]


def main() -> int:
    reg = json.loads((ROOT / "canonical_registry.json").read_text(encoding="utf-8"))
    tables = {t.lower() for t in reg.get("tables", {})}
    views  = {v.lower() for v in reg.get("views", {})}
    rpcs   = {r.lower() for r in reg.get("rpcs", {})}
    pg_builtins = {"now", "current_timestamp", "current_date", "current_setting",
                   "raise", "concat", "coalesce", "lower", "upper", "trim",
                   "count", "sum", "avg", "min", "max", "to_char", "to_date",
                   "extract", "date_trunc", "age", "interval"}

    issues = []
    total_jobs = 0
    seen = set()

    mig_dir = ROOT / "supabase" / "migrations"
    if mig_dir.exists():
        for mig in sorted(mig_dir.glob("*.sql")):
            text = mig.read_text(encoding="utf-8", errors="replace")
            for m in CRON_SCHEDULE_RE.finditer(text):
                total_jobs += 1
                job = m.group("name")
                body = m.group("body")
                # tables / views referenced
                for tm in TABLE_REF_RE.finditer(body):
                    t = tm.group("t").lower()
                    if t in tables or t in views: continue
                    if t in {"only", "lateral", "values"}: continue
                    key = (job, "table", t)
                    if key in seen: continue
                    seen.add(key)
                    issues.append({"job": job, "kind": "table", "ref": t,
                                   "migration": mig.name})
                # functions
                for fm in FN_REF_RE.finditer(body):
                    f = fm.group("f").lower()
                    if f in rpcs or f in pg_builtins: continue
                    key = (job, "function", f)
                    if key in seen: continue
                    seen.add(key)
                    issues.append({"job": job, "kind": "function", "ref": f,
                                   "migration": mig.name})

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("issues", 0)
        except Exception: baseline = 0
    else:
        baseline = len(issues)
        BASELINE_PATH.write_text(json.dumps({"issues": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(issues) < baseline:
        baseline = len(issues)
        BASELINE_PATH.write_text(json.dumps({"issues": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"total_jobs": total_jobs, "total_issues": len(issues), "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\npg_cron Target Existence Validator (L0)")
    print("=" * 56)
    print(f"  cron jobs:        {total_jobs}")
    print(f"  drift refs:       {len(issues)}  (baseline: {baseline})")
    if not issues:
        print("\n  PASS — every pg_cron job target exists.")
        return 0
    for i in issues[:20]:
        print(f"  job='{i['job']}' references {i['kind']} '{i['ref']}' — not in registry")
    return 1 if len(issues) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
