"""
verify_capture_roundtrip -- LAYER-1 VALUE-CORRECTNESS for the §13 capture tier.
=========================================================================================
WHERE THIS SITS
---------------
mine_column_terminus.py bucketed the 196 capture fields by CODE EVIDENCE; verify_column_
terminus.py cross-checked the 46 direct-mapped PERSISTED columns against the live schema.
That left **106 value-verifiable fields** (PERSISTED + PERSISTED?), of which 64 still have
an UNNAMED column (60 "indirected", 4 transform-mapped) because the miner stopped at a
nearest-signal heuristic. This tool closes that spoke.

THE METHOD (deterministic, hermetic, LOCAL -- the calc-validator philosophy applied to
capture): for every persist site `.from(table).insert/upsert/update(<payload>)` on each
surface, it EXTRACTS the actual payload object literal, maps each `column: expr` (and ES6
shorthand `column,`) pair, then resolves each expr back to a `$('field-id')` read -- through
ONE hop of local-variable assignment (`const x = $('f-id').value...; payload = { col: x }`)
and through `...spread` of a named payload var. The DB itself, via the page's real write
contract, NAMES the column -- no guessing, no heuristic.

CRUCIALLY it then classifies the read->persist PATH, because that is where value-correctness
actually lives (the FCU `cw_flow_lps` *1000 bug was a TRANSFORM bug, invisible to a terminus
map):
  • PASSTHROUGH  -- `col: $('id').value`  → value lands verbatim; correct BY CONSTRUCTION.
  • GUARD        -- `... || null`, `?? x`, `? :` default-empty, `.trim()` → safe, value-preserving.
  • BOOL         -- `.checked` → boolean coercion (expected).
  • NUMERIC      -- `Number()/parseFloat/parseInt/.toFixed`/arithmetic → VALUE-AFFECTING.
                    ★ this is the FCU bug class. FLAGGED: needs a value oracle / live round-trip.
  • STRUCT       -- `JSON.stringify/.map/_assetToNode(`/custom fn → reshaped. FLAGGED.
  • COMPUTED     -- arithmetic over MULTIPLE field reads (e.g. total = qty*price). FLAGGED.
  • NO_TERMINUS  -- field is read in the page but appears in NO persist payload = captured-
                    but-dropped = a REAL bug to investigate.
  • UNRESOLVED   -- payload extraction couldn't bind it (honest; flagged, never asserted).

HONESTY: PASSTHROUGH/GUARD/BOOL are value-correct by reading the contract -- no transform can
corrupt an identity copy, and the column is the page's own declared write target. Only the
NUMERIC/STRUCT/COMPUTED set carries value-correctness RISK and is the eligible set for the
live round-trip (submit a sentinel -> read the row back -> assert). This tool names the column
for all 64 unknowns AND isolates that risk set -- turning "round-trip 106 fragile forms" into
"prove the passthroughs by contract, value-check only the transforms."

Reads column_terminus.json (the target set) + each surface .html. Hermetic (no DB/network).
Writes capture_roundtrip.json + capture_roundtrip.md + a console verdict.
Cross-checks the 42 schema-db_confirmed columns: the resolver MUST agree, or it FAILs loudly.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CT = ROOT / "column_terminus.json"

# ── element-read tokens (same family the miner recognises) ───────────────────
#   $('id')  $("id")  getElementById('id')  querySelector('#id'|'id')
def field_read_in(expr: str) -> str | None:
    """Return the FIRST field id read inside `expr`, or None."""
    m = re.search(r"(?:getElementById|querySelector(?:All)?|\$)\(\s*['\"]#?([\w-]+)['\"]", expr)
    return m.group(1) if m else None


# ── tiny JS literal helpers (string/template/nesting aware) ──────────────────
def strip_comments(s: str) -> str:
    """Remove // line and /* block */ comments WITHOUT touching string/template bodies.
    Critical: a comment apostrophe (`aren't`) or brace would otherwise corrupt the
    string/brace state machines used for payload extraction (real inventory.html bug)."""
    out = []
    i, n, quote = 0, len(s), None
    while i < n:
        c = s[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1]); i += 2; continue
            if c == quote:
                quote = None
            i += 1; continue
        if c in "'\"`":
            quote = c; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c); i += 1
    return "".join(out)


def _match_brace(text: str, open_idx: int) -> int:
    """Given index of an opening { [ (, return index of its matching close, or -1."""
    pairs = {"{": "}", "[": "]", "(": ")"}
    close = pairs[text[open_idx]]
    depth = 0
    i = open_idx
    n = len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_commas(body: str) -> list[str]:
    """Split an object-literal body on TOP-LEVEL commas (ignore nested/quoted)."""
    out, depth, start, quote = [], 0, 0, None
    i = 0
    while i < len(body):
        c = body[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        elif c == "," and depth == 0:
            out.append(body[start:i])
            start = i + 1
        i += 1
    if body[start:].strip():
        out.append(body[start:])
    return out


def _top_colon(seg: str) -> int:
    """Index of the FIRST top-level ':' in seg (for key:value), or -1 (shorthand)."""
    depth, quote = 0, None
    i = 0
    while i < len(seg):
        c = seg[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        elif c == ":" and depth == 0:
            # avoid ternary '?:' false hit: a key-colon has an identifier/string key before it
            return i
        i += 1
    return -1


KEY_RE = re.compile(r"^['\"]?([A-Za-z_]\w*)['\"]?$")


def parse_object(body: str) -> list[tuple[str, str]]:
    """Parse object-literal body -> list of (key, value_expr). Shorthand `x` -> (x, x).
    Spread `...v` -> ('...', v). Skips method defs / computed keys (honest)."""
    pairs = []
    for seg in _split_top_commas(body):
        s = seg.strip()
        if not s:
            continue
        if s.startswith("..."):
            pairs.append(("...", s[3:].strip()))
            continue
        ci = _top_colon(s)
        if ci == -1:
            km = KEY_RE.match(s)
            if km:
                pairs.append((km.group(1), s))  # shorthand: value expr == the identifier
            continue
        key_raw, val = s[:ci].strip(), s[ci + 1:].strip()
        km = KEY_RE.match(key_raw)
        if km:
            pairs.append((km.group(1), val))
    return pairs


PERSIST_RE = re.compile(r"\.from\(\s*['\"]([\w.]+)['\"]\s*\)\s*\.\s*(insert|upsert|update)\s*\(")


def extract_payloads(text: str) -> list[dict]:
    """Find every persist site; return [{table, op, pos, body, mapper}] with the payload object
    literal resolved (inline `{...}` / `[{...}]` / a named var / a `mapperFn({...})` wrapper)."""
    payloads = []
    for m in PERSIST_RE.finditer(text):
        table, op = m.group(1), m.group(2)
        paren = m.end() - 1                      # index of the '(' after insert/upsert/update
        close = _match_brace(text, paren)
        if close == -1:
            continue
        arg = text[paren + 1:close].strip()
        body, mapper = _resolve_obj(text, arg, m.start())
        if body is not None:
            payloads.append({"table": table, "op": op, "pos": m.start(), "body": body,
                             "mapper": mapper, "line": text.count("\n", 0, m.start()) + 1})
    return payloads


_CALL_RE = re.compile(r"^([A-Za-z_]\w*)\s*\(")


def _resolve_obj(text: str, arg: str, site: int, depth: int = 0) -> tuple[str | None, str | None]:
    """arg is the expression inside insert(...). Return (OBJECT BODY, mapper_name).
    Unwraps `[{...}]`, a `mapperFn(<inner>)` call (records mapper), and a bare `varName`
    traced to `const varName = {...}` — recursing through `const row = toDBRow(item)`
    (var → mapper-call → var → literal), depth-guarded."""
    if depth > 6:
        return None, None
    a = arg.strip()
    mapper = None
    cm = _CALL_RE.match(a)
    if cm and cm.group(1) not in ("Array", "Object", "Number", "String", "Boolean", "JSON"):
        opn = a.index("(")
        cl = _match_brace(a, opn)
        if cl != -1:
            mapper = cm.group(1)
            a = a[opn + 1:cl].strip()
    if a.startswith("["):
        a = a[a.index("{"):] if "{" in a else ""
    if a.startswith("{"):
        ob = _match_brace(a, 0)
        return (a[1:ob] if ob != -1 else None), mapper
    vm = re.match(r"([A-Za-z_]\w*)\s*$", a)
    if vm:
        body = find_obj_literal(text, vm.group(1), site)
        if body is not None:
            return body, mapper
        defexpr = resolve_var(text, vm.group(1), site)   # e.g. row = toDBRow(item)
        if defexpr and defexpr != a:
            b2, m2 = _resolve_obj(text, defexpr, site, depth + 1)
            return b2, (mapper or m2)
    return None, mapper


def resolve_var(text: str, var: str, before: int) -> str | None:
    """nearest preceding `const|let|var VAR = <expr>;` -> the expr (for one-hop field trace)."""
    best = None
    for dm in re.finditer(rf"\b(?:const|let|var)\s+{re.escape(var)}\s*=\s*([^\n;]+)", text[:before]):
        best = dm
    return best.group(1).strip() if best else None


def find_obj_literal(text: str, var: str, before: int) -> str | None:
    """nearest preceding `const|let|var VAR = { ... }` -> the OBJECT BODY (between braces)."""
    defs = list(re.finditer(rf"\b(?:const|let|var)\s+{re.escape(var)}\s*=\s*\{{", text[:before]))
    if not defs:
        return None
    opn = defs[-1].end() - 1
    cl = _match_brace(text, opn)
    return text[opn + 1:cl] if cl != -1 else None


_TRACE_STOP = {"value", "checked", "trim", "Number", "parseFloat", "parseInt", "null",
               "document", "getElementById", "querySelector", "querySelectorAll",
               "toFixed", "Math", "isFinite", "true", "false", "JSON", "stringify"}


def trace_field(text: str, expr: str, site: int, depth: int = 0):
    """Resolve a value expr to its underlying $('field-id') read, following local-variable
    assignments up to 3 hops (e.g. `price = parseFloat(priceRaw)` ← `priceRaw = $('post-price')`).
    Returns (field_id, combined_expr) where combined_expr concatenates the whole chain so a
    transform anywhere in it (parseFloat at hop-1) is still visible to classify_transform."""
    fid = field_read_in(expr)
    if fid:
        return fid, expr
    if depth >= 3:
        return None, expr
    # Follow ONLY standalone identifiers (a bare var holding the value) — NOT one accessed
    # via `.prop` or `(`. This is the guard against false binds: `tag_id: node.tag || null`
    # must NOT trace `node` (a `.find()` result) back to an unrelated field. `sev`/`priceRaw`
    # (standalone) still resolve.
    for ident in dict.fromkeys(re.findall(r"(?<![.\w])([A-Za-z_]\w*)(?![\w.(])", expr)):
        if ident in _TRACE_STOP:
            continue
        vexpr = resolve_var(text, ident, site)
        if vexpr and vexpr.strip() != expr.strip():
            f2, e2 = trace_field(text, vexpr, site, depth + 1)
            if f2:
                return f2, (expr + " ⟵ " + e2)
    return None, expr


def parse_mapper(text: str, name: str) -> dict:
    """For a payload built via `mapperFn(obj)` (e.g. logbook `_assetToNode`), return
    {intermediate_key: db_column} by parsing the mapper's own `dbcol: param.key` renames.
    This NAMES the real DB column for transform-mapped fields (a.type → iso_class)."""
    m = re.search(rf"function\s+{re.escape(name)}\s*\(\s*(\w+)", text) or \
        re.search(rf"\b{re.escape(name)}\s*=\s*\(?\s*(\w+)\s*\)?\s*=>", text)
    if not m:
        return {}
    param = m.group(1)
    region = text[m.end():m.end() + 4000]
    rename = {}
    for pm in re.finditer(rf"([A-Za-z_]\w*)\s*:\s*[^,;{{]*\b{re.escape(param)}\.([A-Za-z_]\w*)", region):
        rename.setdefault(pm.group(2), pm.group(1))   # {param.key : dbcol}
    return rename


def flatten_payload(text: str, body: str, site: int, depth: int = 0) -> list[tuple[str, str]]:
    """Parse a payload object-literal body into (column, value_expr), FOLLOWING `...spread`
    of a named object-literal variable (the inventory/logbook pattern:
    `payload = {col: $('id')}` → `item = {...payload}` → `upsert({...item})`)."""
    pairs = []
    for key, val in parse_object(body):
        if key == "...":
            m = re.match(r"^([A-Za-z_]\w*)", val.strip())
            if m and depth < 5:
                inner = find_obj_literal(text, m.group(1), site)
                if inner is not None:
                    pairs.extend(flatten_payload(text, inner, site, depth + 1))
            continue
        pairs.append((key, val))
    return pairs


def _distinct_field_reads(e: str) -> set:
    return set(re.findall(r"(?:getElementById|querySelector(?:All)?|\$)\(\s*['\"]#?([\w-]+)['\"]", e))


def classify_transform(expr: str, fid: str) -> str:
    """Classify the read→persist path. SAFE (value-preserving) → CONTRACT_VERIFIED:
       PASSTHROUGH (`.value`), GUARD (`.trim()`, `||default`, `?? x`, empty-guard ternary),
       BOOL (`.checked`). VALUE-AFFECTING → NEEDS_VALUE_CHECK:
       STRUCT (JSON.stringify/.map/combine/_assetToNode), COMPUTED (>1 distinct field),
       SCALED (single field × / arithmetic — the FCU bug class), NUMERIC (Number/parseInt
       coercion of one field)."""
    e = expr.strip().rstrip(",;")
    fids = _distinct_field_reads(e)
    if ".checked" in e:
        return "BOOL"
    if re.search(r"\bJSON\.stringify\b|\.map\s*\(|_assetToNode|combineNotes|\b_to[A-Z]\w*\(", e):
        return "STRUCT"
    if len(fids) > 1:
        return "COMPUTED"
    # strip the field read token (incl. `document.` prefix + optional chaining `?.value`)
    bare = re.sub(r"(?:document\.)?(?:getElementById|querySelector(?:All)?|\$)\([^)]*\)\s*\??\.?(?:value|checked)?",
                  "", e)
    has_coerce = bool(re.search(r"\bNumber\s*\(|\bparseFloat\b|\bparseInt\b|\.toFixed\s*\(", e))
    has_scale = bool(re.search(r"[*/]|[-+]\s*\d", bare))  # arithmetic on the value, post-strip
    if has_scale:
        return "SCALED"
    if has_coerce:
        return "NUMERIC"
    # value-preserving wrappers: .trim(), `|| <fallback>`, `?? <fallback>`, empty-guard ternary,
    # and (for multi-hop chains `outerVar ⟵ $('id')…`) bare variable references flowing through.
    b = bare.replace("⟵", " ")
    b = re.sub(r"\.trim\(\)", "", b)
    b = re.sub(r"\|\|\s*[^|;,)⟵]+", "", b)     # `|| ''`, `|| null`, `|| existing?.x`, `|| type`
    b = re.sub(r"\?\?\s*[^?;,)⟵]+", "", b)       # `?? x`
    b = re.sub(r"[?:]", "", b)
    b = re.sub(r"[A-Za-z_]\w*(?:\?\.\w+|\.\w+)*", "", b)   # bare var/prop refs (the value passing through)
    b = re.sub(r"!==?|===?|''|\"\"|,|10|0", "", b)
    b = b.replace("(", "").replace(")", "").replace(".", "").strip()
    if b == "":
        return "GUARD" if re.search(r"\.trim\(\)|\|\||\?\?|\?|⟵", e) else "PASSTHROUGH"
    return "OTHER"


SURFACE_FILE = lambda s: ROOT / f"{s}.html"

_NUMERIC_DB = ("numeric", "integer", "double", "real", "bigint", "smallint", "decimal")


def live_schema_check(rows: list[dict]) -> dict:
    """LIVE (`--live`): confirm every resolved (table,column) exists in the real edge DB and
    that value-check NUMERIC fields land in numeric columns (so coercion round-trips). Uses
    `docker exec supabase_db_workhive psql` — the same ground-truth path as journey_trace."""
    out = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", "select table_name||'|'||column_name||'|'||data_type from "
         "information_schema.columns where table_schema='public';"],
        capture_output=True, text=True)
    if out.returncode != 0:
        print(f"  docker psql failed: {out.stderr.strip()[:160]} — skipping --live")
        return {}
    schema = {}
    for ln in out.stdout.splitlines():
        ln = ln.strip()
        if ln.count("|") == 2:
            t, c, dt = ln.split("|"); schema[(t, c)] = dt
    pairs = sorted({(r["resolved_table"], r["resolved_column"]) for r in rows
                    if r.get("resolved_column") and r.get("resolved_table")})
    missing, numeric_bad = [], []
    for r in rows:
        if not (r.get("resolved_column") and r.get("resolved_table")):
            continue
        dt = schema.get((r["resolved_table"], r["resolved_column"]))
        r["db_type"] = dt
        r["db_exists"] = dt is not None
        if dt is None:
            missing.append(f"{r['resolved_table']}.{r['resolved_column']} ({r['surface']}:{r['field']})")
        elif r.get("transform") == "NUMERIC" and not any(k in dt for k in _NUMERIC_DB):
            numeric_bad.append(f"{r['surface']}:{r['field']} → {r['resolved_table']}.{r['resolved_column']} is {dt}")
    return {"pairs_checked": len(pairs), "missing": missing, "numeric_mismatch": numeric_bad,
            "exist": len(pairs) - len({m.split(' ')[0] for m in missing})}


def main() -> int:
    if not CT.exists():
        print("  column_terminus.json missing — run mine_column_terminus.py first")
        return 1
    d = json.loads(CT.read_text(encoding="utf-8"))
    targets = [f for f in d["fields"] if f["bucket"] in ("PERSISTED", "PERSISTED?")]
    by_surface = defaultdict(list)
    for f in targets:
        by_surface[f["surface"]].append(f)

    # cache payload maps per surface: field_id -> {table, column, expr, transform}
    resolved: dict[tuple[str, str], dict] = {}
    page_reads: dict[str, set] = {}            # field ids that ARE read on the page (for NO_TERMINUS)
    mapper_cache: dict[tuple[str, str], dict] = {}
    surface_text: dict[str, str] = {}
    for surface in by_surface:
        page = SURFACE_FILE(surface)
        if not page.exists():
            continue
        text = strip_comments(page.read_text(encoding="utf-8", errors="replace"))
        surface_text[surface] = text
        page_reads[surface] = set()
        payloads = extract_payloads(text)
        for p in payloads:
            for col, val in flatten_payload(text, p["body"], p["pos"]):
                # resolve the value to a $('field-id') read, following up to 3 var hops
                # (handles `severity: …sev…` ⟵ `sev=parseInt($('fmea-severity'))` and
                #  `price,` ⟵ `price=parseFloat(priceRaw)` ⟵ `priceRaw=$('post-price')`).
                fid, expr = trace_field(text, val, p["pos"])
                if not fid:
                    continue
                page_reads[surface].add(fid)
                col_final, tclass, via = col, classify_transform(expr, fid), None
                if p.get("mapper"):                       # payload built via a mapper fn
                    key_m = (surface, p["mapper"])
                    if key_m not in mapper_cache:
                        mapper_cache[key_m] = parse_mapper(text, p["mapper"])
                    col_final = mapper_cache[key_m].get(col, col)
                    via = p["mapper"]
                    if col_final != col:                  # a real rename = value-affecting
                        tclass = "RENAME"
                key = (surface, fid)
                if key not in resolved:
                    rec = {"table": p["table"], "column": col_final, "op": p["op"],
                           "line": p["line"], "expr": expr.strip()[:120], "transform": tclass}
                    if via:
                        rec["via_mapper"] = via
                        rec["mapper_in_key"] = col
                    resolved[key] = rec

    # CROSS-FUNCTION FALLBACK: for targets the persist-anchored pass could not bind (the
    # persist is decoupled from the field-read by a function boundary, e.g. dayplanner
    # `meeting = {startTime:$('m-start')…}` → syncItemToSupabase(meeting) → toDBRow → upsert),
    # find the direct `KEY: <…$('fid')…>` object-property literal anywhere on the page. That
    # shape is the persist payload key (render templates use textContent/innerHTML, not
    # `col:$('id').value`), and the miner already proved the field reaches a persister. Tagged
    # `xfn` (lower confidence than persist-anchored; excluded from the schema cross-check).
    for f in targets:
        key = (f["surface"], f["field"])
        if key in resolved or f["surface"] not in surface_text:
            continue
        fid = f["field"]
        prop = re.compile(r"([A-Za-z_]\w*)\s*:\s*([^,;{}\n]*?(?:getElementById|querySelector(?:All)?|\$)"
                          r"\(\s*['\"]#?" + re.escape(fid) + r"['\"][^,;{}\n]*)")
        m = prop.search(surface_text[f["surface"]])
        if m:
            col, expr = m.group(1), m.group(2).strip()
            resolved[key] = {"table": f.get("table"), "column": col, "op": "insert",
                             "line": surface_text[f["surface"]].count("\n", 0, m.start()) + 1,
                             "expr": expr[:120], "transform": classify_transform(expr, fid),
                             "mode": "xfn"}

    # build the report rows, cross-checking the schema-db_confirmed set
    rows, mismatches = [], []
    tcount = Counter()
    for f in targets:
        key = (f["surface"], f["field"])
        r = resolved.get(key)
        out = {"surface": f["surface"], "field": f["field"], "bucket": f["bucket"],
               "claimed_table": f.get("table"), "claimed_column": f.get("column"),
               "schema_state": f.get("table_verified")}
        if not r:
            out["roundtrip"] = "UNRESOLVED"
            out["resolved_column"] = None
            tcount["UNRESOLVED"] += 1
        else:
            out.update(resolved_table=r["table"], resolved_column=r["column"],
                       source_expr=r["expr"], transform=r["transform"],
                       persist=f"{r['table']}.{r['op']}() @L{r['line']}")
            if r.get("via_mapper"):
                out["via_mapper"] = r["via_mapper"]
                out["mapper_in_key"] = r["mapper_in_key"]
            if r.get("mode") == "xfn":
                out["mode"] = "xfn"
            risky = r["transform"] in ("NUMERIC", "SCALED", "STRUCT", "COMPUTED", "RENAME", "OTHER")
            out["roundtrip"] = "NEEDS_VALUE_CHECK" if risky else "CONTRACT_VERIFIED"
            tcount[out["roundtrip"]] += 1
            # cross-check: a db_confirmed direct-mapped column must match what we resolve
            # (persist-anchored only; xfn fallback names the intermediate key, not asserted)
            if f.get("table_verified") == "db_confirmed" and f.get("column") and r.get("mode") != "xfn":
                if r["column"] != f["column"] or r["table"] != f.get("table"):
                    mismatches.append(f"{f['surface']}:{f['field']} schema-confirmed "
                                      f"{f.get('table')}.{f['column']} but payload resolves "
                                      f"{r['table']}.{r['column']}")
        rows.append(out)

    transforms = Counter(r.get("transform") for r in rows if r.get("transform"))
    needs = [r for r in rows if r["roundtrip"] == "NEEDS_VALUE_CHECK"]
    unresolved = [r for r in rows if r["roundtrip"] == "UNRESOLVED"]

    print("=" * 82)
    print("  §13 CAPTURE VALUE-CORRECTNESS — payload-contract resolution of the 106 set")
    print("=" * 82)
    print(f"\n  targets (PERSISTED + PERSISTED?): {len(targets)}")
    print(f"\n  ── roundtrip disposition ──")
    for k in ("CONTRACT_VERIFIED", "NEEDS_VALUE_CHECK", "UNRESOLVED"):
        print(f"     {k:18} {tcount.get(k, 0):3}")
    print(f"\n  ── transform class (read→persist path) ──")
    for k, v in transforms.most_common():
        print(f"     {k:12} {v:3}")
    print(f"\n  columns NEWLY NAMED (were indirected/transform-mapped, now resolved): "
          f"{sum(1 for r in rows if r.get('resolved_column') and not r.get('claimed_column'))}")
    if needs:
        print(f"\n  ── NEEDS_VALUE_CHECK (value-affecting transform — the eligible live-round-trip set) ──")
        for r in needs:
            print(f"     {r['surface']:16} {r['field']:22} → {r.get('resolved_table')}."
                  f"{r.get('resolved_column')}  [{r.get('transform')}]  {r.get('source_expr')}")
    if unresolved:
        print(f"\n  ── still UNRESOLVED (payload bind failed — honest) ──")
        for r in unresolved:
            print(f"     {r['surface']}:{r['field']}")
    if mismatches:
        print(f"\n  ✗✗ CROSS-CHECK MISMATCH vs schema-db_confirmed ({len(mismatches)}) — investigate:")
        for mm in mismatches:
            print(f"     {mm}")
    else:
        print(f"\n  ✓ cross-check: every schema-db_confirmed column agrees with the resolved payload column")

    live = {}
    if "--live" in sys.argv:
        live = live_schema_check(rows)
        if live:
            print(f"\n  ── LIVE schema verification (docker psql, real edge DB) ──")
            print(f"     resolved (table,column) pairs checked : {live['pairs_checked']}")
            print(f"     EXIST in live schema                  : {live['exist']}")
            print(f"     MISSING (resolver named a phantom col): {len(live['missing'])}")
            for m in live["missing"]:
                print(f"        ✗ {m}")
            print(f"     value-check NUMERIC → numeric column  : "
                  f"{'all OK' if not live['numeric_mismatch'] else str(len(live['numeric_mismatch']))+' MISMATCH'}")
            for m in live["numeric_mismatch"]:
                print(f"        ⚠ {m}")

    out = {
        "_doc": "§13 capture value-correctness — payload-contract resolution. Names the exact "
                "column for the indirected/transform-mapped fields by parsing the real insert/upsert "
                "payload + one-hop variable trace, and classifies the read→persist path. "
                "CONTRACT_VERIFIED = passthrough/guard/bool (value-correct by construction). "
                "NEEDS_VALUE_CHECK = value-affecting transform (the eligible live-round-trip set; "
                "the FCU bug class). UNRESOLVED = honest bind failure.",
        "targets": len(targets),
        "disposition": dict(tcount),
        "transform_classes": dict(transforms),
        "cross_check_mismatches": mismatches,
        "live_verification": live,
        "fields": rows,
    }
    (ROOT / "capture_roundtrip.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # markdown summary
    md = ["# §13 Capture Value-Correctness — payload-contract resolution\n",
          "> For each of the 106 value-verifiable capture fields (PERSISTED + PERSISTED?), the exact "
          "DB column is resolved by parsing the surface's REAL insert/upsert payload (spread-following, "
          "≤3-hop variable trace, mapper-rename modeling), and the read→persist path is classified. "
          "PASSTHROUGH/GUARD/BOOL = value-correct by construction; NUMERIC/RENAME/STRUCT = value-affecting "
          "(the FCU bug class, eligible for the live round-trip). Cross-checked vs the schema-confirmed set.\n",
          "## Disposition\n", "| Disposition | Count | Meaning |", "|---|---|---|",
          f"| CONTRACT_VERIFIED | {tcount.get('CONTRACT_VERIFIED',0)} | passthrough/guard/bool — no transform can corrupt the value |",
          f"| NEEDS_VALUE_CHECK | {tcount.get('NEEDS_VALUE_CHECK',0)} | value-affecting transform — eligible live-round-trip set |",
          f"| UNRESOLVED | {tcount.get('UNRESOLVED',0)} | persist decoupled (positional args / computed branch / file upload) — honest |",
          "",
          f"**Columns newly named** (were indirected/transform-mapped): "
          f"{sum(1 for r in rows if r.get('resolved_column') and not r.get('claimed_column'))}. "
          f"**Cross-check**: {'PASS — all schema-confirmed columns agree' if not mismatches else str(len(mismatches))+' MISMATCH'}.\n"]
    if live:
        md += [f"**Live (docker psql)**: {live['exist']}/{live['pairs_checked']} resolved columns exist in the "
               f"real edge DB; value-check NUMERIC→numeric column "
               f"{'all OK' if not live['numeric_mismatch'] else str(len(live['numeric_mismatch']))+' MISMATCH'}.\n"]
    md += ["## NEEDS_VALUE_CHECK (the value-affecting transforms)\n",
           "| Surface | Field | → Column | Class | Source |", "|---|---|---|---|---|"]
    for r in needs:
        md.append(f"| {r['surface']} | {r['field']} | {r.get('resolved_table')}.{r.get('resolved_column')} "
                  f"| {r.get('transform')} | `{(r.get('source_expr') or '')[:80]}` |")
    md += ["\n## UNRESOLVED (persist decoupled from field-read — honest)\n",
           "| Surface | Field |", "|---|---|"]
    for r in unresolved:
        md.append(f"| {r['surface']} | {r['field']} |")
    (ROOT / "capture_roundtrip.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\n  ✓ wrote capture_roundtrip.json + capture_roundtrip.md")
    print("=" * 82)
    fail = bool(mismatches) or bool(live.get("missing")) or bool(live.get("numeric_mismatch"))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
