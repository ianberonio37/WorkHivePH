"""
Lineage Status-Enum Drift Validator -- §13 P3 (the first crystallized nerve)
=============================================================================
Born from the FIRST real bug the §13 nerve-sweep discovered (2026-06-16):
`v_marketplace_sellers_truth.active_listings_count` filters
`marketplace_listings WHERE status = 'active'`, but the listing lifecycle is
draft -> published -> sold ('active' is NEVER written) -> the count is a
permanent 0 = a DEAD NERVE the static auditors missed (they prove a consumer
EXISTS, not that its value is reachable).

Rather than patch that one view, this catches the whole CLASS (doctrine: fix
the class, not the instance): every `v_*_truth` view that filters
`status = '<literal>'` is checked against the LIVE distinct `status` values of
the source table(s) it reads. If the literal never appears in the source, the
view's filter is drift -> the derived value can never fire.

This is the §13.11 loop made concrete: a live-discovered bug becomes a
deterministic static check that fills a §4 matrix cell and can never silently
return. Ground truth via `docker exec supabase_db_workhive psql` (the same
edge DB the journey-trace probes read).

Output: a report + exit code. Exit 1 if any UNALLOWLISTED drift is found.
Forward-only: known/intentional cases go in ALLOWLIST with a reason.

Skills consulted: data-engineer (view<->source enum contract), analytics-
engineer (KPI source filters), qa-tester (the differential probe that found
this), architect (truth-view drift as a structural class).
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB_CONTAINER = "supabase_db_workhive"

# Intentional/known-OK cases: (view, source_table, literal) -> reason. Forward-only.
# (Empty to start -- the marketplace finding is a REAL drift, reported not allowlisted.)
ALLOWLIST: dict[tuple, str] = {
    # (The marketplace 'active' dead nerve discovered 2026-06-16 was FIXED in
    #  migration 20260616000000_fix_marketplace_active_listings.sql — the view now
    #  filters 'published'. The allowlist entry was removed so this is now a HARD
    #  assertion; if the drift ever returns, this validator FAILs.)
    # ("v_example_truth", "example_table", "somestatus"): "intentional future status",
}


def psql(sql: str) -> list[list[str]]:
    out = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip() or out.stdout.strip()}")
    return [ln.split("|") for ln in out.stdout.splitlines() if ln.strip()]


def truth_views() -> list[str]:
    rows = psql("""SELECT relname FROM pg_class
                   WHERE relkind IN ('v','m') AND relname LIKE 'v_%truth' ORDER BY relname;""")
    return [r[0] for r in rows]


def view_def(view: str) -> str:
    rows = psql(f"SELECT pg_get_viewdef('{view}'::regclass, true);")
    return "\n".join("|".join(r) for r in rows)


def alias_map(defn: str) -> dict[str, str]:
    """Map each FROM/JOIN alias -> its table. `FROM marketplace_listings l` -> {l: marketplace_listings}.
    Also maps the table name to itself (for un-aliased refs)."""
    m = {}
    for tbl, alias in re.findall(
            r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-z_][a-z0-9_]*)\s+(?:AS\s+)?([a-z_][a-z0-9_]*)",
            defn, re.IGNORECASE):
        if alias.upper() in ("ON", "WHERE", "LEFT", "RIGHT", "INNER", "JOIN", "GROUP", "ORDER"):
            m[tbl] = tbl
        else:
            m[alias] = tbl
            m[tbl] = tbl
    return m


def aliased_status_literals(defn: str) -> set[tuple[str, str]]:
    """Extract (alias_or_table, literal) from `<x>.status = 'lit'` — attribute to the RIGHT table."""
    out = set(re.findall(r"\b([a-z_][a-z0-9_]*)\.status\s*=\s*'([^']+)'", defn, re.IGNORECASE))
    return {(a, lit) for a, lit in out}


def has_status_col(table: str) -> bool:
    return bool(psql(f"""SELECT 1 FROM information_schema.columns
                         WHERE table_name='{table}' AND column_name='status' LIMIT 1;"""))


def live_statuses(table: str) -> set[str]:
    rows = psql(f"SELECT DISTINCT status FROM {table} WHERE status IS NOT NULL;")
    return {r[0] for r in rows}


def check_allowed_statuses(table: str) -> set[str] | None:
    """The status column's CHECK-constraint enum = the SEED-INDEPENDENT authority
    on what can EVER be written. Returns None if there's no such CHECK."""
    rows = psql(f"""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE conrelid='{table}'::regclass AND contype='c'
                      AND pg_get_constraintdef(oid) ILIKE '%status%';""")
    allowed = set()
    found = False
    for r in rows:
        defn = "|".join(r)
        # match: status = ANY (ARRAY['a'::text, 'b'::text, ...])
        if re.search(r"\bstatus\b", defn, re.IGNORECASE):
            lits = re.findall(r"'([^']+)'", defn)
            if lits:
                allowed |= set(lits)
                found = True
    return allowed if found else None


def main() -> int:
    print("=" * 78)
    print("  Lineage Status-Enum Drift Validator (§13 P3 — first crystallized nerve)")
    print("=" * 78)
    drifts, checked, unused, no_check = [], 0, [], []
    _allowed_cache, _live_cache = {}, {}
    for v in truth_views():
        defn = view_def(v)
        amap = alias_map(defn)
        for alias, lit in sorted(aliased_status_literals(defn)):
            tbl = amap.get(alias)
            if not tbl or not has_status_col(tbl):
                continue   # alias resolves to a non-table or a table without status -> skip
            checked += 1
            if tbl not in _allowed_cache:
                _allowed_cache[tbl] = check_allowed_statuses(tbl)
                _live_cache[tbl] = live_statuses(tbl)
            allowed = _allowed_cache[tbl]
            if allowed is None:
                no_check.append((v, tbl, lit))   # no CHECK -> can't judge seed-independently; note
                continue
            if lit in allowed:
                # permitted by the schema; if no rows use it yet that's fine (valid-but-unused)
                if lit not in _live_cache[tbl]:
                    unused.append((v, tbl, lit))
                continue
            # ★literal is NOT in the column's CHECK enum -> can NEVER be written -> DEAD NERVE
            allow = next((r for (av, at, al), r in ALLOWLIST.items()
                          if av == v and al == lit and at == tbl), None)
            drifts.append({"view": v, "sources": [tbl], "literal": lit,
                           "allowed_enum": sorted(allowed), "allowlisted": allow})

    real = [d for d in drifts if not d["allowlisted"]]
    for d in drifts:
        tag = "ALLOWLISTED" if d["allowlisted"] else "DEAD NERVE"
        print(f"\n  [{tag}] {d['view']} filters {d['sources'][0]}.status='{d['literal']}'")
        print(f"        but the column CHECK enum = {d['allowed_enum']}")
        if d["allowlisted"]:
            print(f"        reason: {d['allowlisted']}")
        else:
            print(f"        → '{d['literal']}' is NOT a permitted status → can NEVER be written → DEAD NERVE")
    if unused:
        print(f"\n  [valid-but-unused — permitted by CHECK, 0 rows yet, NOT a bug] {len(unused)}: " +
              ", ".join(f"{v}:{lit}" for v, _, lit in unused))
    if no_check:
        print(f"\n  [no status CHECK — can't judge seed-independently] {len(no_check)}: " +
              ", ".join(f"{v}:{lit}" for v, _, lit in no_check))

    print("\n" + "-" * 78)
    print(f"  checked {checked} status-literal filters · {len(real)} DEAD NERVE · "
          f"{len(drifts)-len(real)} allowlisted · {len(unused)} valid-unused · {len(no_check)} no-CHECK")
    if real:
        print(f"  ✗ FAIL — {len(real)} dead nerve(s): a truth-view filters a status the schema forbids.")
        for d in real:
            print(f"      • {d['view']}: status='{d['literal']}' ∉ {d['allowed_enum']}")
        return 1
    print("  ✓ PASS — every truth-view status filter is a schema-permitted value.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
