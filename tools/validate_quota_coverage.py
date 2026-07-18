#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D12
"""validate_quota_coverage.py — FREE_TIER_QUOTA_ROADMAP Q2/Q5 breadth ratchet.

Q0 (validate_logbook_quota.py) proves the logbook pilot DEEP. This gate proves BREADTH:
every high-write table has a per-day insert cap, and each cap counts on a timestamp column
that ACTUALLY EXISTS on that table. It is the Q5 ratchet — it FAILs if a new high-write
table ships without a cap, so "free but bounded" can never silently regress.

Two teeth:
  1. COVERAGE — each REQUIRED table must have a BEFORE INSERT trigger calling a per-day cap
     fn (check_logbook_rate_limit for logbook, check_daily_row_cap for the Q2 tables).
  2. PHANTOM-COLUMN GUARD — the timestamp column passed to check_daily_row_cap('cap','<ts>',…)
     must be a real column of that table's CREATE TABLE. This generically catches the class of
     bug that broke the old triggers (a trigger counting on a column the table doesn't have,
     e.g. pm_completions has completed_at, NOT created_at).

USAGE:      python tools/validate_quota_coverage.py
Self-test:  python tools/validate_quota_coverage.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"
RST = "\033[0m"

# High-write tables that MUST be bounded by a per-day cap. logbook uses its bespoke Q0 fn;
# the rest use the generic Q2 check_daily_row_cap. (checklist_records is NOT here — it is a
# phantom table name with zero CREATE TABLE in any migration.)
REQUIRED = [
    "logbook", "inventory_transactions", "inventory_items",
    "pm_completions", "community_posts", "community_replies", "asset_nodes",
    "pdf_jobs",  # Q4: file-ingest is the most expensive write (embeds every chunk)
    # Full write-surface audit (2026-07-05): the previously-uncovered user-content tables.
    "projects", "project_items", "project_links", "project_progress_logs",
    "project_change_orders", "engineering_calcs", "resume_documents",
    "schedule_items", "skill_exam_attempts", "resume_versions",
    "pm_assets", "pm_scope_items", "fault_knowledge", "skill_badges",
    # Per-page audit gaps (2026-07-05): feature-page writes the table audit missed.
    "alert_dismissals", "community_reactions", "early_access_emails",
    "marketplace_watchlist", "report_contacts",
]


def _all_migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(MIGRATIONS.glob("*.sql"))
    )


def table_columns(text: str, tbl: str) -> set[str]:
    """Columns declared in the CREATE TABLE for `tbl` (files = schema truth).

    DROP-AWARE: replays DDL order. If the LAST DDL touching `tbl` is a DROP TABLE
    (no re-CREATE after it), the table does not exist -> return empty. This is the
    guard the live apply taught us: the baseline created `assets`, but 20260512000009
    dropped it (→ asset_nodes), so a CREATE-only scan wrongly reported it coverable.
    """
    # Schema prefix is OPTIONAL: some migrations write `CREATE TABLE projects (`
    # (no public.), others `CREATE TABLE public."projects" (`.
    pfx = r'(?:"?public"?\.)?"?'
    create_pat = re.compile(r'CREATE TABLE (?:IF NOT EXISTS )?' + pfx + re.escape(tbl) + r'"?\s*\(', re.I)
    drop_pat = re.compile(r'DROP TABLE (?:IF EXISTS )?' + pfx + re.escape(tbl) + r'"?\b', re.I)
    last_create = max((m.start() for m in create_pat.finditer(text)), default=-1)
    last_drop = max((m.start() for m in drop_pat.finditer(text)), default=-1)
    if last_create < 0 or last_drop > last_create:
        return set()  # never created, or dropped after its last create

    m = re.search(
        r'CREATE TABLE (?:IF NOT EXISTS )?' + pfx + re.escape(tbl) + r'"?\s*\((.*?)\n\)\s*;',
        text[last_create:], re.S)
    if not m:
        return set()
    # Handle BOTH column styles: baseline uses quoted `"id" "uuid"`, hand-written
    # migrations (e.g. asset_nodes) use unquoted `id uuid`. Skip constraint / CHECK
    # continuation lines so they aren't mistaken for columns.
    SKIP = {"constraint", "primary", "foreign", "unique", "check", "exclude", "like"}
    cols = set()
    for ln in m.group(1).splitlines():
        cm = re.match(r'\s*"?(\w+)"?\s+\S', ln)
        if cm and cm.group(1).lower() not in SKIP:
            cols.add(cm.group(1))
    return cols


def evaluate(text: str) -> list[tuple[str, bool, str]]:
    """Return [(table, covered, detail)] for each REQUIRED table."""
    rows: list[tuple[str, bool, str]] = []
    for tbl in REQUIRED:
        cols = table_columns(text, tbl)
        if not cols:
            rows.append((tbl, False, "no CREATE TABLE found (phantom table?)"))
            continue

        if tbl == "logbook":
            covered = bool(re.search(
                r"CREATE\s+TRIGGER\s+\w+\s+BEFORE\s+INSERT\s+ON\s+public\.logbook\s+FOR\s+EACH\s+ROW\s+EXECUTE\s+FUNCTION\s+public\.check_logbook_rate_limit",
                text, re.I | re.S))
            rows.append((tbl, covered,
                         "per-day cap via check_logbook_rate_limit (Q0)" if covered else "MISSING per-day cap trigger"))
            continue

        # Q2 generic: CREATE TRIGGER ... BEFORE INSERT ON public.<tbl> ... check_daily_row_cap('cap','<ts>',...)
        m = re.search(
            r"CREATE\s+TRIGGER\s+\w+\s+BEFORE\s+INSERT\s+ON\s+public\." + re.escape(tbl) +
            r"\s+FOR\s+EACH\s+ROW\s+EXECUTE\s+FUNCTION\s+public\.check_daily_row_cap\s*\(\s*'(\d+)'\s*,\s*'(\w+)'",
            text, re.I | re.S)
        if not m:
            rows.append((tbl, False, "MISSING per-day cap trigger (check_daily_row_cap)"))
            continue
        cap, ts_col = m.group(1), m.group(2)
        if ts_col not in cols:
            rows.append((tbl, False,
                         f"PHANTOM timestamp column '{ts_col}' not in {tbl} (would break INSERT)"))
            continue
        rows.append((tbl, True, f"per-day cap {cap}/hive on real column '{ts_col}'"))
    return rows


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    text = _all_migrations_text()
    rows = evaluate(text)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q2/Q5 — per-day cap coverage (every high-write table bounded)")
    print("=" * 74)
    covered = sum(1 for _, ok, _ in rows if ok)
    for tbl, ok, detail in rows:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {tbl:24s} {detail}")
    print(f"\n  coverage: {covered}/{len(rows)} high-write tables bounded")

    if self_test:
        # TEETH 1: a table with a trigger on a PHANTOM ts column must be flagged.
        synth = (
            'CREATE TABLE public.asset_nodes ("id" uuid, "hive_id" uuid, "made_at" timestamptz);\n'
            "CREATE TRIGGER trg_daily_cap_asset_nodes BEFORE INSERT ON public.asset_nodes "
            "FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('100','created_at','worker_name','50');"
        )
        rr = dict((t, ok) for t, ok, _ in evaluate(synth))
        guard_fires = rr.get("asset_nodes") is False  # 'created_at' not in the synthetic asset_nodes(made_at) table
        # TEETH 2: empty migrations => every table uncovered.
        empty_all_fail = all(not ok for _, ok, _ in evaluate(""))
        good = guard_fires and empty_all_fail
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] phantom-ts-guard:{guard_fires}  empty=all-fail:{empty_all_fail}")
        if not good:
            return 1

    missing = [t for t, ok, _ in rows if not ok]
    print()
    if missing:
        print(f"  {RED}FAIL{RST} — {len(missing)} high-write table(s) without a per-day cap: {', '.join(missing)}")
        return 1
    print(f"  {GREEN}PASS{RST} — all {len(rows)} high-write tables have a per-day cap on a real timestamp column")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
