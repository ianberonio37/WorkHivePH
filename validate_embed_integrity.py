"""
PostgREST Embed Integrity Detector -- WorkHive Platform
========================================================
Sister gate to validate_schema_phantom.py. Phantom-columns catches scalar
columns that don't exist; this catches PostgREST EMBEDS (relationship-traversal
shapes) that don't resolve.

Why it matters: PostgREST embeds let JS/edge code traverse a foreign key in
one query, e.g. `db.from('inventory_transactions').select('qty_change,
item:inventory_items(part_name)')`. When the embed cannot resolve --
because the embedded table doesn't exist, a column inside the embed doesn't
exist, or no FK relationship connects the two tables -- the result silently
returns null for that nested object. The caller renders empty/wrong data
without ever seeing an error.

Layer 1 -- Phantom embed target                                         [WARN]
  Embedded table (`alias:TARGET(...)` or `TARGET(...)`) must exist as a
  table or view in migrations. Otherwise the embed yields null.

Layer 2 -- Phantom column inside embed                                  [WARN]
  Every column inside the embed parens must exist on the embedded table.
  Otherwise PostgREST returns the embed object with null fields.

Layer 3 -- Missing FK relationship                                      [WARN]
  PostgREST infers the embed via FK metadata between SOURCE and TARGET.
  When no FK exists in either direction, the embed cannot resolve --
  unless an explicit `!fk_name` annotation is present. View targets are
  treated as INFO only (PostgREST 11+ supports view embeds when the FK is
  preserved, but the analysis is migration-text-only).

Layer 4 -- Embed-by-layer distribution                                  [INFO]
  Where embeds concentrate (html / shared_js / edge / python_api).
  Informational -- helps spot lopsided traversal patterns.

Skills consulted: data-engineer (FK design, the part_name embed pattern
shipped in batch-risk-scoring/trigger-ml-retrain), architect (view embed
caveat -- canonical views need explicit FK preservation in PostgREST).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# -- Paths -------------------------------------------------------------------

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")
EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)

# Tables we treat as opaque (third-party / system).
OPAQUE_TABLES = {
    "auth", "users", "objects",
    "pg_publication_tables", "information_schema",
}

# Inner column tokens always valid in an embed body.
ALWAYS_VALID_TOKENS = {"*", "id", "count"}

# An embed targeting one of these tables is acceptable even without an
# explicit FK in migrations (Supabase auth tables; relationships set up in
# Supabase admin metadata, not in our SQL).
FK_OPAQUE_TARGETS = {"auth", "users"}


# -- Schema discovery (table columns) ----------------------------------------

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
ALTER_ADD_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:public\.|"public"\.|IF\s+EXISTS\s+)?
        "?(?P<name>\w+)"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+
        "?(?P<col>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
COLUMN_LINE_RE = re.compile(
    r"""^\s*"?(?P<col>\w+)"?\s+["a-zA-Z]""",
    re.MULTILINE,
)
COL_KEYWORDS = {
    "constraint", "primary", "unique", "foreign", "check", "exclude",
    "like", "create", "alter",
}


def load_table_columns() -> dict[str, set[str]]:
    """Mirror of validate_schema_phantom.load_table_columns."""
    cols: dict[str, set[str]] = defaultdict(set)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in CREATE_TABLE_RE.finditer(sql):
            name = m.group("name").lower()
            body = m.group("body")
            for cm in COLUMN_LINE_RE.finditer(body):
                col = cm.group("col").lower()
                if col in COL_KEYWORDS:
                    continue
                cols[name].add(col)
        for m in ALTER_ADD_RE.finditer(sql):
            cols[m.group("name").lower()].add(m.group("col").lower())
        # Also load view columns so embeds against canonical views resolve.
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?(\w+)\s+AS\s+",
            sql, re.IGNORECASE,
        ):
            view = m.group(1).lower()
            start = m.end()
            depth = 0
            i = start
            select_end = -1
            while i < len(sql):
                ch = sql[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif depth == 0 and ch in "Ff" and sql[i:i+5].upper() == "FROM ":
                    select_end = i
                    break
                if depth == 0 and ch == ";":
                    break
                i += 1
            if select_end < 0:
                continue
            sel_body = sql[start:select_end]
            sel_body = re.sub(r"^\s*SELECT\b", "", sel_body, flags=re.IGNORECASE).strip()
            depth = 0
            cleaned: list[str] = []
            for ch in sel_body:
                if   ch == "(": depth += 1
                elif ch == ")": depth -= 1
                elif depth == 0: cleaned.append(ch)
            for piece in "".join(cleaned).split(","):
                piece = piece.strip()
                if not piece:
                    continue
                m2 = re.search(r"\bAS\s+\"?(\w+)\"?\s*$", piece, re.IGNORECASE)
                if m2:
                    cols[view].add(m2.group(1).lower())
                    continue
                last = re.search(r"(\w+)\s*$", piece)
                if last:
                    name = last.group(1).lower()
                    if name not in COL_KEYWORDS:
                        cols[view].add(name)
    return {k: v for k, v in cols.items()}


# -- FK discovery ------------------------------------------------------------

# Inline column-level FK: `item_id uuid REFERENCES inventory_items(id) ...`
INLINE_FK_RE = re.compile(
    r"""\b(?P<col>\w+)\s+
        (?:uuid|bigint|integer|serial|text|smallint)
        [^,;\n]*?
        \bREFERENCES\s+
        (?:public\.|"public"\.)?
        "?(?P<target>\w+)"?
        \s*(?:\(\s*"?(?P<target_col>\w+)"?\s*\))?""",
    re.IGNORECASE | re.VERBOSE,
)
# Constraint-style FK: `CONSTRAINT name FOREIGN KEY (col) REFERENCES table(id)`
# May appear inside CREATE TABLE bodies or as ALTER TABLE ADD CONSTRAINT.
CONSTRAINT_FK_RE = re.compile(
    r"""(?:CONSTRAINT\s+\w+\s+)?
        FOREIGN\s+KEY\s*\(\s*"?(?P<col>\w+)"?\s*\)
        \s*REFERENCES\s+
        (?:public\.|"public"\.)?
        "?(?P<target>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)


def load_fk_pairs() -> set[tuple[str, str]]:
    """Return symmetric set of (table_a, table_b) where any FK exists.

    PostgREST embeds work in either direction, so we add both (a,b) and (b,a).
    """
    pairs: set[tuple[str, str]] = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        # Walk CREATE TABLE blocks and treat each as the source.
        for m in CREATE_TABLE_RE.finditer(sql):
            source = m.group("name").lower()
            body = m.group("body")
            for fk in INLINE_FK_RE.finditer(body):
                target = fk.group("target").lower()
                pairs.add((source, target))
                pairs.add((target, source))
            for fk in CONSTRAINT_FK_RE.finditer(body):
                target = fk.group("target").lower()
                pairs.add((source, target))
                pairs.add((target, source))
        # ALTER TABLE [ONLY] x ADD CONSTRAINT name FOREIGN KEY (col) REFERENCES y(col)
        # pg_dump splits the declaration: `ALTER TABLE ONLY "public"."x"` on one
        # line, then `    ADD CONSTRAINT "name" FOREIGN KEY ("col")` on the
        # next, then `REFERENCES "public"."y"("id") ...`. The DOTALL flag plus
        # \s+ across whitespace/newlines stitches the chain together.
        for m in re.finditer(
            r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.|IF\s+EXISTS\s+)?
                "?(?P<source>\w+)"?
                \s+ADD\s+(?:CONSTRAINT\s+"?\w+"?\s+)?
                FOREIGN\s+KEY\s*\(\s*"?\w+"?\s*\)
                \s+REFERENCES\s+(?:public\.|"public"\.)?
                "?(?P<target>\w+)"?""",
            sql, re.IGNORECASE | re.VERBOSE | re.DOTALL,
        ):
            source = m.group("source").lower()
            target = m.group("target").lower()
            pairs.add((source, target))
            pairs.add((target, source))
    return pairs


# -- Consumer scan -----------------------------------------------------------

# `.from('TABLE').select('...')` -- same regex as schema_phantom.
SELECT_RE_JSTS = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?:\s*\.\s*[a-zA-Z_]\w*\s*\([^)]*\))*?
        \s*\.\s*select\s*\(\s*['"`](?P<sel>[^'"`]+)['"`]""",
    re.IGNORECASE | re.VERBOSE,
)
SELECT_RE_PY = re.compile(
    r"""\.table\s*\(\s*['"](?P<table>[a-z_][a-z0-9_]*)['"]\s*\)
        \s*\.\s*select\s*\(\s*['"](?P<sel>[^'"]+)['"]""",
    re.IGNORECASE | re.VERBOSE,
)

# Embed shapes inside a select string.
# Aliased: `alias:target(cols)` or `alias:target!fk_name(cols)`.
ALIASED_EMBED_RE = re.compile(
    r"""(?:^|,)\s*
        (?P<alias>[a-zA-Z_]\w*)\s*:\s*
        (?P<target>[a-zA-Z_]\w*)
        (?:\s*!\s*(?P<fk>\w+))?
        \s*\(\s*(?P<cols>[^)]*)\)""",
    re.VERBOSE,
)
# Plain: `target(cols)` or `target!fk_name(cols)` (no alias). Must NOT be
# preceded by ':' (that would be aliased), or by another identifier (which
# would mean we're inside a function call like count()).
PLAIN_EMBED_RE = re.compile(
    r"""(?:^|,)\s*
        (?P<target>[a-zA-Z_]\w*)
        (?:\s*!\s*(?P<fk>\w+))?
        \s*\(\s*(?P<cols>[^)]*)\)""",
    re.VERBOSE,
)
# Aggregate keywords that look like embeds but aren't.
AGGREGATE_NAMES = {"count", "sum", "avg", "min", "max"}


def _path_excluded(path: str) -> bool:
    return any(part in path for part in EXCLUDED_PATH_PARTS)


def list_consumer_files() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append((path, "shared_js"))
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path or _path_excluded(path):
            continue
        out.append((path, "python_api"))
    return out


def file_select_clauses(path: str) -> list[tuple[str, str]]:
    content = read_file(path) or ""
    rx = SELECT_RE_PY if path.endswith(".py") else SELECT_RE_JSTS
    return [(m.group("table").lower(), m.group("sel")) for m in rx.finditer(content)]


def parse_embeds(sel: str) -> list[dict]:
    """Return [{alias, target, fk, cols, position}] for each embed in select."""
    out: list[dict] = []
    seen_starts: set[int] = set()
    # Aliased first (more specific).
    for m in ALIASED_EMBED_RE.finditer(sel):
        target = m.group("target").lower()
        if target in AGGREGATE_NAMES:
            continue
        seen_starts.add(m.start())
        out.append({
            "alias":    m.group("alias"),
            "target":   target,
            "fk":       (m.group("fk") or "").lower() or None,
            "cols":     [c.strip() for c in m.group("cols").split(",") if c.strip()],
            "position": m.start(),
        })
    # Plain. Skip if start overlaps an aliased match, or if preceded by ':'
    # (already aliased) or '.' (function call like .toFixed).
    for m in PLAIN_EMBED_RE.finditer(sel):
        if m.start() in seen_starts:
            continue
        # Look back from match start to skip false positives.
        prev_char = sel[m.start()-1] if m.start() > 0 else ""
        # `,` before the target name is normal. Reject only if previous
        # non-space is ':' (aliased) -- our regex prefix `(?:^|,)\s*` already
        # handles this, so be paranoid and double-check.
        # Find the actual non-space char before the target.
        i = m.start() - 1
        while i >= 0 and sel[i].isspace():
            i -= 1
        if i >= 0 and sel[i] == ":":
            continue
        target = m.group("target").lower()
        if target in AGGREGATE_NAMES:
            continue
        out.append({
            "alias":    None,
            "target":   target,
            "fk":       (m.group("fk") or "").lower() or None,
            "cols":     [c.strip() for c in m.group("cols").split(",") if c.strip()],
            "position": m.start(),
        })
    return out


# -- Layer 1: Phantom embed target -------------------------------------------

def check_phantom_target(
    consumer_files: list[tuple[str, str]],
    table_cols: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path, _layer in consumer_files:
        for source, sel in file_select_clauses(path):
            for emb in parse_embeds(sel):
                target = emb["target"]
                if target in OPAQUE_TABLES or target in FK_OPAQUE_TARGETS:
                    continue
                if target in table_cols:
                    continue
                report.append({
                    "path":   path,
                    "source": source,
                    "alias":  emb["alias"],
                    "target": target,
                })
                issues.append({
                    "check": "phantom_target", "skip": True,
                    "reason": (
                        f"{path}: .from('{source}').select('...{(emb['alias'] + ':' if emb['alias'] else '')}{target}(...)') "
                        f"embeds table '{target}' which does not exist in migrations. "
                        f"PostgREST returns null for this embed; the consumer renders missing data."
                    ),
                })
    return issues, report


# -- Layer 2: Phantom column inside embed ------------------------------------

def check_phantom_embed_column(
    consumer_files: list[tuple[str, str]],
    table_cols: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path, _layer in consumer_files:
        for source, sel in file_select_clauses(path):
            for emb in parse_embeds(sel):
                target = emb["target"]
                if target in OPAQUE_TABLES or target in FK_OPAQUE_TARGETS:
                    continue
                if target not in table_cols:
                    continue   # phantom target -- L1 covers
                known = table_cols[target]
                phantoms: list[str] = []
                for raw in emb["cols"]:
                    # Inner column may itself be aliased: `alias:underlying`
                    # We only validate the underlying column.
                    inner = raw
                    if ":" in inner:
                        inner = inner.split(":", 1)[1].strip()
                    inner = inner.strip()
                    if not inner or inner in ALWAYS_VALID_TOKENS:
                        continue
                    if inner in known:
                        continue
                    phantoms.append(inner)
                if phantoms:
                    report.append({
                        "path":     path,
                        "source":   source,
                        "target":   target,
                        "phantoms": phantoms,
                    })
                    issues.append({
                        "check": "phantom_embed_column", "skip": True,
                        "reason": (
                            f"{path}: .from('{source}').select('...{target}({', '.join(emb['cols'][:3])})') "
                            f"references column(s) {phantoms} that do not exist on '{target}'. "
                            f"The embed object will have those fields as null."
                        ),
                    })
    return issues, report


# -- Layer 3: Missing FK relationship ----------------------------------------

def check_missing_fk(
    consumer_files: list[tuple[str, str]],
    table_cols: dict[str, set[str]],
    fk_pairs: set[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    # Identify view targets so we treat them as INFO (PostgREST view embed
    # works only when FK is preserved into the view -- detection here would
    # need pg_dump). Tables backing views are tracked via load_view_targets.
    view_names = {t for t in table_cols if t.startswith("v_") or t == "asset_brain_overview"}
    for path, _layer in consumer_files:
        for source, sel in file_select_clauses(path):
            for emb in parse_embeds(sel):
                target = emb["target"]
                if target in OPAQUE_TABLES or target in FK_OPAQUE_TARGETS:
                    continue
                if target not in table_cols:
                    continue   # phantom target -- L1 covers
                if emb["fk"]:
                    continue   # explicit `!fk_name` annotation -- trust it
                if target in view_names or source in view_names:
                    # View embeds need FK preservation in the view definition;
                    # we cannot detect that statically without running PG.
                    # Record as INFO, not WARN.
                    report.append({
                        "path": path, "source": source, "target": target,
                        "kind": "view_embed_info",
                    })
                    continue
                if (source, target) in fk_pairs:
                    continue
                report.append({
                    "path": path, "source": source, "target": target,
                    "kind": "missing_fk",
                })
                issues.append({
                    "check": "missing_fk", "skip": True,
                    "reason": (
                        f"{path}: .from('{source}').select('...{target}(...)') has no foreign-key "
                        f"relationship between '{source}' and '{target}' in migrations. PostgREST "
                        f"cannot infer the embed and returns null. Either add a FK constraint, or "
                        f"annotate the embed explicitly with `{target}!fk_name(...)`."
                    ),
                })
    return issues, report


# -- Layer 4: Embed-by-layer distribution ------------------------------------

def check_embed_layer_distribution(
    consumer_files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path, layer in consumer_files:
        for _source, sel in file_select_clauses(path):
            for emb in parse_embeds(sel):
                counter[emb["target"]][layer] += 1
    rows: list[dict] = []
    for target, layers in counter.items():
        total = sum(layers.values())
        rows.append({
            "target": target,
            "total": total,
            "layers": dict(layers),
        })
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Runner ------------------------------------------------------------------

CHECK_NAMES = [
    "phantom_target",
    "phantom_embed_column",
    "missing_fk",
    "embed_layer_distribution",
]
CHECK_LABELS = {
    "phantom_target":           "L1  No embed targets a table that does not exist                  [WARN]",
    "phantom_embed_column":     "L2  No embed selects a column that does not exist on the target   [WARN]",
    "missing_fk":               "L3  Every embed has a FK between source and target (or `!fk` hint) [WARN]",
    "embed_layer_distribution": "L4  Embed concentration by platform layer (informational)         [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nPostgREST Embed Integrity Detector (4-layer)"))
    print("=" * 60)

    table_cols     = load_table_columns()
    fk_pairs       = load_fk_pairs()
    consumer_files = list_consumer_files()

    print(f"  {len(table_cols)} tables/views, "
          f"{len(fk_pairs)//2} FK relationships, "
          f"{len(consumer_files)} consumer files scanned.\n")

    target_issues, target_report = check_phantom_target(consumer_files, table_cols)
    col_issues,    col_report    = check_phantom_embed_column(consumer_files, table_cols)
    fk_issues,     fk_report     = check_missing_fk(consumer_files, table_cols, fk_pairs)
    dist_issues,   dist_report   = check_embed_layer_distribution(consumer_files)

    all_issues = target_issues + col_issues + fk_issues + dist_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if dist_report:
        print(f"\n{bold('EMBED TARGETS BY USE COUNT (informational)')}")
        print("  " + "-" * 56)
        for r in dist_report[:10]:
            layers = ", ".join(f"{k}={v}" for k, v in r["layers"].items())
            print(f"  {r['target']:<32}  total={r['total']:<3}  ({layers})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":              "embed_integrity",
        "total_checks":           total,
        "passed":                 n_pass,
        "warned":                 n_warn,
        "failed":                 n_fail,
        "n_tables":               len(table_cols),
        "n_fk_pairs":             len(fk_pairs) // 2,
        "n_consumers":            len(consumer_files),
        "phantom_targets":        target_report,
        "phantom_embed_columns":  col_report,
        "missing_fks":            fk_report,
        "embed_distribution":     dist_report,
        "issues":                 [i for i in all_issues if not i.get("skip")],
        "warnings":               [i for i in all_issues if i.get("skip")],
    }
    with open("embed_integrity_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
