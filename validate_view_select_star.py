"""
CREATE VIEW SELECT * Validator (L0, ratcheted).
====================================================
A `CREATE [OR REPLACE] VIEW v_foo AS SELECT * FROM base_table` is an
anti-pattern in this codebase:
  - Adding a column to base_table silently widens the view's contract.
  - Renaming a column on base_table breaks every consumer with no
    warning at CREATE time (only at first SELECT).
  - The canonical-registry parser (tools/mine_canonical_registry.py)
    can't enumerate view columns without an explicit projection — so
    other validators (query_column_existence, signal_trust) lose
    coverage of these views.

Acceptable forms:
  - SELECT col1, col2, ... FROM ...
  - SELECT t.* FROM t — but only with `view-select-star-allow` marker
    documenting why the wildcard is intentional (rare).

Output: view_select_star_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "view_select_star_report.json"
BASELINE_PATH = ROOT / "view_select_star_baseline.json"

# CREATE [OR REPLACE] VIEW <name> AS SELECT *
VIEW_STAR_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?P<name>[\w\"\.]+)\s+AS\s+SELECT\s+(?:[\w]+\.)?\*",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('view_select_star: ...')` for coverage credit.
CHECK_NAMES = ["view_select_star"]


def _strip_strings_keep_lines(src: str) -> str:
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
    body_clean = _strip_strings_keep_lines(body_clean)
    for m in VIEW_STAR_RE.finditer(body_clean):
        view = m.group("name").strip('"')
        if "view-select-star-allow" in body[max(0, m.start()-200): m.end()+200]:
            continue
        line_no = body_clean.count("\n", 0, m.start()) + 1
        issues.append({"migration": path.name, "line": line_no, "view": view})
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

    print(f"\nCREATE VIEW SELECT * Validator (L0)")
    print("=" * 56)
    print(f"  migrations scanned: {scanned}")
    print(f"  drift:              {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every CREATE VIEW projects explicit columns.")
        return 0
    for i in issues[:25]:
        print(f"  {i['migration']}:{i['line']}  view={i['view']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
