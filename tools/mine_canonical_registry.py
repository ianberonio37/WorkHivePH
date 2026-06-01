"""
Canonical Source Registry Miner -- L-1 Foundation (WorkHive Platform)
======================================================================
Walks the codebase to produce an authoritative index of every canonical
source on the platform: tables, columns, RPCs, views, edge functions,
and the HTML surfaces that read/write each one.

Why this exists: the platform has grown faster than memory of itself.
Without an auto-built catalog, every new-feature proposal risks
duplicating a surface, column, or RPC that already exists. This miner
makes "what's already here?" a 1-second lookup instead of a memory
call.

Output:
  - canonical_registry.json  (machine)
  - canonical_registry.md    (human)

Architecture:
  Pass 1: parse all SQL migrations to extract tables, columns, RPCs,
          views, GRANTs, COMMENTs, realtime publication, and FKs.
  Pass 2: parse all HTML surfaces for `.from('X')` / `.rpc('X')` /
          `functions.invoke('X')` to learn who reads/writes/calls what.
  Pass 3: parse all edge fns (`supabase/functions/<name>/index.ts`)
          the same way.
  Pass 4: cross-link -- every table gets `read_by_surfaces`,
          `written_by_surfaces`, `written_by_edge_fns`, etc.
  Pass 5: duplicate-signal heuristics -- flag tables with no readers,
          surfaces that share >=3 tables (likely overlap), and column
          name-pair near-duplicates within the same table.

Skills consulted: architect (canonical-source doctrine, schema design),
data-engineer (table / RPC / view conventions), multitenant-engineer
(hive scope as primary axis), qa-tester (the audit reflex this
automates).
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
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
EDGE_FNS_DIR   = ROOT / "supabase" / "functions"

OUT_JSON = ROOT / "canonical_registry.json"
OUT_MD   = ROOT / "canonical_registry.md"

# Exclusion patterns for HTML files (same as other miners).
HTML_EXCLUDE = [
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"-test\.html$"),
]


# ─────────────────────────────────────────────────────────────────────────────
# SQL parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _strip_sql_comments(text: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"--[^\n]*", "", out)
    return out


def _unquote(name: str) -> str:
    """Strip Postgres double-quotes and schema prefix."""
    name = name.strip().strip('"')
    if "." in name:
        name = name.split(".", 1)[1].strip('"')
    return name


# CREATE TABLE [IF NOT EXISTS] [schema.]name (col TYPE, col TYPE, ...);
CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[\"\w.]+)\s*\(""",
    re.IGNORECASE,
)
# ALTER TABLE [ONLY] name ADD COLUMN [IF NOT EXISTS] colname TYPE ...
ADD_COLUMN_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?P<table>[\"\w.]+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<col>[\"\w]+)\s+(?P<type>[\w\s().,\[\]]+?)(?:\s+(?:DEFAULT|NOT\s+NULL|REFERENCES|UNIQUE|PRIMARY)|\s*;|\s*$)""",
    re.IGNORECASE,
)
# CREATE [OR REPLACE] FUNCTION [schema.]name(arg1 type, arg2 type ...) ...
CREATE_FUNCTION_RE = re.compile(
    # Args may contain parenthesized type expressions like `vector(384)` —
    # accept one level of nested parens so the full signature is captured.
    # Previously `[^)]*` truncated at the first ')', cutting args like
    # `match_auth_uid uuid, match_count int` out of the registry, causing
    # RPC-argument-consistency false positives on signatures with vector(N).
    r"""CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?P<name>[\"\w.]+)\s*\((?P<args>(?:[^()]|\([^)]*\))*)\)""",
    re.IGNORECASE,
)
# CREATE [OR REPLACE] [MATERIALIZED] VIEW [IF NOT EXISTS] [schema.]name [WITH (...)] AS ...
# MATERIALIZED + IF NOT EXISTS added 2026-05-28: the miner was silently
# dropping materialised views (e.g. v_kpi_truth in 20260512000005), leaving
# the object- and column-existence validators blind to them. Found via the
# MCP cockpit flywheel.
# WITH (...) options clause added 2026-06-01: a `CREATE OR REPLACE VIEW
# public.v_asset_state_truth WITH (security_invoker = true) AS ...` was
# invisible because the regex required `name\s+AS` and could not span the
# options clause — the exact view-regex gap documented for
# validate_schema_coverage. Optional `(?:\s+WITH\s*\([^)]*\))?` before AS.
CREATE_VIEW_RE = re.compile(
    r"""CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[\"\w.]+)(?:\s+WITH\s*\([^)]*\))?\s+AS""",
    re.IGNORECASE,
)
ENABLE_RLS_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?P<table>[\"\w.]+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY""",
    re.IGNORECASE,
)
GRANT_RE = re.compile(
    r"""GRANT\s+(?P<perms>[\w,\s]+?)\s+ON\s+(?:TABLE\s+)?(?P<obj>[\"\w.]+)\s+TO\s+(?P<roles>[\w,\s]+?)\s*;""",
    re.IGNORECASE,
)
COMMENT_ON_RE = re.compile(
    r"""COMMENT\s+ON\s+(?P<kind>TABLE|COLUMN|FUNCTION|VIEW)\s+(?P<obj>[\"\w.()\s,]+?)\s+IS\s+'(?P<body>(?:[^']|'')*)'""",
    re.IGNORECASE | re.DOTALL,
)
REALTIME_PUB_RE = re.compile(
    r"""ALTER\s+PUBLICATION\s+supabase_realtime\s+ADD\s+TABLE\s+(?P<table>[\"\w.]+)""",
    re.IGNORECASE,
)
SECURITY_DEFINER_RE = re.compile(r"\bSECURITY\s+DEFINER\b", re.IGNORECASE)


def _extract_columns_from_create_table(body: str) -> list[str]:
    """Given the parenthesized body of CREATE TABLE, return the column
    names declared at brace-depth 0 (ignore embedded constraints)."""
    # Split on commas at depth 0, accounting for parens.
    cols, depth, current = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            cols.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        cols.append(current.strip())

    keywords = {
        "constraint", "primary", "foreign", "unique", "check",
        "exclude", "like", "references",
    }
    names = []
    for c in cols:
        c = c.strip()
        if not c:
            continue
        first = c.split()[0].strip('"').lower()
        if first in keywords:
            continue
        names.append(c.split()[0].strip('"'))
    return names


def parse_migration(path: Path, regs: dict) -> None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_sql_comments(raw)
    fname = path.name

    # CREATE TABLE -- extract names + column lists via paren-depth walk.
    for m in CREATE_TABLE_RE.finditer(code):
        name = _unquote(m.group("name"))
        # Walk forward to find the matching closing paren.
        depth, i = 1, m.end()
        while i < len(code) and depth > 0:
            if code[i] == "(":
                depth += 1
            elif code[i] == ")":
                depth -= 1
            i += 1
        body = code[m.end():i - 1]
        cols = _extract_columns_from_create_table(body)

        if name not in regs["tables"]:
            regs["tables"][name] = {
                "defined_in": fname, "columns": [], "rls_enabled": False,
                "grants": {}, "realtime_published": False, "comment": "",
                "read_by_surfaces": [], "written_by_surfaces": [],
                "read_by_edge_fns": [], "written_by_edge_fns": [],
            }
        # First-definition wins for defined_in; merge columns idempotently.
        for c in cols:
            if c not in regs["tables"][name]["columns"]:
                regs["tables"][name]["columns"].append(c)

    # ALTER TABLE ADD COLUMN (incl. multi-clause form:
    #   ALTER TABLE X
    #     ADD COLUMN A type,
    #     ADD COLUMN B type,
    #     ADD COLUMN C type;
    # The single-clause ADD_COLUMN_RE catches the FIRST clause; we then scan
    # the rest of the ALTER statement (up to next `;`) for subsequent
    # `ADD COLUMN <name>` clauses.)
    ALTER_STMT_RE = re.compile(
        r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?P<table>[\"\w.]+)\s+(?P<body>[^;]+);""",
        re.IGNORECASE | re.DOTALL,
    )
    INNER_ADD_RE = re.compile(
        r"""ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<col>[\"\w]+)""",
        re.IGNORECASE,
    )
    for sm in ALTER_STMT_RE.finditer(code):
        tbl = _unquote(sm.group("table"))
        if tbl not in regs["tables"]:
            regs["tables"][tbl] = {
                "defined_in": fname, "columns": [], "rls_enabled": False,
                "grants": {}, "realtime_published": False, "comment": "",
                "read_by_surfaces": [], "written_by_surfaces": [],
                "read_by_edge_fns": [], "written_by_edge_fns": [],
            }
        for am in INNER_ADD_RE.finditer(sm.group("body")):
            col = _unquote(am.group("col"))
            if col not in regs["tables"][tbl]["columns"]:
                regs["tables"][tbl]["columns"].append(col)

    # CREATE FUNCTION
    for m in CREATE_FUNCTION_RE.finditer(code):
        name = _unquote(m.group("name"))
        args = m.group("args").strip()
        # SECURITY DEFINER check within the next 500 chars (function body).
        tail = code[m.end(): m.end() + 800]
        is_definer = bool(SECURITY_DEFINER_RE.search(tail))
        if name not in regs["rpcs"]:
            regs["rpcs"][name] = {
                "defined_in": fname, "args": args, "security_definer": is_definer,
                "comment": "", "called_by_surfaces": [], "called_by_edge_fns": [],
            }
        else:
            # Later definitions may add SECURITY DEFINER or change args.
            regs["rpcs"][name]["security_definer"] = (
                regs["rpcs"][name]["security_definer"] or is_definer
            )

    # CREATE VIEW — also extract the projected column list from the SELECT.
    # Heuristic: walk forward from CREATE VIEW ... AS to the next `;`. The
    # outermost SELECT projection between SELECT and the FIRST top-level FROM
    # gives us the view's column names. Aliases (`expr AS name`) take the
    # alias as the column name; bare identifiers (`tbl.col`) take the
    # rightmost segment.
    for m in CREATE_VIEW_RE.finditer(code):
        name = _unquote(m.group("name"))
        # Walk forward to the matching ';' at depth 0
        i = m.end()
        depth = 0
        in_string = False
        string_ch = ""
        end = len(code)
        while i < len(code):
            ch = code[i]
            if in_string:
                if ch == string_ch and code[i-1] != "\\":
                    in_string = False
            elif ch in ("'", '"'):
                in_string = True
                string_ch = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == ";" and depth == 0:
                end = i
                break
            i += 1
        view_body = code[m.end():end]
        # The outer SELECT is the LAST top-level SELECT in the view body
        # (when CTEs / WITH-clauses exist, those have inner SELECTs first).
        # Find every SELECT...FROM at depth 0.
        proj_match = None
        depth = 0
        cur_select_start = -1
        for ci in range(len(view_body)):
            ch = view_body[ci]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0:
                if view_body[ci:ci+7].upper() == "SELECT ":
                    cur_select_start = ci + 6  # right after "SELECT"
        if cur_select_start >= 0:
            tail = view_body[cur_select_start:]
            # Now find the FROM at depth 0 within tail
            d2, from_idx = 0, -1
            for ci in range(len(tail)):
                ch = tail[ci]
                if ch == "(":
                    d2 += 1
                elif ch == ")":
                    d2 -= 1
                elif d2 == 0 and tail[ci:ci+5].upper() == "FROM " and (ci == 0 or not tail[ci-1].isalnum()):
                    from_idx = ci
                    break
            if from_idx > 0:
                class _Wrap:
                    def __init__(self, s): self._s = s
                    def group(self, k): return self._s
                # Strip leading whitespace + DISTINCT [ON (...)]
                proj_txt = tail[:from_idx].strip()
                proj_txt = re.sub(r"^DISTINCT\s+(?:ON\s*\([^)]*\)\s+)?", "", proj_txt, flags=re.IGNORECASE)
                proj_match = _Wrap(proj_txt)
        view_cols: list[str] = []
        if proj_match:
            proj = proj_match.group("proj")
            # Split projection on commas at depth 0
            parts: list[str] = []
            cur, dep = "", 0
            for ch in proj:
                if ch == "(":
                    dep += 1
                elif ch == ")":
                    dep -= 1
                if ch == "," and dep == 0:
                    parts.append(cur); cur = ""
                else:
                    cur += ch
            if cur.strip():
                parts.append(cur)
            for p in parts:
                p = p.strip()
                if not p: continue
                # `expr AS name` → take `name`
                alias_m = re.search(r"""\bAS\s+['"]?([a-z_][\w]*)['"]?\s*$""", p, re.IGNORECASE)
                if alias_m:
                    view_cols.append(alias_m.group(1).lower())
                    continue
                # bare `col` or `tbl.col` — take rightmost identifier
                last_id = re.findall(r"\b([a-z_][\w]*)\b", p, re.IGNORECASE)
                if last_id:
                    view_cols.append(last_id[-1].lower())
        if name not in regs["views"]:
            regs["views"][name] = {
                "defined_in": fname, "read_by_surfaces": [], "read_by_edge_fns": [],
                "columns": [],
            }
        # Merge view columns (idempotent — first definition wins, later
        # CREATE OR REPLACE adds new columns)
        for c in view_cols:
            if c not in regs["views"][name].get("columns", []):
                regs["views"][name].setdefault("columns", []).append(c)

    # ENABLE RLS
    for m in ENABLE_RLS_RE.finditer(code):
        tbl = _unquote(m.group("table"))
        if tbl in regs["tables"]:
            regs["tables"][tbl]["rls_enabled"] = True

    # GRANT
    for m in GRANT_RE.finditer(code):
        obj = _unquote(m.group("obj"))
        roles = [r.strip() for r in m.group("roles").split(",")]
        perms = [p.strip().upper() for p in m.group("perms").split(",")]
        if obj in regs["tables"]:
            for r in roles:
                if r not in regs["tables"][obj]["grants"]:
                    regs["tables"][obj]["grants"][r] = []
                for p in perms:
                    if p not in regs["tables"][obj]["grants"][r]:
                        regs["tables"][obj]["grants"][r].append(p)

    # Realtime publication
    for m in REALTIME_PUB_RE.finditer(code):
        tbl = _unquote(m.group("table"))
        if tbl in regs["tables"]:
            regs["tables"][tbl]["realtime_published"] = True

    # COMMENT ON
    for m in COMMENT_ON_RE.finditer(code):
        kind = m.group("kind").upper()
        obj_raw = m.group("obj").strip()
        body = m.group("body").replace("''", "'")
        # Normalize: strip quotes, schema prefix, and parenthesized arg lists for functions
        obj = re.split(r"\(", obj_raw, 1)[0]
        obj = _unquote(obj)
        if kind == "TABLE" and obj in regs["tables"]:
            regs["tables"][obj]["comment"] = body
        elif kind == "FUNCTION" and obj in regs["rpcs"]:
            regs["rpcs"][obj]["comment"] = body


# ─────────────────────────────────────────────────────────────────────────────
# HTML / TS parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

# Strip comments per language.
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
TS_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
TS_LINE_COMMENT_RE = re.compile(r"^[ \t]*//[^\n]*$", re.MULTILINE)

# `.from('table')` -- supabase-js table reference.
FROM_RE = re.compile(r"""\.\s*from\s*\(\s*['"](?P<table>\w+)['"]""")
# `.rpc('fn'` -- supabase-js RPC.
RPC_RE = re.compile(r"""\.\s*rpc\s*\(\s*['"](?P<rpc>\w+)['"]""")
# functions.invoke('edge-fn') -- edge fn invocation (HTML side).
INVOKE_RE = re.compile(r"""\.\s*invoke\s*\(\s*['"](?P<fn>[\w-]+)['"]""")
# Detect a write operation following a .from() call: .insert(, .update(, .upsert(, .delete(
# 2026-05-20: tightened to require the write verb IMMEDIATELY after `.from()`
# (only whitespace, including newlines, between). The previous regex allowed
# up to 400 chars and caused false positives like .from('A').select(...) ...
# .from('B').insert(...) attributing the insert to A. The Supabase SDK
# always emits the verb as the FIRST chained call after .from(), so this
# tighter pattern is accurate AND catches the same true writes.
WRITE_SUFFIX_RE = re.compile(r"\.\s*from\s*\(\s*['\"](?P<table>\w+)['\"]\s*\)\s*\.\s*(?:insert|update|upsert|delete)\s*\(")


SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>([\s\S]*?)</script>", re.IGNORECASE)


def _extract_script_blocks(text: str) -> str:
    """Return only the concatenated `<script>...</script>` body text.
    Avoids false positives from prose mentions like '.from(X)' inside
    documentation paragraphs. Comments inside script blocks are also
    stripped via the TS stripper (same JS comment syntax)."""
    blocks = SCRIPT_BLOCK_RE.findall(text)
    joined = "\n".join(blocks)
    # Strip JS comments inside the script.
    joined = TS_BLOCK_COMMENT_RE.sub("", joined)
    joined = TS_LINE_COMMENT_RE.sub("", joined)
    return joined


def _strip_html(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def _strip_ts(text: str) -> str:
    out = TS_BLOCK_COMMENT_RE.sub("", text)
    out = TS_LINE_COMMENT_RE.sub("", out)
    return out


def parse_surface(path: Path, regs: dict) -> None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    # Only scan inside <script> blocks -- prose mentions of `.from('X')`
    # in documentation panels produced false-positive phantom tables.
    code = _extract_script_blocks(_strip_html(raw))
    name = path.name

    tables_read = {m.group("table") for m in FROM_RE.finditer(code)}
    tables_written = {m.group("table") for m in WRITE_SUFFIX_RE.finditer(code)}
    rpcs_called = {m.group("rpc") for m in RPC_RE.finditer(code)}
    edge_fns_invoked = {m.group("fn") for m in INVOKE_RE.finditer(code)}

    regs["surfaces"][name] = {
        "tables_read":      sorted(tables_read),
        "tables_written":   sorted(tables_written),
        "rpcs_called":      sorted(rpcs_called),
        "edge_fns_invoked": sorted(edge_fns_invoked),
        "size_kb":          round(len(raw) / 1024, 1),
    }


def parse_edge_fn(path: Path, regs: dict) -> None:
    """`path` is the function directory; we read its index.ts."""
    index = path / "index.ts"
    if not index.exists():
        return
    _parse_ts_file(index, path.name, regs)


def parse_shared_ts(path: Path, regs: dict) -> None:
    """`path` is a single .ts file under supabase/functions/_shared/.
    Registered as a pseudo edge fn `_shared/<filename>` so the registry
    captures its table/RPC reads — these modules are imported by every
    edge fn and are real consumers."""
    if not path.is_file() or path.suffix != ".ts":
        return
    name = f"_shared/{path.name}"
    _parse_ts_file(path, name, regs)


def _parse_ts_file(ts_path: Path, name: str, regs: dict) -> None:
    raw = ts_path.read_text(encoding="utf-8", errors="replace")
    code = _strip_ts(raw)

    tables_read      = {m.group("table") for m in FROM_RE.finditer(code)}
    tables_written   = {m.group("table") for m in WRITE_SUFFIX_RE.finditer(code)}
    rpcs_called      = {m.group("rpc") for m in RPC_RE.finditer(code)}
    edge_fns_invoked = {m.group("fn") for m in INVOKE_RE.finditer(code)}

    regs["edge_fns"][name] = {
        "tables_read":      sorted(tables_read),
        "tables_written":   sorted(tables_written),
        "rpcs_called":      sorted(rpcs_called),
        "edge_fns_invoked": sorted(edge_fns_invoked),
        "loc":              len([l for l in raw.splitlines() if l.strip()]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cross-linking
# ─────────────────────────────────────────────────────────────────────────────

def cross_link(regs: dict) -> None:
    """For each table / RPC / view, list who reads + writes it."""
    for surface_name, surface in regs["surfaces"].items():
        for t in surface["tables_read"]:
            if t in regs["tables"]:
                regs["tables"][t]["read_by_surfaces"].append(surface_name)
            elif t in regs["views"]:
                regs["views"][t]["read_by_surfaces"].append(surface_name)
            else:
                # Phantom -- table referenced in code but not defined in migrations.
                regs["phantom_tables"].setdefault(t, {"read_by_surfaces": [], "read_by_edge_fns": [],
                                                       "written_by_surfaces": [], "written_by_edge_fns": []})
                regs["phantom_tables"][t]["read_by_surfaces"].append(surface_name)
        for t in surface["tables_written"]:
            if t in regs["tables"]:
                regs["tables"][t]["written_by_surfaces"].append(surface_name)
            else:
                regs["phantom_tables"].setdefault(t, {"read_by_surfaces": [], "read_by_edge_fns": [],
                                                       "written_by_surfaces": [], "written_by_edge_fns": []})
                regs["phantom_tables"][t]["written_by_surfaces"].append(surface_name)
        for r in surface["rpcs_called"]:
            if r in regs["rpcs"]:
                regs["rpcs"][r]["called_by_surfaces"].append(surface_name)

    for fn_name, fn in regs["edge_fns"].items():
        for t in fn["tables_read"]:
            if t in regs["tables"]:
                regs["tables"][t]["read_by_edge_fns"].append(fn_name)
            elif t in regs["views"]:
                regs["views"][t]["read_by_edge_fns"].append(fn_name)
            else:
                regs["phantom_tables"].setdefault(t, {"read_by_surfaces": [], "read_by_edge_fns": [],
                                                       "written_by_surfaces": [], "written_by_edge_fns": []})
                regs["phantom_tables"][t]["read_by_edge_fns"].append(fn_name)
        for t in fn["tables_written"]:
            if t in regs["tables"]:
                regs["tables"][t]["written_by_edge_fns"].append(fn_name)
            else:
                regs["phantom_tables"].setdefault(t, {"read_by_surfaces": [], "read_by_edge_fns": [],
                                                       "written_by_surfaces": [], "written_by_edge_fns": []})
                regs["phantom_tables"][t]["written_by_edge_fns"].append(fn_name)
        for r in fn["rpcs_called"]:
            if r in regs["rpcs"]:
                regs["rpcs"][r]["called_by_edge_fns"].append(fn_name)


# ─────────────────────────────────────────────────────────────────────────────
# Duplicate-signal heuristics
# ─────────────────────────────────────────────────────────────────────────────

def compute_duplicates(regs: dict) -> list[dict]:
    """Heuristics that surface likely-duplicates for human review."""
    out = []

    # 1. Surface-pair table overlap.
    surface_items = list(regs["surfaces"].items())
    for i in range(len(surface_items)):
        for j in range(i + 1, len(surface_items)):
            n1, s1 = surface_items[i]
            n2, s2 = surface_items[j]
            t1 = set(s1["tables_read"]) | set(s1["tables_written"])
            t2 = set(s2["tables_read"]) | set(s2["tables_written"])
            if len(t1) < 2 or len(t2) < 2:
                continue
            common = t1 & t2
            if len(common) < 2:
                continue
            jaccard = len(common) / len(t1 | t2)
            if jaccard >= 0.5 and len(common) >= 2:
                out.append({
                    "kind":     "surface_overlap",
                    "surface_a": n1,
                    "surface_b": n2,
                    "shared_tables": sorted(common),
                    "jaccard":  round(jaccard, 2),
                })

    # 2. Near-duplicate column names within the same table.
    for tname, tinfo in regs["tables"].items():
        cols = tinfo["columns"]
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                c1, c2 = cols[i], cols[j]
                if c1 == c2:
                    continue
                if _name_near_duplicate(c1, c2):
                    out.append({
                        "kind":   "near_duplicate_column",
                        "table":  tname,
                        "columns": [c1, c2],
                    })

    # 3. Tables with NO readers + NO writers (dead).
    for tname, tinfo in regs["tables"].items():
        if not (tinfo["read_by_surfaces"] or tinfo["read_by_edge_fns"]
                or tinfo["written_by_surfaces"] or tinfo["written_by_edge_fns"]):
            out.append({
                "kind":  "dead_table",
                "table": tname,
                "note":  "defined in migrations but not referenced in any surface or edge fn",
            })

    return out


def _name_near_duplicate(a: str, b: str) -> bool:
    """Cheap heuristic: same after dropping common suffixes (_id, _at,
    _no, etc.) or one is a prefix of the other, or token-overlap >=80%."""
    a_l, b_l = a.lower(), b.lower()
    strip_suffixes = ("_id", "_no", "_num", "_name", "_at", "_count", "_amount")
    for suf in strip_suffixes:
        if a_l.endswith(suf) and a_l[:-len(suf)] == b_l:
            return True
        if b_l.endswith(suf) and b_l[:-len(suf)] == a_l:
            return True
    # Synonym pairs we know cause drift in this codebase.
    synonyms = {
        ("manufacturer", "vendor"), ("manufacturer", "supplier"),
        ("model", "model_number"), ("serial", "serial_no"),
        ("created_at", "created_on"), ("updated_at", "updated_on"),
    }
    if (a_l, b_l) in synonyms or (b_l, a_l) in synonyms:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

def write_markdown(regs: dict, out_path: Path) -> None:
    lines = []
    lines.append("# Canonical Source Registry")
    lines.append("")
    lines.append("Authoritative inventory of every table, RPC, view, edge fn, and HTML surface on the platform.")
    lines.append("Re-built on every Mega Gate run by `tools/mine_canonical_registry.py`.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Tables:        **{len(regs['tables'])}**")
    lines.append(f"- Views:         **{len(regs['views'])}**")
    lines.append(f"- RPCs:          **{len(regs['rpcs'])}**")
    lines.append(f"- HTML surfaces: **{len(regs['surfaces'])}**")
    lines.append(f"- Edge fns:      **{len(regs['edge_fns'])}**")
    lines.append(f"- Phantom tables (referenced in code, not in migrations): **{len(regs['phantom_tables'])}**")
    lines.append(f"- Duplicate signals: **{len(regs['duplicate_signals'])}**")
    lines.append("")

    # Tables sorted by read-popularity.
    by_pop = sorted(
        regs["tables"].items(),
        key=lambda kv: -(len(kv[1]["read_by_surfaces"]) + len(kv[1]["read_by_edge_fns"]) +
                          len(kv[1]["written_by_surfaces"]) + len(kv[1]["written_by_edge_fns"])),
    )
    lines.append("## Tables (sorted by usage)")
    lines.append("")
    lines.append("| Table | Cols | RLS | Realtime | Read by surfaces | Written by surfaces | Edge-fn writers |")
    lines.append("|---|---:|---|---|---|---|---|")
    for tname, t in by_pop:
        readers = ", ".join(t["read_by_surfaces"][:4]) + (" ..." if len(t["read_by_surfaces"]) > 4 else "")
        writers = ", ".join(t["written_by_surfaces"][:3]) + (" ..." if len(t["written_by_surfaces"]) > 3 else "")
        edge_writers = ", ".join(t["written_by_edge_fns"][:3]) + (" ..." if len(t["written_by_edge_fns"]) > 3 else "")
        lines.append(f"| `{tname}` | {len(t['columns'])} | {'yes' if t['rls_enabled'] else 'no'} | "
                     f"{'yes' if t['realtime_published'] else 'no'} | {readers or '—'} | {writers or '—'} | {edge_writers or '—'} |")
    lines.append("")

    lines.append("## RPCs / Functions")
    lines.append("")
    lines.append("| Function | Args | Definer | Called by surfaces | Called by edge fns |")
    lines.append("|---|---|---|---|---|")
    for rname, r in sorted(regs["rpcs"].items()):
        args = (r["args"] or "").replace("\n", " ")[:60]
        callers = ", ".join(r["called_by_surfaces"][:3])
        edge_callers = ", ".join(r.get("called_by_edge_fns", [])[:3])
        lines.append(f"| `{rname}` | {args} | {'yes' if r['security_definer'] else 'no'} | {callers or '—'} | {edge_callers or '—'} |")
    lines.append("")

    lines.append("## HTML Surfaces")
    lines.append("")
    lines.append("| Page | Primary tables (read) | Tables written | RPCs called | Edge fns invoked |")
    lines.append("|---|---|---|---|---|")
    for sname, s in sorted(regs["surfaces"].items()):
        reads = ", ".join(s["tables_read"][:4]) + (" ..." if len(s["tables_read"]) > 4 else "")
        writes = ", ".join(s["tables_written"][:3]) + (" ..." if len(s["tables_written"]) > 3 else "")
        rpcs = ", ".join(s["rpcs_called"][:3])
        fns = ", ".join(s["edge_fns_invoked"][:3])
        lines.append(f"| `{sname}` | {reads or '—'} | {writes or '—'} | {rpcs or '—'} | {fns or '—'} |")
    lines.append("")

    if regs["phantom_tables"]:
        lines.append("## Phantom tables (referenced in code, not defined in migrations)")
        lines.append("")
        for t, info in sorted(regs["phantom_tables"].items()):
            all_readers = info["read_by_surfaces"] + info["read_by_edge_fns"] + \
                          info["written_by_surfaces"] + info["written_by_edge_fns"]
            lines.append(f"- `{t}` — referenced by: {', '.join(all_readers[:5])}")
        lines.append("")

    if regs["duplicate_signals"]:
        lines.append("## Duplicate signals -- review")
        lines.append("")
        by_kind = defaultdict(list)
        for d in regs["duplicate_signals"]:
            by_kind[d["kind"]].append(d)

        if by_kind.get("surface_overlap"):
            lines.append("### Surface-pair overlap (Jaccard >= 0.5, >= 2 shared tables)")
            lines.append("")
            lines.append("| Surface A | Surface B | Shared tables | Jaccard |")
            lines.append("|---|---|---|---:|")
            for d in sorted(by_kind["surface_overlap"], key=lambda x: -x["jaccard"]):
                lines.append(f"| `{d['surface_a']}` | `{d['surface_b']}` | {', '.join(d['shared_tables'])} | {d['jaccard']} |")
            lines.append("")

        if by_kind.get("near_duplicate_column"):
            lines.append("### Near-duplicate column names within a table")
            lines.append("")
            for d in by_kind["near_duplicate_column"]:
                lines.append(f"- `{d['table']}`: `{d['columns'][0]}` vs `{d['columns'][1]}`")
            lines.append("")

        if by_kind.get("dead_table"):
            lines.append("### Dead tables (no readers, no writers)")
            lines.append("")
            for d in by_kind["dead_table"]:
                lines.append(f"- `{d['table']}` (defined but unreferenced)")
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def mine() -> dict:
    regs = {
        "tables":           {},
        "views":            {},
        "rpcs":             {},
        "surfaces":         {},
        "edge_fns":         {},
        "phantom_tables":   {},
        "duplicate_signals": [],
    }

    # Pass 1: migrations
    if MIGRATIONS_DIR.exists():
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            parse_migration(path, regs)

    # Pass 2: HTML surfaces (root + one level deep — feedback/, learn/, etc.)
    for path in sorted(ROOT.glob("*.html")):
        if any(rx.search(path.name) for rx in HTML_EXCLUDE):
            continue
        parse_surface(path, regs)
    for subdir in sorted(ROOT.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith(".") or subdir.name in {
            "node_modules", "test-results", "playwright-report", ".tmp",
            "supabase", "tools", "python-api", "tests",
        }:
            continue
        for path in sorted(subdir.rglob("*.html")):
            if any(rx.search(path.name) for rx in HTML_EXCLUDE):
                continue
            parse_surface(path, regs)

    # Pass 3: edge fns + shared TS modules (_shared/ is also a consumer surface).
    if EDGE_FNS_DIR.exists():
        for path in sorted(EDGE_FNS_DIR.iterdir()):
            if not path.is_dir():
                continue
            if path.name == "_shared":
                # Shared TS modules consume tables/views/RPCs directly; register
                # each as a pseudo edge fn `_shared/<file>` so the cross-link
                # picks up its readers/writers.
                for ts in sorted(path.rglob("*.ts")):
                    parse_shared_ts(ts, regs)
                continue
            parse_edge_fn(path, regs)

    # Pass 4: cross-link
    cross_link(regs)
    # Dedup the reader/writer arrays.
    for t in regs["tables"].values():
        for k in ("read_by_surfaces", "written_by_surfaces", "read_by_edge_fns", "written_by_edge_fns"):
            t[k] = sorted(set(t[k]))
    for v in regs["views"].values():
        for k in ("read_by_surfaces", "read_by_edge_fns"):
            v[k] = sorted(set(v[k]))
    for r in regs["rpcs"].values():
        for k in ("called_by_surfaces", "called_by_edge_fns"):
            r.setdefault(k, [])
            r[k] = sorted(set(r[k]))

    # Pass 5: duplicate signals
    regs["duplicate_signals"] = compute_duplicates(regs)
    return regs


def main() -> int:
    regs = mine()
    OUT_JSON.write_text(json.dumps(regs, indent=2), encoding="utf-8")
    write_markdown(regs, OUT_MD)

    print(f"Canonical Source Registry Miner")
    print(f"  tables:         {len(regs['tables'])}")
    print(f"  views:          {len(regs['views'])}")
    print(f"  rpcs:           {len(regs['rpcs'])}")
    print(f"  surfaces:       {len(regs['surfaces'])}")
    print(f"  edge fns:       {len(regs['edge_fns'])}")
    print(f"  phantom tables: {len(regs['phantom_tables'])}")
    print(f"  duplicate signals: {len(regs['duplicate_signals'])}")
    print(f"  outputs:        {OUT_JSON.name}, {OUT_MD.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
