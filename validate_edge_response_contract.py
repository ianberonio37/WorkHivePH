"""
Edge Function Response Contract Validator — WorkHive Platform
==============================================================
Mirror of the caller contract gate (validate_edge_caller_contract): every
page that consumes `result.data.X` after `await db.functions.invoke('foo', ...)`
should reference a field the function actually returns. When the function's
response shape changes (a field gets renamed, removed, or wrapped in an
envelope), callers that still read the old field get `undefined` and
silently produce wrong results.

Same silent-failure class as schema phantom + caller contract + realtime
payload contract. The contract triangle is now a square: caller body,
function destructure, function return, caller consumption — all four sides
under static enforcement.

  Layer 1 — Function has return paths
    1.  Every invoked edge function has at least one detectable
        `return new Response(JSON.stringify(...))` so the validator
        can analyse its shape.
    [WARN] Function has no discoverable return — possibly malformed or
    uses an unusual return pattern (e.g. throws unconditionally, returns
    bare strings).

  Layer 2 — Caller fields exist in function returns
    2.  Every `data.X` (and destructured `const { X } = data`) in caller
        code references a field that appears in at least one of the
        function's object-literal return paths.
    [FAIL] Caller reads a phantom field — function never returns X;
    caller silently gets undefined.
    Functions whose returns include opaque variable forms
    (`JSON.stringify(payload)` where payload is built incrementally) are
    SKIPPED — static analysis can't enumerate their fields safely.

  Layer 3 — Static introspection coverage
    3.  Track the fraction of edge functions whose returns are all
        object literals (fully analysable) vs functions with any opaque
        variable return. Informational metric — high opaque fraction
        means L2 catches less than it could; refactoring opaque returns
        to direct object literals improves contract enforcement.
    [INFO] Coverage <50% — most functions are too dynamic to gate.

  Layer 4 — Error envelope consistency
    4.  Every function whose direct-literal returns include `error: ...`
        also has at least one non-error return shape (so callers that
        consume `data.X` aren't always landing on the error envelope by
        accident).
    [WARN] Function only returns error shapes — caller `.error` checks
    and the success path are inconsistent.

Usage:  python validate_edge_response_contract.py
Output: edge_response_contract_report.json
"""
from __future__ import annotations
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT          = os.path.dirname(os.path.abspath(__file__))
FUNCTIONS_DIR = os.path.join(ROOT, "supabase", "functions")


# Functions whose responses are intentionally untyped (binary, streaming,
# always passthrough). Caller never destructures fields from these.
RESPONSE_OPAQUE_OK: dict = {
    "voice-transcribe":    "Returns plain text transcript, not JSON",
    "engineering-bom-sow": "Returns large structured BOM/SOW; caller reads via data.bom_lines etc — too dynamic to fully gate statically",
}


# Caller field-access patterns that don't map to a real function return:
# - `data.error` — universal envelope from edge_contracts validator
# - `data.message` — error message convention
# - Built-in Promise/JS shapes
NEUTRAL_CALLER_FIELDS: set = {
    "error",        # error envelope (validate_edge_contracts owns this)
    "message",      # alternate error message field
    "status",       # HTTP status sometimes returned
    "ok",           # convention for success boolean
}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _list_edge_functions() -> list[str]:
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    out: list[str] = []
    for name in sorted(os.listdir(FUNCTIONS_DIR)):
        if name.startswith("_"):
            continue
        if not os.path.isfile(os.path.join(FUNCTIONS_DIR, name, "index.ts")):
            continue
        out.append(name)
    return out


def _list_caller_files() -> list[str]:
    out: list[str] = []
    for fname in os.listdir(ROOT):
        if fname in {"engineering-design-test.html", "hive-test.html"}:
            continue
        if not (fname.endswith(".html") or fname.endswith(".js")):
            continue
        out.append(os.path.join(ROOT, fname))
    return out


# ─── Function side: extract return-shape signature ───────────────────────────

# Match `return new Response(JSON.stringify(<payload>)`. Capture the payload
# text and the position right after `JSON.stringify(`.
RETURN_RESPONSE_RE = re.compile(
    r"return\s+new\s+Response\s*\(\s*JSON\.stringify\s*\(",
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_]\w*")


def _find_matching_paren(src: str, open_paren_pos: int) -> int:
    """Walk character-by-character to find the matching `)`. Aware of JS
    strings, template literals, and comments. Tracks paren + brace depth."""
    if open_paren_pos < 0 or open_paren_pos >= len(src) or src[open_paren_pos] != "(":
        return -1
    depth = 0
    i = open_paren_pos
    in_string: str = ""
    while i < len(src):
        ch = src[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = ""
            i += 1
            continue
        if ch == "/" and i + 1 < len(src):
            if src[i + 1] == "/":
                nl = src.find("\n", i)
                i = nl + 1 if nl != -1 else len(src)
                continue
            if src[i + 1] == "*":
                end = src.find("*/", i + 2)
                i = end + 2 if end != -1 else len(src)
                continue
        if ch in "\"'`":
            in_string = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _find_matching_brace(src: str, open_brace_pos: int) -> int:
    if open_brace_pos < 0 or open_brace_pos >= len(src) or src[open_brace_pos] != "{":
        return -1
    depth = 0
    i = open_brace_pos
    in_string: str = ""
    while i < len(src):
        ch = src[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = ""
            i += 1
            continue
        if ch == "/" and i + 1 < len(src):
            if src[i + 1] == "/":
                nl = src.find("\n", i)
                i = nl + 1 if nl != -1 else len(src)
                continue
            if src[i + 1] == "*":
                end = src.find("*/", i + 2)
                i = end + 2 if end != -1 else len(src)
                continue
        if ch in "\"'`":
            in_string = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _extract_object_literal_keys(literal_text: str) -> tuple[set[str], bool]:
    """Top-level keys from a JS object literal `{ k1: ..., k2: ..., ...rest }`.
    Strips nested objects/arrays so commas inside don't fool the splitter.
    Skips spread (`...x`) and computed (`[expr]`) keys.

    Returns (keys, has_spread). When has_spread is True, the literal pulls in
    additional keys from a variable (e.g. `...stub` spreads stub's keys); the
    caller treats this as opaque because static analysis can't enumerate the
    spread source's keys without type-tracking."""
    out: set[str] = set()
    has_spread = False
    depth = 0
    flat = []
    for ch in literal_text:
        if ch in "{[":
            depth += 1
            if depth == 1:
                continue
        if ch in "}]":
            depth -= 1
            if depth == 0:
                continue
        if depth == 1:
            flat.append(ch)
    inside = "".join(flat)
    for part in inside.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("..."):
            has_spread = True
            continue
        m = re.match(r"['\"]?(\w+)['\"]?\s*[:,]?", part)
        if m:
            out.add(m.group(1))
    return out, has_spread


def _extract_function_return_shape(func_name: str) -> dict:
    """Return:
      {
        "literal_keys": set[str]   # union of keys across all object-literal returns
        "opaque":       bool       # True if at least one return is JSON.stringify(<var>)
        "has_returns":  bool       # True if any return new Response(JSON.stringify(...)) found
        "error_only":   bool       # True if all literal returns include 'error' (no success shape)
        "literal_paths": int       # count of analysable returns
      }
    """
    src = _read(os.path.join(FUNCTIONS_DIR, func_name, "index.ts"))
    if not src:
        return {"literal_keys": set(), "opaque": False, "has_returns": False,
                "error_only": False, "literal_paths": 0}
    literal_keys: set[str] = set()
    literal_returns: list[set[str]] = []
    opaque = False
    has_returns = False
    for m in RETURN_RESPONSE_RE.finditer(src):
        # We're at `JSON.stringify(` — the payload begins one char ahead.
        payload_start = m.end()
        # Fast-forward past whitespace
        while payload_start < len(src) and src[payload_start].isspace():
            payload_start += 1
        if payload_start >= len(src):
            continue
        has_returns = True
        ch = src[payload_start]
        if ch == "{":
            close = _find_matching_brace(src, payload_start)
            if close == -1:
                continue
            literal = src[payload_start: close + 1]
            keys, has_spread = _extract_object_literal_keys(literal)
            if has_spread:
                # `{ a, b, ...rest }` pulls in unknown keys from `rest`.
                # We collect the explicit keys (a, b) but mark the function
                # opaque so L2 doesn't false-flag callers reading spread-
                # supplied fields like weibull-fitter's `data.failure_pattern`.
                opaque = True
            if keys:
                literal_keys |= keys
                literal_returns.append(keys)
        else:
            # Could be an identifier (opaque) or another expression
            id_m = IDENTIFIER_RE.match(src[payload_start:])
            if id_m and id_m.group(0) not in {"null", "true", "false"}:
                opaque = True
    error_only = bool(literal_returns) and all("error" in keys for keys in literal_returns)
    return {
        "literal_keys": literal_keys,
        "opaque":       opaque,
        "has_returns":  has_returns,
        "error_only":   error_only,
        "literal_paths": len(literal_returns),
    }


# ─── Caller side: extract data field accesses ────────────────────────────────

# Match the destructure pattern `const { data, error } = await db.functions.invoke('fn', ...)`
# and `const { data: ALIAS, error } = ...` for renamed access.
INVOKE_AWAIT_RE = re.compile(
    r"""const\s*\{\s*data(?:\s*:\s*(?P<alias>\w+))?\s*(?:,\s*error\s*)?\}\s*=\s*await\s+
        \w+\.functions\.invoke\(\s*['"`](?P<fn>[\w-]+)['"`]""",
    re.VERBOSE,
)


_BOUNDARY_RE = re.compile(
    # Stop the window at the next callsite that re-defines `data` in a
    # different scope. Common boundaries:
    #   - another `await db.functions.invoke(`
    #   - a `db.from(...)` chain ending in `.then(({ data }) => ...)`
    #     (re-binds `data` to a different shape)
    #   - a function declaration (`async function foo` / `function foo` /
    #     ` foo() {` arrow-function declaration in object literal)
    # First match closes the previous caller's scope.
    r"\bawait\s+\w+\.functions\.invoke\s*\(|"
    r"\.then\s*\(\s*\(\s*\{\s*data\b|"
    r"\b(?:async\s+)?function\s+\w+\s*\("
)


def _collect_caller_field_accesses() -> list[dict]:
    """For each invoke callsite, scan a window of lines after it for
    `<data_name>.<field>` accesses. Returns list of dicts with the fields
    each callsite consumes.

    Window is bounded by the next scope-changing event so re-definitions of
    `data` in other functions / handlers don't leak into the contract."""
    out: list[dict] = []
    for path in _list_caller_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        for m in INVOKE_AWAIT_RE.finditer(src):
            data_name = m.group("alias") or "data"
            fn = m.group("fn")
            line = src[: m.start()].count("\n") + 1
            window_start = m.end()
            # Window upper bound: the next scope boundary OR a hard cap.
            hard_cap = min(len(src), window_start + 2500)
            bm = _BOUNDARY_RE.search(src, window_start, hard_cap)
            window_end = bm.start() if bm else hard_cap
            window = src[window_start: window_end]
            field_re = re.compile(rf"\b{re.escape(data_name)}\??\.\s*(\w+)")
            destruct_re = re.compile(rf"const\s*\{{([^}}]+)\}}\s*=\s*{re.escape(data_name)}\b")
            fields: set[str] = set()
            for fm in field_re.finditer(window):
                fields.add(fm.group(1))
            for dm in destruct_re.finditer(window):
                for piece in dm.group(1).split(","):
                    piece = piece.strip()
                    if not piece:
                        continue
                    name_m = re.match(r"['\"]?(\w+)['\"]?", piece)
                    if name_m:
                        fields.add(name_m.group(1))
            out.append({
                "file":   rel,
                "line":   line,
                "fn":     fn,
                "fields": fields,
            })
    return out


# ─── Layer checks ────────────────────────────────────────────────────────────

def check_function_has_returns(shapes: dict) -> list[dict]:
    issues: list[dict] = []
    for fn, shape in sorted(shapes.items()):
        if shape["has_returns"]:
            continue
        if fn in RESPONSE_OPAQUE_OK:
            continue
        issues.append({
            "check": "edge_response_has_returns", "skip": True,
            "fn":    fn,
            "reason": (
                f"Edge function '{fn}' has no detectable "
                f"`return new Response(JSON.stringify(...))` paths. Either it "
                f"throws unconditionally, returns plain text, or uses an "
                f"unusual response pattern. Static contract enforcement "
                f"can't gate callers on its return shape. If intentional "
                f"(binary / streaming / passthrough), add to RESPONSE_OPAQUE_OK."
            ),
        })
    return issues


def check_caller_field_validity(
    accesses: list[dict], shapes: dict
) -> list[dict]:
    issues: list[dict] = []
    for acc in accesses:
        shape = shapes.get(acc["fn"])
        if not shape:
            continue   # function doesn't exist; edge_caller_contract owns L1
        if acc["fn"] in RESPONSE_OPAQUE_OK:
            continue
        if shape["opaque"]:
            continue   # can't tell statically; skip
        if not shape["literal_keys"]:
            continue   # function returns nothing detectable; covered by L1
        for field in acc["fields"]:
            if field in NEUTRAL_CALLER_FIELDS:
                continue
            if field in shape["literal_keys"]:
                continue
            issues.append({
                "check":  "edge_response_phantom_field",
                "file":   acc["file"], "line": acc["line"],
                "fn":     acc["fn"], "field": field,
                "known_keys": sorted(shape["literal_keys"]),
                "reason": (
                    f"{acc['file']}:{acc['line']} reads `data.{field}` after "
                    f"invoke('{acc['fn']}'), but '{field}' is NOT in any of "
                    f"the function's object-literal returns ({sorted(shape['literal_keys'])}). "
                    f"Caller silently gets undefined; downstream logic / UI "
                    f"renders blank. Either rename to one of the actual return "
                    f"fields, or update the function to include the field, or "
                    f"(if this caller intentionally consumes a dynamically-shaped "
                    f"response) add the function to RESPONSE_OPAQUE_OK."
                ),
            })
    return issues


def check_error_only_functions(shapes: dict) -> list[dict]:
    issues: list[dict] = []
    for fn, shape in sorted(shapes.items()):
        if not shape["error_only"]:
            continue
        if fn in RESPONSE_OPAQUE_OK:
            continue
        # An "error only" function might be intentionally guard-only (always
        # 4xx/5xx) — but more often it indicates the success path was missed
        # by the regex (success path uses JSON.stringify(<var>) which is
        # opaque and not counted). If shape['opaque'] is true AND error_only
        # is also true, that's the explanation; skip.
        if shape["opaque"]:
            continue
        issues.append({
            "check": "edge_response_error_only", "skip": True,
            "fn":    fn,
            "reason": (
                f"Edge function '{fn}' has only object-literal returns that "
                f"include an 'error' field (no detectable success-shape "
                f"return). Callers consuming `data.X` for any field other "
                f"than 'error' will always get undefined. Either the success "
                f"path uses opaque JSON.stringify(<var>) (then add to "
                f"RESPONSE_OPAQUE_OK), or the function genuinely never "
                f"returns success — investigate."
            ),
        })
    return issues


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "edge_response_has_returns",
    "edge_response_phantom_field",
    "edge_response_error_only",
]
CHECK_LABELS = {
    "edge_response_has_returns":  "L1  Every edge function has at least one detectable JSON return  [WARN]",
    "edge_response_phantom_field":"L2  Every caller `data.X` references a field the function returns",
    "edge_response_error_only":   "L4  No function returns ONLY error envelopes (success path missing)  [WARN]",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nEdge Function Response Contract Validator (4-layer)"))
    print("=" * 65)

    fns = _list_edge_functions()
    shapes = {fn: _extract_function_return_shape(fn) for fn in fns}
    accesses = _collect_caller_field_accesses()

    analysable = sum(1 for s in shapes.values() if s["literal_paths"] > 0 and not s["opaque"])
    partial    = sum(1 for s in shapes.values() if s["literal_paths"] > 0 and s["opaque"])
    fully_opaque = sum(1 for s in shapes.values() if s["literal_paths"] == 0 and s["opaque"])
    no_returns = sum(1 for s in shapes.values() if not s["has_returns"])
    pct_analysable = round(100 * analysable / max(1, len(fns)))

    print(f"  {len(fns)} edge fns: {analysable} fully analysable ({pct_analysable}%), "
          f"{partial} partial-opaque, {fully_opaque} fully opaque, "
          f"{no_returns} no detectable returns.")
    print(f"  {len(accesses)} caller invoke→data destructure callsites, "
          f"{sum(len(a['fields']) for a in accesses)} field reads.\n")

    all_issues: list[dict] = []
    all_issues += check_function_has_returns(shapes)
    all_issues += check_caller_field_validity(accesses, shapes)
    all_issues += check_error_only_functions(shapes)

    by_check: dict = defaultdict(list)
    for i in all_issues:
        by_check[i["check"]].append(i)

    n_pass = n_warn = n_fail = 0
    for name in CHECK_NAMES:
        items = by_check.get(name, [])
        warns = [i for i in items if i.get("skip")]
        fails = [i for i in items if not i.get("skip")]
        label = CHECK_LABELS[name]
        if not items:
            print(f"  \033[92mPASS\033[0m  {label}")
            n_pass += 1
        elif not fails:
            print(f"  \033[93mSKIP\033[0m  {label}")
            n_warn += 1
        else:
            print(f"  \033[91mFAIL\033[0m  {label}")
            n_fail += 1

    # L3 is the coverage metric — informational, doesn't block
    print(f"  \033[96mINFO\033[0m  L3  Static introspection coverage: "
          f"{pct_analysable}% of functions fully analysable ({analysable}/{len(fns)})")

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")

    report = {
        "validator":      "edge_response_contract",
        "summary":        {"pass": n_pass, "warn": n_warn, "fail": n_fail,
                           "coverage_pct": pct_analysable},
        "function_shapes": {
            fn: {**s, "literal_keys": sorted(s["literal_keys"])}
            for fn, s in shapes.items()
        },
        "caller_accesses": [
            {**a, "fields": sorted(a["fields"])} for a in accesses
        ],
        "issues":   [i for i in all_issues if not i.get("skip")],
        "warnings": [i for i in all_issues if i.get("skip")],
    }
    out = os.path.join(ROOT, "edge_response_contract_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=lambda o: list(o) if isinstance(o, set) else o)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
