#!/usr/bin/env python3
"""validate_dedup_constraints.py - Arc S (Resilience/DR) C-lens cell `dedup_constraints`.
================================================================================
Exactly-once on retries (C floor = 100): every dedup-prone write path must have a
DATABASE-LEVEL UNIQUE guard, so a double-submit / network-retry collapses to one
row instead of creating a phantom duplicate. Client-side button-disable has a race
window and is NOT sufficient (validate_idempotency flagged pm_completions WARN;
Arc S promotes it to a hard constraint).

For each dedup-prone (table, required-columns) the gate asserts a UNIQUE index OR
constraint exists across supabase/migrations covering those columns, AND (where the
write is a client .insert) that the page treats a 23505 unique_violation as benign
(an .upsert/onConflict OR an explicit `code === '23505'` branch) instead of a scary
"failed" toast.

Exit 0 = every dedup-prone path is DB-guarded (+ client-graceful); 1 = a gap remains.
Local-first, file-static, stdlib only, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "supabase" / "migrations"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# (table, [required cols all present in one UNIQUE index/constraint], client page or None)
DEDUP_PATHS = [
    ("pm_completions",     ["scope_item_id", "worker_name", "completed_at"], "pm-scheduler.html"),
    ("project_links",      ["project_id", "link_type", "link_id"],           "project-manager.html"),
    # Arc S C-lens depth (2026-07-20): the parts-staging accept fired an unguarded insert in parallel with a
    # guarded status-update — a double-accept (offline-retry/timeout/2nd device past the button-disable) made
    # duplicate reservations. Fixed: UNIQUE(recommendation_id,item_id) mig 20260720000001 + client upsert-ignore.
    ("parts_staged_reservations", ["recommendation_id", "item_id"],          "asset-hub.html"),
]


def _all_migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    out = []
    for p in sorted(MIGRATIONS.glob("*.sql")):
        try:
            out.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return "\n".join(out)


def _has_unique_over(sql: str, table: str, cols: list[str]) -> bool:
    """A UNIQUE index or constraint on `table` whose body references every col in `cols`."""
    # Match CREATE [UNIQUE] INDEX ... ON <table> ( ... ) [WHERE ...]; up to the statement end.
    for m in re.finditer(
        rf"CREATE\s+UNIQUE\s+INDEX[^;]*\bON\s+(?:public\.)?{re.escape(table)}\b([^;]*);",
        sql, re.IGNORECASE):
        body = m.group(1).lower()
        if all(c.lower() in body for c in cols):
            return True
    # Inline / ALTER TABLE ADD CONSTRAINT ... UNIQUE (...) and column-level UNIQUE.
    for m in re.finditer(
        rf"(?:ADD\s+CONSTRAINT[^;]*UNIQUE|CONSTRAINT[^;]*UNIQUE|\bUNIQUE\b)\s*\(([^)]*)\)",
        sql, re.IGNORECASE):
        body = m.group(1).lower()
        if all(c.lower() in body for c in cols):
            # cheap proximity guard: the table name should appear before this UNIQUE
            pre = sql[:m.start()].lower()
            if table.lower() in pre[-4000:]:
                return True
    # Single-column column-level UNIQUE (e.g. `stripe_session_id text UNIQUE`).
    if len(cols) == 1:
        if re.search(rf"\b{re.escape(cols[0])}\b[^,;\n]*\bUNIQUE\b", sql, re.IGNORECASE):
            return True
    return False


def _client_graceful(page: str) -> bool:
    p = ROOT / page
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return ("23505" in t) or bool(re.search(r"\.upsert\(", t))


def main() -> int:
    print(f"{B}Arc S - dedup constraints (C-lens, exactly-once){X}")
    print("=" * 60)
    sql = _all_migrations_text()
    issues = []
    for table, cols, page in DEDUP_PATHS:
        db_ok = _has_unique_over(sql, table, cols)
        cli_ok = True if page is None else _client_graceful(page)
        status = G + "PASS" + X if (db_ok and cli_ok) else R + "FAIL" + X
        detail = []
        if not db_ok:
            detail.append(f"no UNIQUE over ({', '.join(cols)})")
        if not cli_ok:
            detail.append(f"{page} does not handle 23505 / upsert")
        print(f"  {status}  {table:<20} {'· '.join(detail) if detail else 'DB-guarded' + ('' if page is None else ' + client-graceful')}")
        if detail:
            issues.append((table, detail))

    if issues:
        print(f"\n{R}{B}  DEDUP: FAIL{X} - {len(issues)} dedup-prone path(s) unguarded.")
        return 1
    print(f"\n{G}{B}  DEDUP: PASS{X} - every dedup-prone write has a DB UNIQUE guard + graceful client.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
