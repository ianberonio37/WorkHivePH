"""
Status-Enum Drift Guard — Grounded Sweep critique W3 (status-enum-constants).
============================================================================
The dayplanner "overdue" KPI bug: a filter compared schedule_items.item_status
against the literal 'closed' — a value that does NOT exist in the enum
(pending / in_progress / done / blocked / skipped) — so DONE items were silently
counted as overdue (live 6 vs DB 3). It was invisible to every static gate and
only surfaced when the live count diverged from the DB.

The systemic guard: a SINGLE source of truth for per-table status enums lives in
utils.js `window.WH_STATUS_ENUMS`, and pages reference it instead of hand-typing
status strings. This validator asserts that constant can NEVER silently diverge
from the canonical DB enum (the capture contract JSON in supabase/migrations).

It is a DETERMINISTIC source-vs-source comparison (JS constant ↔ migration), NOT
a page scanner — so it has zero false positives (a page-literal scanner would
false-fire on legitimate defensive excludes of non-enum values like the fixed
dayplanner filter's 'closed'/'cancelled' guards).

Usage:  python validate_status_enum_drift.py
Exit codes:
  0  WH_STATUS_ENUMS matches the canonical capture-contract enum for every column.
  1  drift detected, the JS constant is missing, or the canonical source is absent.
"""
import io, re, sys, glob, os, json
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# (key in window.WH_STATUS_ENUMS, capture-contract column name to compare against)
CHECKED = [("schedule_item", "item_status")]


def _quoted(s: str) -> set:
    """All single/double-quoted string tokens in a fragment (ignores bare null)."""
    return set(re.findall(r"""['"]([^'"]+)['"]""", s))


def _js_enum(key: str):
    """The array for `key` inside utils.js window.WH_STATUS_ENUMS = { ... }."""
    text = (ROOT / "utils.js").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"WH_STATUS_ENUMS\s*=\s*\{(.*?)\n\s*\};", text, re.DOTALL)
    if not m:
        return None
    km = re.search(re.escape(key) + r"\s*:\s*\[([^\]]*)\]", m.group(1))
    return _quoted(km.group(1)) if km else None


def _db_enum(column: str):
    """The canonical enum for `column` from a capture-contract field def in a
    migration: {"name":"<column>","type":"enum",...,"values":[...]}."""
    pat = re.compile(r'"name"\s*:\s*"' + re.escape(column) + r'"[^}]*?"values"\s*:\s*\[([^\]]*)\]')
    for fp in sorted(glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql"))):
        m = pat.search(Path(fp).read_text(encoding="utf-8", errors="replace"))
        if m:
            return _quoted(m.group(1)), os.path.basename(fp)
    return None, None


def main() -> int:
    bar = "=" * 70
    print(bar)
    failures = []
    for key, column in CHECKED:
        js = _js_enum(key)
        db, src = _db_enum(column)
        if js is None:
            failures.append(f"WH_STATUS_ENUMS['{key}'] not found in utils.js")
            continue
        if db is None:
            failures.append(f"canonical capture-contract enum for '{column}' not found in any migration")
            continue
        if js != db:
            failures.append(
                f"DRIFT: WH_STATUS_ENUMS['{key}'] {sorted(js)} != {column} canonical {sorted(db)} "
                f"(source {src}) — missing {sorted(db - js)} / extra {sorted(js - db)}")
        else:
            print(f"\033[92mOK\033[0m  WH_STATUS_ENUMS['{key}'] == {column} canonical "
                  f"{sorted(db)}  (source {src})")

    print(bar)
    with open(ROOT / "status_enum_drift_report.json", "w", encoding="utf-8") as _f:
        json.dump({"validator": "status_enum_drift",
                   "checked": [{"key": k, "column": c} for k, c in CHECKED],
                   "failures": failures, "passed": not failures}, _f, indent=2)
    if failures:
        print(f"\033[91mFAIL\033[0m  Status-enum drift guard ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        print("  Fix: align utils.js window.WH_STATUS_ENUMS with the canonical capture")
        print("  contract, OR update the contract if the DB enum legitimately changed.")
        return 1
    print(f"\033[92mOK\033[0m  Status-enum source of truth in sync with the canonical DB enum.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
