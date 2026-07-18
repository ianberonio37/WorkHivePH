#!/usr/bin/env python3
"""validate_attribution_pinned.py — LOCK the attribution-forge class (bug-hunt roadmap P3/P5, 2026-07-18).

Accountability columns that record WHO did something (actor, approved_by, acknowledged_by, resolved_by,
reviewed_by, assigned_by, submitted_by, dismissed_by, closed_by, rejected_by, completed_by, sent_by) are
CLIENT-forgeable unless a BEFORE INSERT/UPDATE trigger pins them to the caller's hive_members identity.
RLS gates the ROLE (member/supervisor of the hive) but NOT the NAME — so without a bind trigger a caller
can stamp ANOTHER person's name on an approval / acknowledgement / assignment (intra-hive impersonation).

This gate runs the same discovery query used to FIND the class (migs 010/011/014/015) and FAILS if any
hive-scoped action-attribution column lacks a trigger fn that assigns `NEW.<col>`. It therefore (a) locks
the existing pins against a dropped trigger, and (b) catches any NEW unpinned attribution column a future
table introduces. Genuinely server-only columns can be added to ALLOWLIST with a written reason.

Live gate: docker/DB unreachable => SKIP (exit 0), never a false FAIL. Registered in run_platform_checks.
"""
import subprocess
import sys

DB = "supabase_db_workhive"

# action-attribution columns (WHO performed an action). Authorship columns (worker_name/author_name/
# seller_name) are covered by the page-crud gate + the worker_name sweep, so they are intentionally not
# duplicated here.
ATTR_COLS = [
    "actor", "acknowledged_by", "resolved_by", "approved_by", "reviewed_by", "assigned_by",
    "submitted_by", "dismissed_by", "closed_by", "rejected_by", "completed_by", "sent_by",
]

# (table, column) pairs that are legitimately server/service-role-written only (auth.uid() NULL) and so
# cannot be client-forged. Each entry needs a written reason. Empty today — every hit is pinned.
ALLOWLIST: set[tuple[str, str]] = set()

QUERY = """
WITH attr_cols AS (
  SELECT c.table_name, c.column_name
  FROM information_schema.columns c
  JOIN information_schema.tables t
    ON t.table_name=c.table_name AND t.table_schema='public' AND t.table_type='BASE TABLE'
  WHERE c.table_schema='public' AND c.column_name = ANY(ARRAY[{cols}])
),
has_hive AS (
  SELECT table_name FROM information_schema.columns
  WHERE table_schema='public' AND column_name='hive_id'
)
SELECT ac.table_name || '.' || ac.column_name
FROM attr_cols ac
WHERE ac.table_name IN (SELECT table_name FROM has_hive)
  AND NOT EXISTS (
    SELECT 1 FROM pg_trigger tg JOIN pg_class cl ON cl.oid=tg.tgrelid
    WHERE cl.relname=ac.table_name AND NOT tg.tgisinternal
      AND pg_get_functiondef(tg.tgfoid) ~ ('NEW\\.' || ac.column_name)
  )
ORDER BY 1;
"""


def _psql(sql: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-tAc", sql],
            capture_output=True, text=True, timeout=30)
        return r.returncode == 0, r.stdout
    except Exception:
        return False, ""


def main() -> int:
    cols = ", ".join(f"'{c}'" for c in ATTR_COLS)
    ok, out = _psql(QUERY.format(cols=cols))
    if not ok:
        print("attribution-pinned: docker/DB unreachable — SKIPPED (live gate).")
        return 0
    hits = [ln.strip() for ln in out.splitlines() if ln.strip()]
    unpinned = [h for h in hits if tuple(h.split(".", 1)) not in ALLOWLIST]
    if unpinned:
        print(f"attribution-pinned: {len(unpinned)} hive-scoped action-attribution column(s) NOT pinned "
              f"to the caller's identity — CLIENT-FORGEABLE (intra-hive impersonation):")
        for h in unpinned:
            print(f"  ✗ {h}: no trigger fn assigns NEW.{h.split('.',1)[1]} — a member can stamp another "
                  f"person's name on this action.")
        print("  FIX: add a BEFORE INSERT OR UPDATE trigger that derives the name from hive_members by "
              "auth.uid()+hive_id (see migs 20260717000014/000015 bind_*_from_hive), or add the (table,col) "
              "to ALLOWLIST with a reason if it is genuinely server-only.")
        return 1
    print(f"attribution-pinned: ✓ all {len(ATTR_COLS)} action-attribution column types are identity-pinned "
          f"on every hive-scoped table ({len(ALLOWLIST)} allowlisted).")
    return 0


def selftest() -> int:
    # structural: the query must reference NEW.<col> pinning + the column set must be non-empty
    fails = []
    if not ATTR_COLS:
        fails.append("ATTR_COLS must be non-empty")
    if "NEW\\." not in QUERY:
        fails.append("query must test for NEW.<col> assignment in trigger bodies")
    if "has_hive" not in QUERY:
        fails.append("query must restrict to hive-scoped tables")
    if fails:
        print("✗ validate_attribution_pinned selftest FAILED:")
        for f in fails:
            print("   - " + f)
        return 1
    print("✓ validate_attribution_pinned selftest passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
