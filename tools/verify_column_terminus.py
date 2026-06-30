"""
verify_column_terminus -- LIVE second pass over the column-terminus map (§13).
=========================================================================================
mine_column_terminus.py produces a STATIC terminus map: each capture field bucketed
PERSISTED / PERSISTED? / AI_EDGE / TRANSIENT_UI / NO_TERMINUS / UNRESOLVED, and for the
direct-mapped PERSISTED set, a (table, column) pair extracted from `column: $('id')`.

This tool checks those (table, column) pairs against the REAL database schema
(`docker exec supabase_db_workhive psql` → information_schema.columns) and tags each:

  • db_confirmed     -- table.column exists exactly as the static map claimed. Strong:
                        the field DOES land in a real column (value-verifiable next).
  • column_in_other  -- the JS key is NOT a column of the claimed table but IS a unique
                        column of another written table → table auto-CORRECTED (the
                        "nearest persist" guess was wrong; the DB names the real owner).
  • ambiguous        -- the JS key matches a column in >1 table (incl. v_*_truth views) →
                        cannot resolve statically; needs the live round-trip.
  • key_not_a_column -- the JS object key is NOT any DB column. This is the
                        TRANSFORM-MAPPED-PAYLOAD case: the page passes the field through a
                        mapper (e.g. logbook `_assetToNode(asset)`) that RENAMES the key
                        before insert (a-type→key 'type'→ asset_nodes has no 'type';
                        f-downtime→key 'downtime'→ logbook.downtime_hours). The field IS
                        persisted, but the exact column needs the live round-trip — the
                        static key is not the terminus. Flagged, never asserted.

HONESTY: this does NOT value-verify (it does not submit a form and read the row back). It
verifies the TERMINUS exists in the schema. db_confirmed = "lands in a real column";
value-correctness is the final round-trip pass on the db_confirmed + ambiguous sets.

Requires the local Supabase DB container up. Falls back to a --schema-file <path> dump
(one `table|col,col,...` line per table) so it can run without docker.

Reads + rewrites column_terminus.json (adds `table_verified` per PERSISTED field +
a `schema_verification` summary block). Prints a console report.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CT = ROOT / "column_terminus.json"
CONTAINER = "supabase_db_workhive"
SCHEMA_SQL = ("select table_name, string_agg(column_name, ',' order by column_name) "
              "from information_schema.columns where table_schema='public' group by table_name;")


def load_schema() -> dict[str, set[str]]:
    """Return {table_or_view: {columns}} from the live DB (or --schema-file)."""
    if "--schema-file" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--schema-file") + 1])
        raw = path.read_text(encoding="utf-8")
    else:
        out = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-F", "|", "-c", SCHEMA_SQL],
            capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            print(f"  docker psql failed: {out.stderr.strip()[:200]}")
            print("  (start the DB container, or pass --schema-file <dump>)")
            raise SystemExit(2)
        raw = out.stdout
    schema: dict[str, set[str]] = {}
    for ln in raw.splitlines():
        ln = ln.strip()
        if "|" not in ln:
            continue
        t, cols = ln.split("|", 1)
        schema[t.strip()] = set(c.strip() for c in cols.split(","))
    return schema


def main() -> int:
    if not CT.exists():
        print("  column_terminus.json missing — run mine_column_terminus.py first")
        return 1
    schema = load_schema()
    d = json.loads(CT.read_text(encoding="utf-8"))
    persisted = [r for r in d["fields"] if r["bucket"] == "PERSISTED" and r.get("column")]

    # CONSERVATIVE: confirm the claimed (table, column) against the schema, or FLAG for the
    # live round-trip. NEVER mutate the table to a guessed owner — a generic key like 'type'
    # coincidentally matching an unrelated table's column (e.g. a-type→inventory_transactions.type,
    # when a-type is an asset field transform-mapped via _assetToNode) is the exact over-claim to
    # avoid. We only HINT candidate owners; the round-trip is the proof.
    tags = Counter()
    flags = []
    for r in persisted:
        col, tbl = r["column"], r.get("table")
        if tbl in schema and col in schema[tbl]:
            r["table_verified"] = "db_confirmed"   # the payload key IS a column of the written table
        else:
            owners = [t for t, c in schema.items() if col in c and not t.startswith("v_")]
            r["table_verified"] = "needs_round_trip"
            r["column_owner_hints"] = owners        # HINTS only — not asserted
            why = (f"key '{col}' not a column of claimed '{tbl}'"
                   if owners else f"key '{col}' is no base-table column (transform-mapped payload)")
            flags.append(f"{r['surface']}:{r['field']}  {why}; owners={owners or '—'}")
        tags[r["table_verified"]] += 1

    d["schema_verification"] = {
        "checked_pairs": len(persisted),
        "db_confirmed": tags["db_confirmed"],
        "needs_round_trip": tags["needs_round_trip"],
        "note": "db_confirmed = the payload key IS a real column of the written table "
                "(schema-consistent; the field lands in table.column). needs_round_trip = the "
                "static key did not match the claimed table (transform-mapped payload via a mapper "
                "like logbook _assetToNode, or a generic key) — the live round-trip names the exact "
                "column; we only HINT candidate owners, never assert them. This step verifies the "
                "TERMINUS exists; VALUE-correctness is the final round-trip pass.",
    }
    CT.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 80)
    print("  §13 COLUMN-TERMINUS — LIVE SCHEMA VERIFICATION of the direct-mapped PERSISTED set")
    print("=" * 80)
    print(f"\n  PERSISTED (direct column:field) pairs checked: {len(persisted)}")
    print(f"     db_confirmed (key IS a column of the written table): {tags['db_confirmed']}")
    print(f"     needs_round_trip (transform-mapped / generic key)  : {tags['needs_round_trip']}")
    if flags:
        print("\n  ── flagged for live round-trip (HINTS only, NOT asserted) ──")
        for f in flags:
            print(f"     {f}")
    print(f"\n  ✓ column_terminus.json updated with table_verified + schema_verification")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
