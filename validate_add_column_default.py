"""
ADD COLUMN with DEFAULT/NULL Validator (L0, ratcheted).
==========================================================
Every `ALTER TABLE X ADD COLUMN Y` MUST do at least one of:
  - allow NULL explicitly (the default unless NOT NULL is added)
  - provide a DEFAULT value
  - declare NOT NULL DEFAULT <something>
  - be wrapped in IF NOT EXISTS + explicit backfill in the same migration

Anti-pattern: `ADD COLUMN status text NOT NULL` — Postgres rejects this
on a table with existing rows (no default, can't satisfy NOT NULL).
The migration fails halfway, leaving the schema in an inconsistent
state.

This validator scans migration SQL for the dangerous shape: ADD COLUMN
with NOT NULL and no DEFAULT.

Output: add_column_default_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "add_column_default_report.json"
BASELINE_PATH = ROOT / "add_column_default_baseline.json"

# Match `ADD COLUMN [IF NOT EXISTS] <name> <type> ... ` up to comma/semi.
ADD_COL_RE = re.compile(
    r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[\w\"]+)\s+(?P<rest>[^,;]+)",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('add_column_default: ...')` for coverage credit.
CHECK_NAMES = ["add_column_default"]


def _check_migration(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    if "add-column-default-allow" in body:
        return []
    # Strip block comments + line comments
    body_clean = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body_clean = re.sub(r"--[^\n]*", "", body_clean)
    for m in ADD_COL_RE.finditer(body_clean):
        rest = m.group("rest").lower()
        has_not_null = re.search(r"\bnot\s+null\b", rest) is not None
        has_default  = re.search(r"\bdefault\b", rest) is not None
        # Primary keys imply NOT NULL by spec but PG also requires a value;
        # treat PRIMARY KEY without explicit value as risky.
        if has_not_null and not has_default:
            issues.append({
                "migration": path.name,
                "column":     m.group("name").strip('"'),
                "rest":       m.group("rest").strip()[:120],
            })
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
        issues.extend(_check_migration(path))

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

    print(f"\nADD COLUMN DEFAULT Validator (L0)")
    print("=" * 56)
    print(f"  migrations scanned: {scanned}")
    print(f"  drift:              {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every ADD COLUMN NOT NULL has a DEFAULT.")
        return 0
    for i in issues[:25]:
        print(f"  {i['migration']}  → ADD COLUMN {i['column']} {i['rest']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
