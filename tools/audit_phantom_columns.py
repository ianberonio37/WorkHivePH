"""
Phantom DB Column Auditor (Layer -1.5 schema-bloat detector).
=============================================================

Sibling to `audit_phantom_captures.py` but at the DB schema layer.

For every column in every table registered in canonical_registry.json,
scan the codebase for read consumers (`.select('col')`, `.eq('col', ...)`,
SQL/RPC references, AI prompts injecting the column). Columns with ZERO
read consumers are phantoms — schema bloat ready for a `DROP COLUMN`
migration.

A phantom column can be exonerated by adding it to PHANTOM_COLUMN_ALLOW
below with a one-line reason (external system depends on it, regulatory
archival, partition-key required by an SQL extension, etc.).

Output:
  - phantom_columns_report.json
  - phantom_columns_report.md

Exit code:
  0 if no unjustified phantoms
  1 if at least one (CI gate)
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Always-allowed columns — Postgres / Supabase plumbing that's universally
# required even if no application code references them.
# ---------------------------------------------------------------------------

UNIVERSAL_COLUMNS = {
    "id", "created_at", "updated_at", "inserted_at", "deleted_at",
    "user_id", "auth_uid",  # framework FKs
    "hive_id",              # tenant key — read implicitly via RLS even if no app .select() mentions it
}

# Per-table allowlist: column -> reason. Edit this when a column is
# legitimately unused by application code (external systems, archival,
# trigger-only, materialized view backers, etc).
PHANTOM_COLUMN_ALLOW: dict[str, dict[str, str]] = {
    "asset_nodes": {
        "external_ids": "JSONB grab-bag for CMMS imports; consumed by integrations, queried dynamically",
    },
    "canonical_lineage_edges": {
        "target_kind": "edge graph just shipped 2026-05-20; auditor + future readers reference target_kind via comments only (comment-strip hides it). Real readers wire up as the contract matures.",
    },
    "canonical_sources": {
        "last_validated": "Written by validate_schema_phantom.py + future canonical-source validator runs. Allowlisted while the validator suite catches up to the column.",
    },
}


# ---------------------------------------------------------------------------
# Source files scanned for column consumers.
# ---------------------------------------------------------------------------

HTML_GLOB = "*.html"
JS_GLOB = "*.js"
SUPABASE_DIR = ROOT / "supabase"

EXCLUDED_HTML = [re.compile(r"\.backup\d*\.html$"), re.compile(r"-test\.html$")]


def _strip_sql_comments(text: str) -> str:
    # Drop /* ... */ block comments + `-- ...` line comments so a commented-
    # out DROP COLUMN (or a punch-list note in a DRAFT migration) doesn't
    # count as a real consumer of the column it mentions.
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"--[^\n]*", "", out)
    # Also strip ALTER TABLE ... DROP COLUMN ... statements — they MENTION
    # the column name but are removing it, not consuming it.
    out = re.sub(r"ALTER\s+TABLE\s+[\w\.]+\s+DROP\s+COLUMN(?:\s+IF\s+EXISTS)?\s+\w+\s*;",
                 "", out, flags=re.IGNORECASE)
    return out


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text)


def _strip_js_comments(text: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"^[ \t]*//[^\n]*$", "", out, flags=re.MULTILINE)
    return out


def _strip_py_comments(text: str) -> str:
    return re.sub(r"^[ \t]*#[^\n]*$", "", text, flags=re.MULTILINE)


def _gather_blobs() -> dict[str, str]:
    blobs: dict[str, str] = {}
    for p in sorted(ROOT.glob(HTML_GLOB)):
        if any(rx.search(p.name) for rx in EXCLUDED_HTML):
            continue
        blobs[p.name] = _strip_html_comments(p.read_text(encoding="utf-8", errors="replace"))
    for p in sorted(ROOT.glob(JS_GLOB)):
        if p.name == "sw.js":
            continue
        blobs[p.name] = _strip_js_comments(p.read_text(encoding="utf-8", errors="replace"))
    if SUPABASE_DIR.exists():
        for fn_dir in sorted((SUPABASE_DIR / "functions").glob("*")):
            if fn_dir.is_dir() and (fn_dir / "index.ts").exists():
                blobs[f"edge:{fn_dir.name}"] = _strip_js_comments(
                    (fn_dir / "index.ts").read_text(encoding="utf-8", errors="replace")
                )
        for m in sorted((SUPABASE_DIR / "migrations").glob("*.sql")):
            blobs[f"mig:{m.name}"] = _strip_sql_comments(m.read_text(encoding="utf-8", errors="replace"))
    for p in sorted(ROOT.glob("tools/*.py")):
        blobs[f"tools:{p.name}"] = _strip_py_comments(p.read_text(encoding="utf-8", errors="replace"))
    for p in sorted(ROOT.glob("python-api/**/*.py")):
        blobs[f"python-api:{p.relative_to(ROOT).as_posix()}"] = _strip_py_comments(
            p.read_text(encoding="utf-8", errors="replace")
        )
    return blobs


def _column_has_consumer(table: str, col: str, blobs: dict[str, str], own_migration: str) -> tuple[int, list[str]]:
    """A column `col` of table `table` has a consumer if its name appears in
    any non-migration file (or in a migration OTHER than its own DDL site).

    Word-boundary match: `(?<![A-Za-z0-9_])col(?![A-Za-z0-9_])`.
    """
    pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(col) + r"(?![A-Za-z0-9_])")
    consumers = []
    for fname, blob in blobs.items():
        if fname == f"mig:{own_migration}":
            # the column's own DDL site doesn't count
            continue
        if pat.search(blob):
            consumers.append(fname)
    return len(consumers), consumers[:8]


def main() -> int:
    reg_path = ROOT / "canonical_registry.json"
    if not reg_path.exists():
        print(f"FAIL: canonical_registry.json missing ({reg_path})")
        return 2
    registry = json.loads(reg_path.read_text(encoding="utf-8"))
    blobs = _gather_blobs()

    by_table: dict[str, dict] = {}
    grand_total_cols = 0
    grand_alive = 0
    grand_phantom = 0
    grand_universal = 0
    grand_allowlisted = 0

    for table, meta in sorted(registry["tables"].items()):
        # `columns` is either a list of column names OR a comma-string in
        # the truncated registry output. Be defensive.
        cols_raw = meta.get("columns")
        if isinstance(cols_raw, str):
            cols = [c.strip() for c in cols_raw.split(",") if c.strip()]
        elif isinstance(cols_raw, list):
            cols = list(cols_raw)
        else:
            cols = []
        if not cols:
            continue
        own_mig = meta.get("defined_in", "")

        col_rows = []
        for c in cols:
            grand_total_cols += 1
            if c in UNIVERSAL_COLUMNS:
                col_rows.append({"name": c, "status": "universal", "consumer_count": 0, "consumers": []})
                grand_universal += 1
                continue
            allow_reason = PHANTOM_COLUMN_ALLOW.get(table, {}).get(c)
            n_consumers, sample = _column_has_consumer(table, c, blobs, own_mig)
            if n_consumers == 0 and allow_reason:
                col_rows.append({
                    "name": c, "status": "allowlisted", "consumer_count": 0,
                    "consumers": [], "reason": allow_reason,
                })
                grand_allowlisted += 1
            elif n_consumers == 0:
                col_rows.append({"name": c, "status": "phantom", "consumer_count": 0, "consumers": []})
                grand_phantom += 1
            else:
                col_rows.append({"name": c, "status": "alive", "consumer_count": n_consumers, "consumers": sample})
                grand_alive += 1

        phantoms_here = [r for r in col_rows if r["status"] == "phantom"]
        by_table[table] = {
            "table":          table,
            "total_cols":     len(cols),
            "alive":          sum(1 for r in col_rows if r["status"] == "alive"),
            "phantom":        len(phantoms_here),
            "universal":      sum(1 for r in col_rows if r["status"] == "universal"),
            "allowlisted":    sum(1 for r in col_rows if r["status"] == "allowlisted"),
            "phantom_names":  [r["name"] for r in phantoms_here],
            "columns":        col_rows,
        }

    report = {
        "summary": {
            "tables_scanned":    len(by_table),
            "total_columns":     grand_total_cols,
            "alive":             grand_alive,
            "phantom":           grand_phantom,
            "universal_skipped": grand_universal,
            "allowlisted":       grand_allowlisted,
        },
        "by_table": by_table,
    }

    (ROOT / "phantom_columns_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ── Markdown report ───────────────────────────────────────────────
    md = []
    md.append("# Phantom Column Audit (Layer -1.5 schema-bloat detector)\n")
    md.append("Every column in canonical_registry.json with ZERO downstream consumers.")
    md.append("Run by `tools/audit_phantom_columns.py`. Output is a `DROP COLUMN`")
    md.append("candidates punch list. Allowlist a column by adding it to")
    md.append("`PHANTOM_COLUMN_ALLOW` in the auditor source with a reason.\n")

    s = report["summary"]
    md.append("## Summary\n")
    md.append(f"- Tables scanned:           **{s['tables_scanned']}**")
    md.append(f"- Total columns:            **{s['total_columns']}**")
    md.append(f"- Alive (consumed):         **{s['alive']}** ✅")
    md.append(f"- Universal-skipped:        **{s['universal_skipped']}** (id, created_at, hive_id, ...)")
    md.append(f"- Allowlisted phantoms:     **{s['allowlisted']}**")
    md.append(f"- Phantom (deletion cand):  **{s['phantom']}** ❌")
    md.append("")

    # Tables with phantom columns
    tables_with_phantoms = sorted(
        [t for t in by_table.values() if t["phantom"] > 0],
        key=lambda t: -t["phantom"],
    )
    md.append(f"## Tables with phantom columns ({len(tables_with_phantoms)})\n")
    if not tables_with_phantoms:
        md.append("_None — every non-universal column has at least one consumer._\n")
    else:
        md.append("| Table | Phantom cols | Phantom column names |")
        md.append("|---|---:|---|")
        for t in tables_with_phantoms:
            names = ", ".join(f"`{n}`" for n in t["phantom_names"][:10])
            if len(t["phantom_names"]) > 10:
                names += f", ... +{len(t['phantom_names']) - 10} more"
            md.append(f"| `{t['table']}` | {t['phantom']} | {names} |")
        md.append("")

    md.append("## What to do with a phantom column\n")
    md.append("1. **DROP it** — write a follow-up migration `ALTER TABLE T DROP COLUMN c;`. Safe move.")
    md.append("2. **Justify it** — add an entry to `PHANTOM_COLUMN_ALLOW` in the auditor source")
    md.append("   with a one-line reason (external system, archival, trigger-only).")
    md.append("3. **Wire a consumer** — if the column should be read by a surface or edge fn,")
    md.append("   add the read site. The next run reclassifies as alive.")

    (ROOT / "phantom_columns_report.md").write_text("\n".join(md), encoding="utf-8")

    # ── stdout banner ─────────────────────────────────────────────────
    print("Phantom Column Audit (Layer -1.5 schema-bloat detector)")
    print(f"  tables scanned: {s['tables_scanned']}")
    print(f"  total columns:  {s['total_columns']}")
    print(f"  alive:          {s['alive']}")
    print(f"  universal:      {s['universal_skipped']}")
    print(f"  allowlisted:    {s['allowlisted']}")
    print(f"  phantom:        {s['phantom']}")
    print()
    if tables_with_phantoms:
        print("Tables with phantom columns:")
        for t in tables_with_phantoms[:10]:
            print(f"  {t['table']:<32} {t['phantom']:>3} phantom: {', '.join(t['phantom_names'][:5])}")

    return 1 if grand_phantom > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
