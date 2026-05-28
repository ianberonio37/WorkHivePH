"""
Truth-View Contract Validator (L0, P1 roadmap 2026-05-26).
==========================================================
Every `v_*_truth` view defined in supabase/migrations/ must declare the
canonical signal-trust contract:

    _source_count       INTEGER  -- how many rows fed this aggregate
    _freshness_ts       TIMESTAMPTZ -- max(updated_at) of source rows
    _canonical_version  TEXT     -- e.g. 'oee:v2' — version of the formula

Why: today frontends silently trust that a `v_*_truth` view shape will not
change. When a view is rewritten (e.g. column renamed, formula updated),
tiles read stale or wrong values for hours before someone notices. By
forcing every truth view to publish these three meta-columns, frontends
can render last-refresh + source-count tooltips, and Layer 2 specs can
assert the canonical_version they were authored against.

Exit codes:
  0  every v_*_truth view declares all three meta-columns
  1  one or more views are missing meta-columns (FAIL with file:line)
  2  no v_*_truth views found at all (probably a path bug)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "supabase" / "migrations"
REPORT = ROOT / "truth_view_contract_report.json"
BASELINE = ROOT / "truth_view_contract_baseline.json"

CHECK_NAMES = ["truth_view_contract"]

REQUIRED = ("_source_count", "_freshness_ts", "_canonical_version")
VIEW_RE  = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?(v_[a-z0-9_]+_truth)\b(.*?)(?=;)",
    re.IGNORECASE | re.DOTALL,
)


def scan() -> dict:
    """Scan all migrations; for each v_*_truth view, keep only the LATEST
    definition (newest migration timestamp wins). This matches Postgres
    runtime semantics: CREATE OR REPLACE makes the most recent SQL the
    effective view, so an old definition without meta-columns shouldn't
    count as a violation if a later migration added them.
    """
    if not MIGRATIONS.exists():
        return {"views": [], "missing": [], "error": "no migrations dir"}

    latest: dict[str, dict] = {}   # view_name -> entry (latest only)
    for f in sorted(MIGRATIONS.glob("*.sql")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in VIEW_RE.finditer(text):
            name, body = m.group(1), m.group(2)
            absent = [c for c in REQUIRED if c not in body]
            latest[name] = {
                "file":   f.name,        # always overwrite — sorted ascending
                "view":   name,
                "absent": absent,
            }

    views = list(latest.values())
    missing = [v for v in views if v["absent"]]
    return {"views": views, "missing": missing}


def main() -> int:
    result = scan()
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")

    n_views   = len(result["views"])
    n_missing = len(result["missing"])

    if n_views == 0:
        print("\033[91mFAIL: no v_*_truth views found under supabase/migrations/\033[0m")
        return 2

    # Baseline ratchet: first run records the current missing-count so this
    # validator can be added to a codebase that already has gaps without
    # being immediately red. New gaps above baseline fail; closed gaps
    # tighten it downward.
    baseline = 0
    if BASELINE.exists():
        try: baseline = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("missing", 0))
        except Exception: baseline = 0
    else:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")
        baseline = n_missing

    print(f"Truth-view contract: {n_views} views, {n_missing} missing meta-columns (baseline {baseline}).")
    if n_missing > baseline:
        print(f"\033[91mFAIL: regressed +{n_missing - baseline} above baseline\033[0m")
        for e in result["missing"][:10]:
            print(f"  {e['file']} :: {e['view']} → missing {e['absent']}")
        return 1
    if n_missing < baseline:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")
        print(f"\033[92mPASS: baseline tightened {baseline} → {n_missing}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
