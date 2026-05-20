"""
Query Column Existence Validator (L0, ratcheted).
===================================================
Every column name passed to `.select(...)`, `.eq()`, `.neq()`, `.in()`,
`.gt()`, `.gte()`, `.lt()`, `.lte()`, `.order()`, `.is()` on a known
table or view MUST be a real column of that table/view.

Catches: db.from('asset_nodes').select('asset_id, tag') — when asset_id
no longer exists on asset_nodes, postgrest returns 400 but the page
typically swallows the error in a catch and shows empty state.

Output: query_column_existence_report.json. Exit 1 on regression.
Allow with `// query-col-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "query_column_existence_report.json"
BASELINE_PATH = ROOT / "query_column_existence_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# Aliases and ambient columns that don't need to exist on the table.
UNIVERSAL_COLUMNS = {
    "id", "created_at", "updated_at", "inserted_at", "deleted_at",
    "user_id", "auth_uid", "hive_id",
}

# .from('table').select('a,b:c,d') — capture table + projection string.
# We do this in two passes: locate .from(), then scan forward for .select(.
FROM_RE = re.compile(r"""\.from\(\s*['"`](?P<name>[a-z_][\w]*)['"`]\s*\)""")
SELECT_PAT = re.compile(r"""\.select\(\s*['"`](?P<cols>[^'"`]{1,800})['"`]""")
# Filters .eq('col', ...), .neq('col', ...), .in('col', [...]), etc.
FILTER_PAT = re.compile(
    r"""\.(?:eq|neq|in|gt|gte|lt|lte|is|like|ilike|contains|containedBy|order)\(\s*['"`](?P<col>[a-z_][\w]*)['"`]"""
)
ALLOW_RE = re.compile(r"query-col-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _parse_projection(s: str) -> set[str]:
    """Extract column names from a `.select('a, alias:b, foo(...)')` projection.
    Skip wildcard '*' and DROP relation-expansion tokens (`rel_name(col,col2)`)
    entirely — the `rel_name` is a foreign-table reference, not a column of
    the current table. Caught false positive 2026-05-20 on
    `pm_completions.select('... pm_assets(asset_name), pm_scope_items(item_text)')`."""
    if "*" in s:
        return set()
    # FIRST drop any `identifier(args)` — both the identifier AND the parens.
    cleaned = re.sub(r"\b[a-z_][\w]*\s*\([^)]*\)", "", s, flags=re.IGNORECASE)
    cols = set()
    for tok in cleaned.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" in tok:
            tok = tok.split(":", 1)[1].strip()
        tok = tok.strip("!").strip()
        m = re.match(r"^([a-z_][\w]*)", tok, re.IGNORECASE)
        if m:
            cols.add(m.group(1).lower())
    return cols


def _load_registry() -> dict[str, set[str]]:
    """Return {table_or_view_name → set_of_columns}. Includes VIEWS now that
    `mine_canonical_registry.py` parses CREATE VIEW AS SELECT projections
    into a view-columns list (2026-05-20)."""
    reg = json.loads((ROOT / "canonical_registry.json").read_text(encoding="utf-8"))
    cols: dict[str, set[str]] = {}
    for t, meta in reg.get("tables", {}).items():
        c = meta.get("columns", [])
        if isinstance(c, list):
            cols[t.lower()] = {x.lower() for x in c}
        elif isinstance(c, str):
            cols[t.lower()] = {x.strip().lower() for x in c.split(",") if x.strip()}
    for v, meta in reg.get("views", {}).items():
        c = meta.get("columns", [])
        if isinstance(c, list) and c:
            cols[v.lower()] = {x.lower() for x in c}
    return cols


# Sentinel binding: name the L2 test `test('query_column_existence: ...')` for coverage credit.
CHECK_NAMES = ["query_column_existence"]


def main() -> int:
    table_cols = _load_registry()

    per_file = []
    total_drift = 0
    total_calls = 0
    seen: set = set()

    files: list[tuple[str, Path]] = [(n, ROOT / n) for n in PAGES]
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))

    for name, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        issues = []

        # Chain boundary: a query chain ends at the next `.from(`, a `;`
        # statement terminator outside a string, or a closing brace at
        # column 0 (heuristic — keeps the chain reasonably bounded).
        chain_end_re = re.compile(r"""\.from\(|;\s*\n|^\s*\}""", re.MULTILINE)

        for m in FROM_RE.finditer(body):
            table = m.group("name").lower()
            total_calls += 1

            # Find the next chain-boundary; cap at 1200 chars.
            search_window = body[m.end(): m.end() + 1200]
            cend = chain_end_re.search(search_window)
            tail = search_window[:cend.start()] if cend else search_window

            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win): continue

            cols = table_cols.get(table)
            if cols is None:
                continue
            cols_full = cols | UNIVERSAL_COLUMNS

            # .select() projection — only the FIRST .select() in the chain
            sm = SELECT_PAT.search(tail)
            if sm:
                projected = _parse_projection(sm.group("cols"))
                for col in projected:
                    if col in cols_full: continue
                    key = (name, table, col, "select")
                    if key in seen: continue
                    seen.add(key)
                    issues.append({"table": table, "column": col, "kind": "select"})

            # Filter operators in the same chain
            for fm in FILTER_PAT.finditer(tail):
                col = fm.group("col").lower()
                if col in cols_full: continue
                key = (name, table, col, "filter")
                if key in seen: continue
                seen.add(key)
                issues.append({"table": table, "column": col, "kind": "filter"})

        per_file.append({"file": name, "issues": issues})
        total_drift += len(issues)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(per_file), "total_calls": total_calls,
                    "total_drift": total_drift, "baseline": baseline,
                    "tables_known": len(table_cols)},
        "per_file": per_file,
    }, indent=2), encoding="utf-8")

    print(f"\nQuery Column Existence Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(per_file)}")
    print(f"  tables known:     {len(table_cols)}")
    print(f"  .from() calls:    {total_calls}")
    print(f"  drift:            {total_drift}  (baseline: {baseline})")
    if total_drift == 0:
        print("\n  PASS — every queried column exists on its table/view.")
        return 0
    shown = 0
    for entry in per_file:
        if not entry["issues"]: continue
        print(f"  {entry['file']}")
        for i in entry["issues"]:
            print(f"    {i['kind']:7s}  from('{i['table']}').{i['kind']}('{i['column']}', ...)  — column doesn't exist")
            shown += 1
            if shown >= 40:
                print("    ... (more in report)")
                break
        if shown >= 40: break
    return 1 if total_drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
