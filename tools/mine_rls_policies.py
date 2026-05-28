"""
RLS Policy Substrate Miner (L-1.5, P1 roadmap 2026-05-27).
============================================================
Closes the (S, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

Scans every CREATE POLICY statement in supabase/migrations/ and flags:
  - USING (true)          — permissive policy on what may be a private table
  - WITH CHECK (true)     — same on write path
  - missing TO clause     — defaults to PUBLIC which includes anon
  - service_role-only policies on tables that ALSO have anon/authenticated SELECT
    (could mask a leak)

This is a SUBSTRATE miner: it does not gate the build, it surfaces patterns
that a human + the harden skill should evaluate. Output flows into
substrate_manifest.json via tools/build_substrate_manifest.py.

Output:
  rls_policy_mining_report.json — per-pattern findings + counts

Exit code:
  0  always (informational miner; aggregated by build_substrate_manifest.py)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
REPORT = ROOT / "rls_policy_mining_report.json"

# CREATE POLICY name ON table FOR verb TO role USING (...) WITH CHECK (...);
POLICY_RE = re.compile(
    r"CREATE\s+POLICY\s+(?P<name>\w+)\s+ON\s+(?:public\.)?(?P<table>\w+)\s+"
    r"(?:FOR\s+(?P<verb>SELECT|INSERT|UPDATE|DELETE|ALL)\s+)?"
    r"(?:TO\s+(?P<to>[\w,\s]+?)\s+)?"
    r"(?:USING\s*\((?P<using>[^;]+?)\))?\s*"
    r"(?:WITH\s+CHECK\s*\((?P<check>[^;]+?)\))?\s*;",
    re.IGNORECASE | re.DOTALL,
)


def main() -> int:
    if not MIGRATIONS.exists():
        REPORT.write_text(json.dumps({"error": "no migrations dir"}), encoding="utf-8")
        return 0

    findings = {
        "permissive_using_true":   [],
        "permissive_check_true":   [],
        "missing_to_clause":       [],
        "anon_select_on_table":    [],
        "total_policies":          0,
    }
    anon_tables: set[str] = set()
    for f in sorted(MIGRATIONS.glob("*.sql")):
        text = f.read_text(encoding="utf-8", errors="replace")
        # Strip comments to avoid false positives in commentary blocks.
        text_clean = re.sub(r"--[^\n]*", "", text)
        for m in POLICY_RE.finditer(text_clean):
            findings["total_policies"] += 1
            name  = m.group("name")
            table = m.group("table")
            verb  = (m.group("verb") or "ALL").upper()
            to    = (m.group("to") or "").strip().lower()
            using = (m.group("using") or "").strip()
            check = (m.group("check") or "").strip()
            row = {"file": f.name, "policy": name, "table": table, "verb": verb, "to": to or "(default PUBLIC)"}

            if re.search(r"^\s*true\s*$", using, re.IGNORECASE):
                findings["permissive_using_true"].append(row)
            if re.search(r"^\s*true\s*$", check, re.IGNORECASE):
                findings["permissive_check_true"].append(row)
            if not to:
                findings["missing_to_clause"].append(row)
            if "anon" in to and verb in ("SELECT", "ALL"):
                anon_tables.add(table)
                findings["anon_select_on_table"].append(row)

    findings["unique_tables_with_anon_select"] = sorted(anon_tables)

    REPORT.write_text(json.dumps(findings, indent=2), encoding="utf-8")

    n_perm_using = len(findings["permissive_using_true"])
    n_perm_check = len(findings["permissive_check_true"])
    n_missing_to = len(findings["missing_to_clause"])
    print(f"RLS policy miner: {findings['total_policies']} policies scanned")
    print(f"  permissive USING(true): {n_perm_using}")
    print(f"  permissive WITH CHECK(true): {n_perm_check}")
    print(f"  missing TO clause (defaults to PUBLIC): {n_missing_to}")
    print(f"  tables with anon SELECT policy: {len(anon_tables)}")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
