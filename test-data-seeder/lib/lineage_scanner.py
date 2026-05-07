"""
Platform Lineage Scanner
========================
Scans the WorkHive codebase and builds a full dependency graph:
  which components (HTML pages, edge functions, Python files) read and
  write which tables, and which fields they write.

Used by the /lineage route to power the interactive visual.
"""

import re
import os
from pathlib import Path
from collections import defaultdict

# Root of the WorkHive project (one level up from test-data-seeder)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Files/dirs to skip
SKIP_DIRS = {
    "test-data-seeder", "node_modules", ".git", "venv",
    "__pycache__", ".tmp", "brand_assets",
}

SKIP_FILES = {"sw.js", "manifest.json"}

# ── Field extraction helpers ───────────────────────────────────────────────────

JS_NOISE = {
    "const", "let", "var", "return", "if", "else", "true", "false",
    "null", "undefined", "await", "async", "function", "data", "error",
    "then", "catch", "new", "this", "typeof", "instanceof",
}


def _extract_object_body(text: str, start: int) -> str:
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    return ""


def _clean_and_extract_keys(body: str) -> set:
    body = re.sub(r"'[^'\n]*'", "''", body)
    body = re.sub(r'"[^"\n]*"', '""', body)
    body = re.sub(r"`[^`\n]*`", "``", body)
    body = re.sub(r"\$\{[^}]*\}", "__INTERP__", body)
    keys = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*:", body)
    return {k for k in keys if k not in JS_NOISE and len(k) > 1}


def extract_insert_fields(content: str, table: str) -> set:
    """Extract field names from .insert({...}) or .upsert({...}) calls."""
    fields = set()
    for op in ("insert", "upsert"):
        for quote in ("'", '"'):
            search = f"from({quote}{table}{quote}).{op}("
            pos = 0
            while True:
                idx = content.find(search, pos)
                if idx == -1:
                    break
                brace = content.find("{", idx + len(search) - 1)
                if brace == -1:
                    pos = idx + 1
                    continue
                body = _extract_object_body(content, brace)
                fields.update(_clean_and_extract_keys(body))
                pos = idx + 1
    return fields - JS_NOISE


def extract_select_columns(content: str, table: str) -> set:
    """Extract column names from .select('a, b, c') calls."""
    cols = set()
    for quote in ("'", '"'):
        pattern = rf"from\({re.escape(quote)}{re.escape(table)}{re.escape(quote)}\)\.select\(['\"]([^'\"]+)['\"]"
        for m in re.finditer(pattern, content):
            raw = m.group(1)
            if raw.strip() == "*":
                cols.add("*")
            else:
                for col in re.split(r"[,\s]+", raw):
                    col = col.strip().split(":")[0]  # handle 'col:alias'
                    if col and col not in JS_NOISE:
                        cols.add(col)
    return cols


# ── File scanners ──────────────────────────────────────────────────────────────

_TABLE_OPS_PATTERN = re.compile(
    r"""from\s*\(\s*['"](\w+)['"]\s*\)\s*\.\s*(select|insert|upsert|update|delete)""",
    re.IGNORECASE,
)


def scan_file(path: Path) -> dict:
    """Scan one file and return its DB operations.

    Returns:
        {
            "reads":   {table: [columns]},
            "writes":  {table: [fields]},
            "updates": [table],
            "deletes": [table],
        }
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    reads   = defaultdict(set)
    writes  = defaultdict(set)
    updates = set()
    deletes = set()

    for m in _TABLE_OPS_PATTERN.finditer(content):
        table = m.group(1)
        op    = m.group(2).lower()

        if op == "select":
            cols = extract_select_columns(content, table)
            reads[table].update(cols)
        elif op in ("insert", "upsert"):
            fields = extract_insert_fields(content, table)
            writes[table].update(fields)
        elif op == "update":
            updates.add(table)
        elif op == "delete":
            deletes.add(table)

    if not (reads or writes or updates or deletes):
        return {}

    return {
        "reads":   {t: sorted(c) for t, c in reads.items()},
        "writes":  {t: sorted(f) for t, f in writes.items()},
        "updates": sorted(updates),
        "deletes": sorted(deletes),
    }


def _label(path: Path) -> str:
    """Human-readable short label for a file."""
    rel = path.relative_to(PROJECT_ROOT)
    parts = rel.parts

    # Edge functions: supabase/functions/<name>/index.ts → <name> (edge fn)
    if len(parts) >= 3 and parts[0] == "supabase" and parts[1] == "functions":
        return f"{parts[2]} (edge fn)"

    # Everything else: just the filename
    return path.name


# ── Main scanner ───────────────────────────────────────────────────────────────

def scan_all() -> dict:
    """Scan all HTML + TS + Python files in the project.

    Returns the full lineage graph:
    {
        "components": [
            {
                "name":    "logbook.html",
                "path":    "logbook.html",
                "type":    "html" | "edge_fn" | "python",
                "reads":   {"logbook": ["worker_name", ...], ...},
                "writes":  {"logbook": ["worker_name", ...], ...},
                "updates": ["logbook"],
                "deletes": [],
            },
            ...
        ],
        "tables": {
            "logbook": {
                "written_by":  ["logbook.html", "cmms-sync (edge fn)", ...],
                "read_by":     ["analytics-orchestrator (edge fn)", ...],
                "updated_by":  [...],
                "deleted_by":  [...],
                "write_fields": {
                    "logbook.html": ["worker_name", "date", ...],
                    ...
                },
            },
            ...
        },
        "impact": {
            "logbook.machine": {
                "written_by": ["logbook.html", "cmms-sync (edge fn)"],
                "read_by":    ["analytics-orchestrator (edge fn)", ...],
            },
            ...
        },
    }
    """
    components = []

    # Collect files to scan
    candidates = []

    # 1. HTML files in project root
    for f in PROJECT_ROOT.glob("*.html"):
        if f.name not in SKIP_FILES:
            candidates.append(("html", f))

    # 2. Edge function index.ts files
    fn_dir = PROJECT_ROOT / "supabase" / "functions"
    if fn_dir.exists():
        for fn_index in fn_dir.rglob("index.ts"):
            if "_shared" not in fn_index.parts:
                candidates.append(("edge_fn", fn_index))

    # 3. Key Python files (nav-hub.js, floating-ai.js)
    for f in PROJECT_ROOT.glob("*.js"):
        if f.name not in SKIP_FILES:
            candidates.append(("js", f))

    for file_type, path in candidates:
        ops = scan_file(path)
        if not ops:
            continue
        components.append({
            "name":    _label(path),
            "path":    str(path.relative_to(PROJECT_ROOT)),
            "type":    file_type,
            "reads":   ops.get("reads",   {}),
            "writes":  ops.get("writes",  {}),
            "updates": ops.get("updates", []),
            "deletes": ops.get("deletes", []),
        })

    # Build table-centric index
    tables = defaultdict(lambda: {
        "written_by":  [],
        "read_by":     [],
        "updated_by":  [],
        "deleted_by":  [],
        "write_fields": {},
    })

    for comp in components:
        name = comp["name"]
        for table, fields in comp["writes"].items():
            tables[table]["written_by"].append(name)
            tables[table]["write_fields"][name] = fields
        for table in comp["reads"]:
            tables[table]["read_by"].append(name)
        for table in comp["updates"]:
            tables[table]["updated_by"].append(name)
        for table in comp["deletes"]:
            tables[table]["deleted_by"].append(name)

    # Build field-level impact index
    impact = defaultdict(lambda: {"written_by": [], "read_by": []})

    for comp in components:
        name = comp["name"]
        for table, fields in comp["writes"].items():
            for field in fields:
                key = f"{table}.{field}"
                impact[key]["written_by"].append(name)
        for table, cols in comp["reads"].items():
            for col in cols:
                if col != "*":
                    key = f"{table}.{col}"
                    impact[key]["read_by"].append(name)

    return {
        "components": components,
        "tables":     dict(tables),
        "impact":     dict(impact),
        "stats": {
            "components_scanned": len(components),
            "tables_found":       len(tables),
            "fields_tracked":     len(impact),
        },
    }
