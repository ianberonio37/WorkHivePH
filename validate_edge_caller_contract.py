"""
Edge Function Caller Contract Validator — WorkHive Platform
============================================================
Every `db.functions.invoke('fn-name', { body: { ... } })` callsite from
HTML/JS forms an implicit contract with the edge function's `req.json()`
destructure. When that contract drifts (caller renames a field, function
adds a new required field, function gets renamed/deleted), the failure
is silent: the function 500s deep in logic, the caller surfaces a
generic "function returned an error", and nobody knows the contract
broke until a user reports a missing feature.

Static counterpart of the run-time contract. Catches the silent class
before it ships. Same shape as schema phantom + cron schedule integrity:
parse both sides of the boundary, cross-check, list mismatches.

  Layer 1 — Function existence
    1.  Every invoke('fn-name') targets a deployed function on disk
    [FAIL] Renamed/deleted function leaves caller calling into the void.

  Layer 2 — Required-field coverage
    2.  Every field destructured from req.json() is sent by every caller
        (fields with default values or marked-optional in OPTIONAL_FIELDS
        are exempt).
    [WARN] Function reads X but caller didn't send it — X is undefined,
    function may 500 / behave wrong.

  Layer 3 — Phantom body fields
    3.  Every key in the caller's body is read by the function.
    [WARN] Caller sends X but function never reads it — likely stale code
    after a field was removed from the function but not from callers.

  Layer 4 — Orphan functions
    4.  Every deployed edge function has at least one caller (page invoke,
        cron job, or other edge function).
    [WARN] Function has no caller — possibly dead code; ship costs apply
    nonetheless (deploy time, secret rotations).

Usage:  python validate_edge_caller_contract.py
Output: edge_caller_contract_report.json
"""
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT          = os.path.dirname(os.path.abspath(__file__))
FUNCTIONS_DIR = os.path.join(ROOT, "supabase", "functions")


# Functions intentionally callable only via cron / HTTP without a JS caller.
# Scheduled by pg_cron (validated by validate_cron_schedule_integrity) or
# webhook handlers (called by external systems).
ORPHAN_OK_FUNCTIONS = {
    "scheduled-agents":          "Cron-only fan-out via pg_cron (see validate_cron_schedule_integrity)",
    "batch-risk-scoring":        "Cron-only daily risk scoring",
    "trigger-ml-retrain":        "Cron-only weekly ML retrain",
    "marketplace-webhook":       "Stripe webhook receiver (called by Stripe, not by JS)",
    "cmms-webhook-receiver":     "External CMMS webhook receiver",
    "intelligence-api":          "Public REST API for third-party integrations (no JS caller)",
    "marketplace-checkout":      "Called via Stripe Checkout redirect (uses fetch directly, not invoke)",
    "marketplace-release":       "Called via marketplace-admin internals or scheduled-agents",
    "marketplace-connect-status":"Polled from marketplace-seller; uses fetch not invoke",
    "marketplace-connect-onboard":"Called from marketplace-seller.html via direct fetch (Stripe Connect onboarding redirect)",
    "send-report-email":         "Called from report-sender.html via direct fetch (matches FormData/streaming response pattern)",
    "semantic-search":           "Called by ai-orchestrator edge fn via direct fetch (server-to-server RAG path)",
    "voice-transcribe":          "Called by voice-action-router internally",
    "voice-action-router":       "Called by ai-gateway (server-to-server) via the 'voice-action' route since Companion Unification Step 4; voice-handler.js now invokes ai-gateway, not this fn directly",
    "voice-report-intent":       "Called by voice-handler.js via direct fetch",
    "failure-signature-scan":    "Cron-scheduled detection sweep",
    "parts-staging-recommender": "Cron-scheduled recommender",
    "embed-entry":               "Fire-and-forget background embedding",
    "shift-planner-orchestrator":"Called from shift-brain.html and cron",
}

# Fields that may be omitted by callers without raising L2 (function handles
# missing case gracefully via `??` / default param / explicit null check).
# Keyed by (function, field) — only exempt when documented case-by-case.
OPTIONAL_FIELDS: dict = {
    ("ai-orchestrator", "worker_name"):        "Optional context — function uses anon if absent",
    ("ai-orchestrator", "mode"):               "Defaults to 'chat' when omitted",
    ("analytics-orchestrator", "hive_id"):     "Optional — runs cross-hive when omitted",
    ("analytics-orchestrator", "worker_name"): "Optional context for personalization",
    ("analytics-orchestrator", "criticality"): "Filter — omitted = no filter",
    ("analytics-orchestrator", "discipline"):  "Filter — omitted = no filter",
    ("analytics-orchestrator", "period_days"): "Defaults to 90 in the function",
    ("scheduled-agents", "voice_context"):     "Optional voice transcript context",
    ("scheduled-agents", "hive_id"):           "Cron path omits; on-demand path supplies it",
    ("semantic-search", "sources"):            "Defaults to all sources when omitted",
    ("semantic-search", "match_count"):        "Defaults to 10 when omitted",
    ("voice-logbook-entry", "hive_id"):        "Optional — function falls back to worker_profile lookup",
    ("voice-logbook-entry", "worker_name"):    "Optional — function falls back to auth.uid lookup",
    ("send-report-email", "sent_at"):          "Defaults to now() when omitted",
}


# ─── File walking ────────────────────────────────────────────────────────────

def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _list_edge_functions() -> list[str]:
    """Returns list of function dir names under supabase/functions/ that have
    an index.ts. Skips _shared/ and dirs without index.ts."""
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
    """HTML + JS files that may call db.functions.invoke. Skip backup/test/
    _shared dirs."""
    out: list[str] = []
    for fname in os.listdir(ROOT):
        if not (fname.endswith(".html") or fname.endswith(".js")):
            continue
        if fname in {"engineering-design-test.html"}:
            continue  # test copy — known to drift; not a live page
        out.append(os.path.join(ROOT, fname))
    return out


# ─── Function side: parse req.json() destructure ─────────────────────────────

# Captures the destructure pattern. Matches both `await req.json()` and
# variants like `await req.json() as ...`. Captures the field list inside
# `{ ... }`. Stops at the first closing brace (no nested object literals
# expected in destructure).
DESTRUCT_RE = re.compile(
    r"const\s*\{\s*([^}]+?)\s*\}\s*(?::\s*[^=]+)?\s*=\s*await\s+req\.json\(\)",
    re.DOTALL,
)
# Matches a single field name in a destructure list, capturing the name and
# whether a default was provided. Default = optional.
FIELD_RE = re.compile(
    r"(\w+)\s*(?::\s*[^,=]+?)?\s*(?:=\s*[^,]+)?",
)


def _function_required_fields(func_name: str) -> dict:
    """Returns {field_name: has_default}. has_default=True means optional.
    Returns empty dict if function doesn't use req.json() destructure (might
    parse manually) — those skip L2 entirely."""
    src = _read(os.path.join(FUNCTIONS_DIR, func_name, "index.ts"))
    if not src:
        return {}
    m = DESTRUCT_RE.search(src)
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, bool] = {}
    # Manual split — FIELD_RE matches everything which is too greedy; safer
    # to split on commas at top level (no nested commas in destructure heads)
    for part in body.split(","):
        part = part.strip()
        if not part:
            continue
        # Default = optional
        has_default = "=" in part
        # Field name is the first identifier
        m2 = re.match(r"(\w+)", part)
        if not m2:
            continue
        out[m2.group(1)] = has_default
    return out


# ─── Caller side: parse db.functions.invoke('fn', { body: {...} }) ───────────

# First-stage: locate the function name + the START of the body literal.
# Then we walk character-by-character to find the matching `}` because
# non-greedy regex over-captures when a trailing comma or other options
# follow the body literal: `body: {...}, headers: {...}`.
INVOKE_HEAD_RE = re.compile(
    r"""\.functions\.invoke\(\s*['"`](?P<fn>[\w-]+)['"`]\s*
        ,\s*\{\s*body\s*:\s*\{""",
    re.DOTALL | re.VERBOSE,
)


def _find_matching_brace(src: str, open_brace_pos: int) -> int:
    """Given the index of an opening `{`, return the index of its matching
    `}`. Tracks brace depth, ignores braces inside strings/template literals
    and line comments. Returns -1 if no match found."""
    if open_brace_pos < 0 or open_brace_pos >= len(src) or src[open_brace_pos] != "{":
        return -1
    depth = 0
    i = open_brace_pos
    in_string: str = ""   # holds the active quote char if inside a string
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
        # Skip JS line comments
        if ch == "/" and i + 1 < len(src) and src[i + 1] == "/":
            nl = src.find("\n", i)
            i = nl + 1 if nl != -1 else len(src)
            continue
        # Skip JS block comments
        if ch == "/" and i + 1 < len(src) and src[i + 1] == "*":
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


def _extract_body_fields(body_text: str) -> set[str]:
    """Best-effort key extraction from a JS object literal text. Skips spread
    operators (`...x`) and computed keys (`[expr]`). Returns the set of
    top-level keys."""
    out: set[str] = set()
    # Strip nested objects/arrays so commas inside don't fool the splitter
    depth = 0
    flat = []
    for ch in body_text:
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
        if not part or part.startswith("..."):
            continue
        # Match `key:` or `key,` (shorthand)
        m = re.match(r"['\"]?(\w+)['\"]?\s*[:,]?", part)
        if m:
            out.add(m.group(1))
    return out


def _collect_invocations() -> list[dict]:
    """Returns list of {file, line, fn, body_fields}.

    Two-stage parser: regex finds `invoke('fn', { body: {` head, then
    brace-depth walker locates the matching `}` of the body literal. This
    handles the `body: {...}, headers: {...}` and trailing-comma cases
    that broke the single-regex approach."""
    out: list[dict] = []
    for path in _list_caller_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        for m in INVOKE_HEAD_RE.finditer(src):
            # The `{` we want is the LAST char of the head match (the body
            # literal's opening brace).
            body_open = m.end() - 1
            body_close = _find_matching_brace(src, body_open)
            if body_close == -1:
                continue
            body_text = src[body_open: body_close + 1]
            line = src[:m.start()].count("\n") + 1
            out.append({
                "file":        rel,
                "line":        line,
                "fn":          m.group("fn"),
                "body_fields": _extract_body_fields(body_text),
            })
    return out


# ─── Layer checks ────────────────────────────────────────────────────────────

def check_function_existence(invocations: list[dict], functions: set[str]) -> list[dict]:
    issues: list[dict] = []
    for inv in invocations:
        if inv["fn"] in functions:
            continue
        issues.append({
            "check":  "edge_caller_function_exists",
            "file":   inv["file"], "line": inv["line"], "fn": inv["fn"],
            "reason": (
                f"{inv['file']}:{inv['line']} invoke('{inv['fn']}') targets a "
                f"function that does NOT exist in supabase/functions/. The call "
                f"will surface as a generic 'function not found' error to the "
                f"user. Either deploy the function or rename the invoke."
            ),
        })
    return issues


def check_required_field_coverage(
    invocations: list[dict], fn_fields: dict[str, dict]
) -> list[dict]:
    issues: list[dict] = []
    for inv in invocations:
        fields = fn_fields.get(inv["fn"])
        if fields is None:
            continue  # function doesn't use destructure pattern — skip
        for field, has_default in fields.items():
            if has_default:
                continue
            if (inv["fn"], field) in OPTIONAL_FIELDS:
                continue
            if field in inv["body_fields"]:
                continue
            issues.append({
                "check": "edge_caller_required_field", "skip": True,
                "file":  inv["file"], "line": inv["line"], "fn": inv["fn"],
                "field": field,
                "reason": (
                    f"{inv['file']}:{inv['line']} invoke('{inv['fn']}') omits "
                    f"required field '{field}' that the function destructures "
                    f"from req.json() with no default. The function reads it "
                    f"as undefined and may 500 / produce wrong results. Either "
                    f"add the field to the body, give it a default in the "
                    f"function, or add (\"{inv['fn']}\", \"{field}\") to "
                    f"OPTIONAL_FIELDS with a justification."
                ),
            })
    return issues


_function_source_cache: dict[str, str] = {}


def _load_function_source(func_name: str) -> str:
    if func_name not in _function_source_cache:
        _function_source_cache[func_name] = _read(
            os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        )
    return _function_source_cache[func_name]


def _function_references_field(func_name: str, field: str) -> bool:
    """A field is considered 'known' to a function if it appears anywhere in
    the function source as either a destructured variable or a property
    access. Catches the patterns the L1 destructure regex misses:
      - `const body = await req.json(); const { x } = body;`
      - `const body = await req.json(); body.x`
      - `req.json().then(({ x }) => ...)`
      - destructures inside switch cases or after validation
    A bare keyword match (e.g. the field name appearing in a comment or
    string) is acceptable false-positive cost — better than flagging real
    valid fields."""
    src = _load_function_source(func_name)
    if not src:
        return False
    # Look for the field as a whole word — covers destructure, property
    # access, JSON keys in error messages. False-positive risk is comment
    # mentions, but those are rare for short identifiers.
    return bool(re.search(rf"\b{re.escape(field)}\b", src))


def check_phantom_body_fields(
    invocations: list[dict], fn_fields: dict[str, dict]
) -> list[dict]:
    issues: list[dict] = []
    for inv in invocations:
        for sent in inv["body_fields"]:
            # Skip if function source references the field anywhere — much
            # more accurate than relying on the destructure regex alone.
            if _function_references_field(inv["fn"], sent):
                continue
            issues.append({
                "check": "edge_caller_phantom_field", "skip": True,
                "file":  inv["file"], "line": inv["line"], "fn": inv["fn"],
                "field": sent,
                "reason": (
                    f"{inv['file']}:{inv['line']} invoke('{inv['fn']}') sends "
                    f"field '{sent}' that does NOT appear ANYWHERE in the "
                    f"function source (no destructure, no property access, "
                    f"no string mention). Likely stale caller code after the "
                    f"function dropped or renamed the field. Remove from the "
                    f"caller body or update the function to read it."
                ),
            })
    return issues


def check_orphan_functions(invocations: list[dict], functions: set[str]) -> list[dict]:
    issues: list[dict] = []
    invoked = {inv["fn"] for inv in invocations}
    for fn in sorted(functions):
        if fn in invoked:
            continue
        if fn in ORPHAN_OK_FUNCTIONS:
            continue
        issues.append({
            "check": "edge_caller_orphan_function", "skip": True,
            "fn":    fn,
            "reason": (
                f"Edge function '{fn}' has no db.functions.invoke('{fn}') "
                f"caller anywhere in the platform's HTML/JS. Either it's "
                f"called via cron / webhook / direct fetch (add to "
                f"ORPHAN_OK_FUNCTIONS with a justification), or it's dead "
                f"code costing deploy time + secret rotations for nothing."
            ),
        })
    return issues


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "edge_caller_function_exists",
    "edge_caller_required_field",
    "edge_caller_phantom_field",
    "edge_caller_orphan_function",
]
CHECK_LABELS = {
    "edge_caller_function_exists":  "L1  Every invoke('fn') targets a deployed function",
    "edge_caller_required_field":   "L2  Every required req.json() field is sent by callers  [WARN]",
    "edge_caller_phantom_field":    "L3  Every caller body field is read by the function  [WARN]",
    "edge_caller_orphan_function":  "L4  Every deployed function has at least one caller  [WARN]",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nEdge Function Caller Contract Validator (4-layer)"))
    print("=" * 60)

    functions = set(_list_edge_functions())
    fn_fields = {fn: _function_required_fields(fn) for fn in functions}
    invocations = _collect_invocations()
    print(f"  {len(functions)} edge functions, {len(invocations)} invoke callsites, "
          f"{sum(1 for f in fn_fields.values() if f)} fns parse req.json() with destructure.\n")

    all_issues: list[dict] = []
    all_issues += check_function_existence(invocations, functions)
    all_issues += check_required_field_coverage(invocations, fn_fields)
    all_issues += check_phantom_body_fields(invocations, fn_fields)
    all_issues += check_orphan_functions(invocations, functions)

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

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")

    report = {
        "validator":      "edge_caller_contract",
        "functions":      sorted(functions),
        "invocations":    invocations,
        "summary":        {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    out = os.path.join(ROOT, "edge_caller_contract_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=lambda o: list(o) if isinstance(o, set) else o)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
