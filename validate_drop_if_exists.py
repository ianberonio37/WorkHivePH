"""
Migration DROP ... IF EXISTS Idempotency Validator (L0, ratcheted).
=======================================================================
Every `DROP TABLE`, `DROP VIEW`, `DROP FUNCTION`, `DROP INDEX`,
`DROP POLICY`, `DROP TRIGGER`, `DROP TYPE`, `DROP SEQUENCE`,
`DROP SCHEMA` in a migration MUST include `IF EXISTS`. Otherwise
re-running the migration against a partially-applied state aborts
with "does not exist" — broken deployment recovery.

Postgres handles `IF EXISTS` for all the above kinds; there's no
reason to omit it in versioned migrations.

Exemption: `drop-if-exists-allow` marker on the same statement.

Output: drop_if_exists_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "drop_if_exists_report.json"
BASELINE_PATH = ROOT / "drop_if_exists_baseline.json"

DROP_RE = re.compile(
    r"\bDROP\s+(TABLE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|INDEX|POLICY|TRIGGER|TYPE|SEQUENCE|SCHEMA|CONSTRAINT)\b(?P<after>[^;]*)",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('drop_if_exists: ...')` for coverage credit.
CHECK_NAMES = ["drop_if_exists"]


def _strip_sql_strings_keep_lines(src: str) -> str:
    def _rep(m):
        return "\n" * m.group(0).count("\n") + " " * (len(m.group(0)) - m.group(0).count("\n"))
    out = re.sub(r"\$([\w]*)\$.*?\$\1\$", _rep, src, flags=re.DOTALL)
    out = re.sub(r"'(?:''|[^'])*'", _rep, out)
    return out


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    body_clean = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body_clean = re.sub(r"--[^\n]*", "", body_clean)
    body_clean = _strip_sql_strings_keep_lines(body_clean)
    for m in DROP_RE.finditer(body_clean):
        kind = m.group(1).upper().replace("  ", " ")
        after = m.group("after")
        if re.search(r"\bIF\s+EXISTS\b", after, re.IGNORECASE):
            continue
        if "drop-if-exists-allow" in body[max(0, m.start()-200): m.end()+100]:
            continue
        line_no = body_clean.count("\n", 0, m.start()) + 1
        issues.append({"migration": path.name, "line": line_no, "kind": kind,
                       "ctx": m.group(0)[:100].strip()})
    return issues


def main() -> int:
    mig_dir = ROOT / "supabase" / "migrations"
    if not mig_dir.exists():
        print("PASS — no migrations.")
        return 0
    issues = []
    scanned = 0
    for path in sorted(mig_dir.glob("*.sql")):
        scanned += 1
        issues.extend(_check_file(path))

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

    print(f"\nDROP ... IF EXISTS Idempotency Validator (L0)")
    print("=" * 56)
    print(f"  migrations scanned: {scanned}")
    print(f"  drift:              {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every DROP includes IF EXISTS.")
        return 0
    for i in issues[:25]:
        print(f"  {i['migration']}:{i['line']}  DROP {i['kind']}  {i['ctx']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
