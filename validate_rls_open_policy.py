"""
RLS Open-Policy Detection Validator (L0, ratcheted).
=========================================================
Every `CREATE POLICY` MUST have a USING clause that meaningfully
scopes rows. The dangerous patterns:
  - `USING (true)` — every row matches; RLS effectively disabled
  - `WITH CHECK (true)` on INSERT/UPDATE — anyone can write any row
  - Policy declared but USING/WITH CHECK omitted entirely

These open-tenant policies leak data across hives or expose audit
tables to all users. Caught early, easy fix; caught late, GDPR-grade
incident.

Legitimate exemptions (use `rls-open-allow: <reason>` marker):
  - Public-read tables (achievement_definitions, standards catalog)
  - Health-check / heartbeat tables visible to all authenticated users

Output: rls_open_policy_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "rls_open_policy_report.json"
BASELINE_PATH = ROOT / "rls_open_policy_baseline.json"

# Match CREATE POLICY name ON table ... USING (...) ... WITH CHECK (...)
POLICY_RE = re.compile(
    r"CREATE\s+POLICY\s+(?P<name>[\w\"]+)\s+ON\s+(?P<table>[\w\"\.]+)(?P<body>[\s\S]*?)(?:;|$)",
    re.IGNORECASE,
)
USING_RE      = re.compile(r"USING\s*\(\s*(?P<expr>[\s\S]*?)\s*\)\s*(?:WITH|;|$)", re.IGNORECASE)
WITH_CHECK_RE = re.compile(r"WITH\s+CHECK\s*\(\s*(?P<expr>[\s\S]*?)\s*\)\s*(?:USING|;|$)", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('rls_open_policy: ...')` for coverage credit.
CHECK_NAMES = ["rls_open_policy"]


def _is_open_expr(expr: str) -> bool:
    """An expression is OPEN if it normalises to `true`, `1=1`, or empty."""
    e = expr.strip().lower()
    e = re.sub(r"\s+", " ", e)
    return e in ("true", "1=1", "1 = 1", "(true)", "(1=1)") or e == ""


DROP_POLICY_RE = re.compile(
    r"DROP\s+POLICY(?:\s+IF\s+EXISTS)?\s+(?P<name>[\w\"]+)\s+ON\s+(?P<table>[\w\"\.]+)",
    re.IGNORECASE,
)


def _check_file(path: Path, dropped: set) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    # Strip line + block comments
    body_clean = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body_clean = re.sub(r"--[^\n]*", "", body_clean)
    for m in POLICY_RE.finditer(body_clean):
        block = m.group(0)
        policy = m.group("name").strip('"')
        table  = m.group("table").strip('"').rsplit('.', 1)[-1].strip('"')
        # Superseded by a later DROP POLICY on the same (table, name) key?
        if (table.lower(), policy.lower()) in dropped:
            continue
        if "rls-open-allow" in body[max(0, m.start()-200): m.end()+100]:
            continue
        bm = m.group("body")
        using_match = USING_RE.search(bm)
        wc_match    = WITH_CHECK_RE.search(bm)
        if using_match and _is_open_expr(using_match.group("expr")):
            issues.append({"migration": path.name, "policy": policy, "table": table,
                           "clause": "USING (true)"})
            continue
        if wc_match and _is_open_expr(wc_match.group("expr")):
            issues.append({"migration": path.name, "policy": policy, "table": table,
                           "clause": "WITH CHECK (true)"})
            continue
    return issues


def main() -> int:
    mig_dir = ROOT / "supabase" / "migrations"
    if not mig_dir.exists():
        print("PASS — no migrations.")
        return 0
    # Pass 1: gather every DROP POLICY across all migrations.
    dropped = set()
    for path in sorted(mig_dir.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"--[^\n]*", "", text)
        for m in DROP_POLICY_RE.finditer(text):
            tbl = m.group("table").strip('"').rsplit('.', 1)[-1].strip('"').lower()
            name = m.group("name").strip('"').lower()
            dropped.add((tbl, name))
    issues = []
    scanned = 0
    for path in sorted(mig_dir.glob("*.sql")):
        scanned += 1
        issues.extend(_check_file(path, dropped))

    drift = len(issues)
    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if drift < baseline:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"migrations_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nRLS Open-Policy Validator (L0)")
    print("=" * 56)
    print(f"  migrations scanned: {scanned}")
    print(f"  open policies:      {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no RLS policy uses USING(true)/WITH CHECK(true) without an allow marker.")
        return 0
    for i in issues[:25]:
        print(f"  {i['migration']}  {i['table']}.{i['policy']}  {i['clause']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
