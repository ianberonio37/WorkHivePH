"""
Edge Function API Contract Validator — WorkHive Platform
=========================================================
WorkHive's AI features are powered by 6 Supabase Edge Functions. Each
function is a mini-API with an implicit contract: the caller (browser
or cron job) sends a specific JSON body and expects a specific JSON
response. A broken contract produces a silent failure or a cryptic error.

The AI Engineer skill and the Multi-Agent Supervisor agentic pattern
require that every agent interface is stable and self-describing.

Four things checked:

  1. All edge functions handle CORS OPTIONS preflight
     — Every function must respond to OPTIONS requests with the CORS
       headers. Without it, the browser blocks ALL requests from the
       frontend before they even reach the function logic. This is the
       #1 cause of "the AI feature just stopped working" incidents.

  2. All edge functions return { error: string } JSON on failure
     — The error contract: every failure path must return a JSON object
       with an "error" key. Callers (browser, cron, orchestrator) check
       for response.error. If a function returns plain text or a
       differently-shaped object, the caller silently fails to detect
       the error and treats the result as success.

  3. Required input fields validated at function entry
     — Every function that expects required fields (calc_type, question,
       report_type, etc.) must validate them upfront and return a 400
       with a clear error message. Missing input validation means the
       function crashes deep in its logic with a cryptic 500 error
       instead of a meaningful "Missing required field: X" message.

  4. BOM/SOW sections use content:string format (not items:array)
     — The SOW schema MUST be:
         { section_no: string, title: string, content: string }
       NOT:
         { title: string, items: string[] }
       The AI Engineer skill explicitly calls out this format as the
       correct one. The renderer in engineering-design.html reads
       section.content — if the LLM returns items[], the SOW renders
       blank. This is the most common silent format regression.

Usage:  python validate_edge_contracts.py
Output: edge_contracts_report.json
"""
import re, json, sys, os

FUNCTIONS_DIR = os.path.join("supabase", "functions")

# All 6 edge functions that serve HTTP requests
ALL_FUNCTIONS = [
    "ai-orchestrator",
    "engineering-calc-agent",
    "engineering-bom-sow",
    "scheduled-agents",
    "semantic-search",
    "embed-entry",
]

# Functions that must validate specific required fields (function → field list)
REQUIRED_FIELDS = {
    "ai-orchestrator":        ["question"],
    "engineering-calc-agent": ["calc_type", "inputs"],
    "engineering-bom-sow":    ["discipline", "calc_type"],
    "scheduled-agents":       ["report_type"],
    "semantic-search":        ["query"],
}


def read_function(name):
    path = os.path.join(FUNCTIONS_DIR, name, "index.ts")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), path
    except FileNotFoundError:
        return None, path


# ── Check 1: All edge functions handle CORS OPTIONS preflight ─────────────────

def check_cors_options(func_names):
    """
    Every edge function must handle OPTIONS requests and return CORS headers.
    Without this, the browser's preflight check fails BEFORE any request
    body is sent — the AI feature appears completely broken with no
    specific error in the browser console.

    Required pattern:
      if (req.method === "OPTIONS") { return new Response("ok", { headers: corsHeaders }); }
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            issues.append({
                "func":   name,
                "reason": f"{path} not found — cannot verify CORS OPTIONS handling",
            })
            continue
        if not re.search(r'req\.method\s*===\s*["\']OPTIONS["\']', content):
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts does not handle OPTIONS preflight — "
                    f"browser CORS check will block all frontend requests to this function"
                ),
            })
    return issues


# ── Check 2: All functions return { error: string } JSON on failure ───────────

def check_error_contract(func_names):
    """
    Every error response must be a JSON object with an 'error' key.
    The frontend and orchestrator both check result.error — if the shape
    differs, the caller silently misses the error condition.

    Required patterns:
      JSON.stringify({ error: "..." })
      JSON.stringify({ error: err.message })
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        # Every function should have at least one { error: ... } JSON response
        has_error_contract = bool(re.search(
            r'JSON\.stringify\s*\(\s*\{\s*error\s*:',
            content
        ))
        if not has_error_contract:
            issues.append({
                "func":   name,
                "reason": (
                    f"{name}/index.ts has no JSON.stringify({{ error: ... }}) "
                    f"error response — callers cannot detect failures because "
                    f"the error shape doesn't match the expected contract"
                ),
            })
    return issues


# ── Check 3: Required input fields validated at function entry ────────────────

def check_input_validation(required_fields):
    """
    Functions that expect required fields must validate them at the top of
    the request handler and return a 400 with a clear message.

    Without this check:
    - A caller that sends an empty body gets a cryptic 500 error deep
      in the function logic instead of "Missing required field: X"
    - Debugging takes minutes instead of seconds
    - The cron scheduler or orchestrator can't distinguish missing fields
      from server errors
    """
    issues = []
    for name, fields in required_fields.items():
        content, path = read_function(name)
        if content is None:
            continue

        for field in fields:
            # Check for !field_name or Missing required field: field
            has_validation = bool(re.search(
                rf"!{re.escape(field)}\b|Missing.*{re.escape(field)}",
                content
            ))
            if not has_validation:
                issues.append({
                    "func":  name,
                    "field": field,
                    "reason": (
                        f"{name}/index.ts does not validate required field "
                        f"'{field}' at entry — a missing field produces a "
                        f"cryptic 500 instead of a clear 400 'Missing required field'"
                    ),
                })
    return issues


# ── Check 4: BOM/SOW sections use content:string not items:array ──────────────

def check_sow_content_format():
    """
    The SOW schema in engineering-bom-sow must instruct the LLM to return
    sections as { section_no, title, content: string } — NOT { title, items[] }.

    The engineering-design.html renderer reads section.content.
    If the LLM returns items[], the SOW silently renders blank.

    This is the format bug the AI Engineer skill explicitly documents:
    'SOW agent schema (content: string, not items: array)'
    """
    issues = []
    content, path = read_function("engineering-bom-sow")
    if content is None:
        return [{"func": "engineering-bom-sow", "reason": f"{path} not found"}]

    # Look for the SOW section schema definition
    # The correct pattern includes "content": string in the schema instruction
    has_content_field = bool(re.search(
        r'"content"\s*:\s*(?:string|"[^"]*")',
        content
    ))
    if not has_content_field:
        issues.append({
            "func":   "engineering-bom-sow",
            "reason": (
                "engineering-bom-sow/index.ts SOW schema does not declare "
                "'content': string for section objects — the renderer reads "
                "section.content; if the LLM returns items[] instead, "
                "the entire SOW renders blank silently"
            ),
        })
        return issues

    # Also check that 'items' is not used as the section content field
    # (The wrong pattern: { "title": ..., "items": [...] })
    # Find SOW section schema blocks and check for items:array instruction
    sow_schema_blocks = re.findall(
        r"sow_sections.*?(?=bom_items|\Z)",
        content[:5000], re.DOTALL | re.IGNORECASE
    )
    for block in sow_schema_blocks[:3]:
        if re.search(r'"items"\s*:\s*(?:array|Array|\[)', block, re.IGNORECASE):
            issues.append({
                "func":   "engineering-bom-sow",
                "reason": (
                    "engineering-bom-sow/index.ts SOW schema uses 'items: array' "
                    "format — must use 'content: string' per AI Engineer skill. "
                    "The renderer reads section.content, not section.items"
                ),
            })
            break
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Edge Function API Contract Validator")
print("=" * 70)
print(f"\n  Checking {len(ALL_FUNCTIONS)} edge functions: "
      f"{', '.join(ALL_FUNCTIONS)}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] All edge functions handle CORS OPTIONS preflight",
        check_cors_options(ALL_FUNCTIONS),
        "FAIL",
    ),
    (
        "[2] All edge functions return { error: string } JSON on failure",
        check_error_contract(ALL_FUNCTIONS),
        "FAIL",
    ),
    (
        "[3] Required input fields validated at function entry",
        check_input_validation(REQUIRED_FIELDS),
        "FAIL",
    ),
    (
        "[4] BOM/SOW sections use content:string format (not items:array)",
        check_sow_content_format(),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('func', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("edge_contracts_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved edge_contracts_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll edge contract checks PASS.")
