"""
Cross-Migration Table-Collision Auditor (Layer -1 static).
==========================================================
Catches the class of bug that took 4 migration patches to fix on
2026-05-20: two migrations both `CREATE TABLE IF NOT EXISTS <name>`
with INCOMPATIBLE columns. The IF NOT EXISTS silently skips the later
declaration; subsequent indexes / RLS / view / RPCs reference columns
that don't exist; `supabase migration up` aborts mid-file, blocking
every downstream migration.

The static validator pattern checks file shape, not deployed schema.
This auditor surfaces collisions at the static layer so they're caught
before they ever hit a `supabase migration up`.

Detection logic
  1. Walk every supabase/migrations/*.sql.
  2. For each `CREATE TABLE [IF NOT EXISTS] public.<name>` or
     `create table [if not exists] <name>`, capture the column set.
  3. If the same table name appears in 2+ migrations with DIFFERENT
     column sets, flag as a collision.
  4. A migration that ONLY does `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
     against an existing table is NOT a collision — additive evolution
     is the documented self-heal pattern.

Allow markers
  Add `-- table-collision-allow: <reason>` on the CREATE TABLE line or
  the line above to document an intentional redeclaration (e.g. when
  the later migration is the self-heal that's KNOWN to ship after the
  older one).

Output
  table_collision_report.json    machine-readable
  Exit 1 when any unallowed collision is detected; 0 otherwise.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
MIG_DIR = ROOT / "supabase" / "migrations"

CREATE_TABLE_RE = re.compile(
    r"""
    create\s+table\s+
    (?:if\s+not\s+exists\s+)?
    (?:public\.)?
    (?P<name>[a-z_][\w]*)
    \s*\(
    (?P<body>[^;]*?)
    \)\s*;
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
COLUMN_RE = re.compile(
    r"^\s*(?P<col>[a-z_][\w]*)\s+[a-z]",
    re.IGNORECASE | re.MULTILINE,
)
ALLOW_RE = re.compile(r"table-collision-allow:\s*(?P<reason>.+)", re.IGNORECASE)


def _extract_columns(body: str) -> set[str]:
    """Pull bare column names out of a CREATE TABLE body. Skips constraints
    (`primary key`, `unique`, `check`, `foreign key`, `constraint`) and
    whitespace/comments — anything where the first token is a known SQL
    keyword instead of a column name."""
    SKIP_FIRST_TOKEN = {"primary", "unique", "check", "foreign", "constraint",
                        "exclude", "like"}
    cols: set[str] = set()
    for raw in body.split(","):
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        m = COLUMN_RE.match(line)
        if not m:
            continue
        c = m.group("col").lower()
        if c in SKIP_FIRST_TOKEN:
            continue
        cols.add(c)
    return cols


def _scan(mig: Path) -> list[dict]:
    out: list[dict] = []
    try:
        text = mig.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for m in CREATE_TABLE_RE.finditer(text):
        name = m.group("name").lower()
        body = m.group("body")
        cols = _extract_columns(body)
        # Look for an allow marker on the CREATE TABLE line or up to 4
        # lines above (lets the comment include a 2-3 line explanation).
        start = m.start()
        cursor = start
        for _ in range(4):
            prev = text.rfind("\n", 0, max(0, cursor - 1))
            if prev < 0:
                cursor = 0
                break
            cursor = prev
        window = text[cursor:m.end()].lower()
        allow_match = ALLOW_RE.search(window)
        out.append({
            "file":    str(mig.relative_to(ROOT)).replace("\\", "/"),
            "table":   name,
            "columns": sorted(cols),
            "allow":   allow_match.group("reason").strip() if allow_match else None,
        })
    return out


def main() -> int:
    if not MIG_DIR.exists():
        print(f"FAIL: {MIG_DIR} missing")
        return 2

    decls: dict[str, list[dict]] = {}
    for mig in sorted(MIG_DIR.glob("*.sql")):
        for entry in _scan(mig):
            decls.setdefault(entry["table"], []).append(entry)

    collisions = []
    for table, entries in decls.items():
        if len(entries) < 2:
            continue
        # Compare column sets pairwise. If they differ AND there's no
        # allow marker on the later declaration(s), it's a collision.
        baseline = set(entries[0]["columns"])
        for later in entries[1:]:
            cur = set(later["columns"])
            if cur != baseline:
                if later.get("allow"):
                    continue
                collisions.append({
                    "table":          table,
                    "first":          {
                        "file":    entries[0]["file"],
                        "columns": entries[0]["columns"],
                    },
                    "later":          {
                        "file":    later["file"],
                        "columns": later["columns"],
                    },
                    "first_only":     sorted(baseline - cur),
                    "later_only":     sorted(cur - baseline),
                })

    report = {
        "summary": {
            "tables_scanned":   len(decls),
            "tables_redeclared": sum(1 for e in decls.values() if len(e) >= 2),
            "collisions":       len(collisions),
        },
        "collisions": collisions,
    }
    (ROOT / "table_collision_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Cross-Migration Table-Collision Auditor")
    print(f"  tables scanned:    {report['summary']['tables_scanned']}")
    print(f"  tables redeclared: {report['summary']['tables_redeclared']}")
    print(f"  collisions:        {report['summary']['collisions']}")
    if collisions:
        print()
        for c in collisions[:10]:
            print(f"  COLLISION on `{c['table']}`:")
            print(f"     {c['first']['file']}  columns only here: {c['first_only']}")
            print(f"     {c['later']['file']}  columns only here: {c['later_only']}")
            print(f"     fix options: (1) edit later migration to be self-healing")
            print(f"                  (2) add `-- table-collision-allow: <reason>` on the CREATE TABLE line")
            print()
    return 1 if collisions else 0


if __name__ == "__main__":
    sys.exit(main())
