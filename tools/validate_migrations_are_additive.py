#!/usr/bin/env python3
r"""migrations-additive - T199: a migration must not break the page already open.

Deploys happen while people are working. A worker who opened the logbook at 13:58 and
presses Save at 14:00 is running the OLD page JavaScript against the NEW schema, and
whether that write lands is decided entirely by whether the migration was ADDITIVE.

Adding a nullable column is invisible to the open page. Dropping a column, renaming one,
or making one NOT NULL without a default is not: the in-flight write fails, and it fails
at the worst possible moment - after the person has typed everything.

MEASURED across 561 migrations: only NINE non-additive operations exist in the entire
history, and every one is a deliberate, named cleanup from May-June 2026 - the Phase 5b/5c
retirement of the old `assets` model, four `drop_phantom_columns_*` migrations removing
columns that were never real, one NOT NULL on a benchmarks upsert, and the Stripe removal.
NONE since 2026-06-30.

THE ASSERTION is a forward-only ratchet with an allowlist, not a count: those nine files
are grandfathered BY NAME, and any OTHER migration containing a drop-column, drop-table,
rename-column or set-not-null fails. Naming them means the gate still fires if a new
non-additive migration appears even while an old one is deleted - a count would not.

★WHAT THIS DOES NOT CLAIM. It does not prove a deploy is safe: an additive migration can
still break an open page through a changed CHECK constraint or a trigger, and the
window-discipline question (deploy at PHT night, not 2pm on a workday) is a runbook
decision rather than a schema property. This catches the one class that is objectively
readable from the SQL.

Usage: python tools/validate_migrations_are_additive.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# Deliberate, named cleanups. Each retired something that was already dead; none ran against
# live in-flight writes from a page that still used the column.
GRANDFATHERED = {
    "20260512000007_phase_5b1_drop_logbook_asset_ref.sql":      "Phase 5b: old assets model retired",
    "20260512000008_phase_5b2_drop_inventory_linked_asset_ids.sql": "Phase 5b: same retirement",
    "20260512000009_phase_5c_drop_assets.sql":                   "Phase 5c: the assets table itself",
    "20260520000004_drop_phantom_columns_safe.sql":              "columns that were never real",
    "20260520000007_drop_phantom_columns_auth_tier.sql":         "columns that were never real",
    "20260520000008_drop_phantom_columns_transient.sql":         "columns that were never real",
    "20260520000009_drop_phantom_columns_seeder_only.sql":       "seeder-only columns",
    "20260618000000_fix_network_benchmarks_upsert.sql":          "NOT NULL to make an upsert key work",
    "20260630000000_remove_stripe_free_marketplace.sql":         "Stripe removed; marketplace is free",
}

DROP_COL = re.compile(r"ALTER\s+TABLE\s+[^;]*?DROP\s+COLUMN", re.I | re.S)
SET_NOT_NULL = re.compile(r"ALTER\s+TABLE\s+[^;]*?ALTER\s+COLUMN\s+\w+\s+SET\s+NOT\s+NULL", re.I | re.S)
RENAME_COL = re.compile(r"ALTER\s+TABLE\s+[^;]*?RENAME\s+COLUMN", re.I | re.S)
DROP_TABLE = re.compile(r"DROP\s+TABLE(?!\s+IF\s+EXISTS\s+\w*_?(tmp|temp|probe))", re.I)
KINDS = (("drop-column", DROP_COL), ("set-not-null", SET_NOT_NULL),
         ("rename-column", RENAME_COL), ("drop-table", DROP_TABLE))


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql")))
    if not files:
        print("SKIP migrations-additive - no migrations found")
        return 0

    offenders, grandfathered_seen = [], 0
    for f in files:
        name = Path(f).name
        sql = re.sub(r"--[^\n]*", "", io.open(f, encoding="utf-8", errors="replace").read())
        hits = [k for k, rx in KINDS if rx.search(sql)]
        if not hits:
            continue
        if name in GRANDFATHERED:
            grandfathered_seen += 1
            continue
        offenders.append(f"{name}: {', '.join(hits)}")

    print(f"  migrations: {len(files)} | non-additive: {len(offenders)} "
          f"| grandfathered cleanups still present: {grandfathered_seen}/{len(GRANDFATHERED)}")
    if offenders:
        print(f"FAIL migrations-additive - {len(offenders)} migration(s) can break a page already open:")
        for x in offenders[:10]:
            print("    - " + x)
        print("    A worker who opened the page at 13:58 and presses Save at 14:00 runs the OLD")
        print("    JavaScript against the NEW schema. Add a nullable column and they never notice;")
        print("    drop or rename one and their write fails after they typed everything. If the")
        print("    change is genuinely a retirement of something already dead, add it to")
        print("    GRANDFATHERED with the reason.")
        return 1
    print(f"PASS migrations-additive - every migration outside the {len(GRANDFATHERED)} named historical "
          f"cleanups is additive, so a deploy cannot fail a write that was already in flight.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
