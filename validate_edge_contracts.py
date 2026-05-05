"""
Edge Function API Contract Validator — WorkHive Platform
=========================================================
WorkHive's AI features are powered by Supabase Edge Functions. Each
function is a mini-API with an implicit contract: the caller sends a
specific JSON body and expects a specific JSON response. A broken
contract produces a silent failure or a cryptic error.

  Layer 1 — Request handling
    1.  CORS OPTIONS preflight         — every function must handle OPTIONS or browser blocks all calls

  Layer 2 — Response contract
    2.  { error: string } on failure   — callers check result.error; wrong shape = silent failure

  Layer 3 — Input safety
    3.  Required fields validated      — missing field should 400, not 500 deep in logic
    4.  BOM/SOW sections: content:string — renderer reads section.content; items[] renders blank

  Layer 4 — Operational hygiene
    5.  All function dirs registered   — new functions escape all checks if not in ALL_FUNCTIONS
    6.  SUPABASE env vars guarded      — createClient() should not use bare Deno.env.get()! [WARN]

Usage:  python validate_edge_contracts.py
Output: edge_contracts_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FUNCTIONS_DIR = os.path.join("supabase", "functions")

ALL_FUNCTIONS = [
    "ai-orchestrator",
    "analytics-orchestrator",
    "engineering-calc-agent",
    "engineering-bom-sow",
    "scheduled-agents",
    "semantic-search",
    "embed-entry",
    "send-report-email",
    "voice-report-intent",
    "voice-transcribe",
    "marketplace-checkout",
    "marketplace-webhook",
    "marketplace-connect-onboard",
    "marketplace-release",
    "marketplace-connect-status",
    "project-progress",
    "project-orchestrator",
]

REQUIRED_FIELDS = {
    "ai-orchestrator":          ["question"],
    "analytics-orchestrator":   ["phase"],
    "engineering-calc-agent":   ["calc_type", "inputs"],
    "engineering-bom-sow":      ["discipline", "calc_type"],
    "scheduled-agents":         ["report_type"],
    "semantic-search":          ["query"],
    "send-report-email":        ["recipient_email", "reports"],  # hive_id optional — workers without hive context can still send
    "voice-report-intent":      ["transcript"],
    "voice-transcribe":         ["audio"],
    "marketplace-checkout":        ["listing_id", "buyer_name"],
    "marketplace-release":         ["order_id", "buyer_name"],
    "marketplace-connect-onboard":  ["worker_name", "return_url", "refresh_url"],
    "marketplace-connect-status":   ["worker_name"],
    "project-progress":             ["project_id", "hive_id"],
    "project-orchestrator":         ["phase"],
}


def read_function(name):
    path = os.path.join(FUNCTIONS_DIR, name, "index.ts")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), path
    except FileNotFoundError:
        return None, path


# ── Layer 1: Request handling ─────────────────────────────────────────────────

def check_cors_options(func_names):
    """Every edge function must handle OPTIONS requests — without it, the browser
    preflight check blocks all calls before any request body is even sent."""
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            issues.append({"check": "cors_options", "func": name,
                           "reason": f"{path} not found — cannot verify CORS OPTIONS handling"})
            continue
        if not re.search(r'req\.method\s*===\s*["\']OPTIONS["\']', content):
            issues.append({"check": "cors_options", "func": name,
                           "reason": (f"{name}/index.ts does not handle OPTIONS preflight — "
                                      f"browser CORS check blocks all frontend requests")})
    return issues


# ── Layer 2: Response contract ────────────────────────────────────────────────

def check_error_contract(func_names):
    """Every failure path must return JSON.stringify({ error: ... }) — the frontend
    and orchestrator both check result.error; wrong shape = silent failure."""
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        if not re.search(r'JSON\.stringify\s*\(\s*\{\s*error\s*:', content):
            issues.append({"check": "error_contract", "func": name,
                           "reason": (f"{name}/index.ts has no JSON.stringify({{ error: ... }}) "
                                      f"error response — callers cannot detect failures")})
    return issues


# ── Layer 3: Input safety ─────────────────────────────────────────────────────

def check_input_validation(required_fields):
    """Required fields must be validated at entry with a 400 — a missing field
    should produce 'Missing required field: X', not a cryptic 500."""
    issues = []
    for name, fields in required_fields.items():
        content, path = read_function(name)
        if content is None:
            continue
        for field in fields:
            if not re.search(rf"!{re.escape(field)}\b|Missing.*{re.escape(field)}", content):
                issues.append({"check": "input_validation", "func": name,
                               "reason": (f"{name}/index.ts does not validate required field "
                                          f"'{field}' at entry — missing field produces cryptic 500")})
    return issues


def check_sow_content_format():
    """The SOW schema must instruct the LLM to return sections as
    { section_no, title, content:string } — NOT { title, items[] }.
    The renderer reads section.content; items[] renders blank silently."""
    content, path = read_function("engineering-bom-sow")
    if content is None:
        return [{"check": "sow_content_format", "func": "engineering-bom-sow",
                 "reason": f"{path} not found"}]
    if not re.search(r'"content"\s*:\s*(?:string|"[^"]*")', content):
        return [{"check": "sow_content_format", "func": "engineering-bom-sow",
                 "reason": ("engineering-bom-sow SOW schema has no 'content': string field — "
                            "renderer reads section.content; LLM returning items[] renders blank")}]
    sow_blocks = re.findall(r"sow_sections.*?(?=bom_items|\Z)", content[:5000], re.DOTALL | re.IGNORECASE)
    for block in sow_blocks[:3]:
        if re.search(r'"items"\s*:\s*(?:array|Array|\[)', block, re.IGNORECASE):
            return [{"check": "sow_content_format", "func": "engineering-bom-sow",
                     "reason": ("engineering-bom-sow SOW schema uses 'items: array' — "
                                "must use 'content: string' per AI Engineer skill")}]
    return []


# ── Layer 4: Operational hygiene ──────────────────────────────────────────────

def check_all_functions_covered(registered):
    """
    Every directory under supabase/functions/ that contains an index.ts must
    be in ALL_FUNCTIONS. analytics-orchestrator was previously not registered —
    its CORS handling, error contract, and input validation were never checked.
    A new function deployed without being added here escapes all contract checks.
    """
    issues = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    registered_set = set(registered)
    for dirname in sorted(os.listdir(FUNCTIONS_DIR)):
        func_path = os.path.join(FUNCTIONS_DIR, dirname, "index.ts")
        if not os.path.isfile(func_path):
            continue
        if dirname not in registered_set:
            issues.append({"check": "all_functions_covered", "func": dirname,
                           "reason": (f"supabase/functions/{dirname}/ exists but is not in "
                                      f"ALL_FUNCTIONS — its CORS, error contract, and input "
                                      f"validation are never checked; add it to validate_edge_contracts.py")})
    return issues


def check_env_var_validation(func_names):
    """
    Functions that call createClient() must not use bare Deno.env.get("SUPABASE_URL")!
    with the TypeScript non-null assertion operator as the only guard. The ! is
    compile-time only — at runtime, if the env var is missing, createClient() receives
    undefined and fails with a cryptic 'Invalid URL' error instead of a clear message.
    The GROQ_API_KEY already uses an explicit if (!GROQ_KEY) throw guard; SUPABASE_URL
    and SUPABASE_SERVICE_ROLE_KEY should follow the same pattern.
    Reported as WARN — functions work correctly when properly deployed.
    """
    issues = []
    for name in func_names:
        content, path = read_function(name)
        if content is None:
            continue
        # Find createClient calls that use Deno.env.get() inline without prior assignment
        inline_pattern = re.search(
            r"createClient\s*\(\s*Deno\.env\.get\s*\(",
            content
        )
        if not inline_pattern:
            continue
        # Check if SUPABASE_URL is explicitly validated somewhere
        has_guard = bool(re.search(
            r"if\s*\(\s*!.*SUPABASE_URL|const\s+\w+\s*=\s*Deno\.env\.get.*SUPABASE_URL.*\n.*if\s*\(!",
            content
        ))
        if not has_guard:
            issues.append({"check": "env_var_validation", "func": name, "skip": True,
                           "reason": (f"{name}/index.ts passes Deno.env.get('SUPABASE_URL')! "
                                      f"directly to createClient() without an explicit guard — "
                                      f"a missing env var produces cryptic 'Invalid URL' error; "
                                      f"assign to a const and add if (!SUPABASE_URL) throw first")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "cors_options",
    "error_contract",
    "input_validation",
    "sow_content_format",
    "all_functions_covered",
    "env_var_validation",
]

CHECK_LABELS = {
    "cors_options":          "L1  All edge functions handle CORS OPTIONS preflight",
    "error_contract":        "L2  All functions return { error: string } JSON on failure",
    "input_validation":      "L3  Required input fields validated at function entry",
    "sow_content_format":    "L3  BOM/SOW sections use content:string (not items:array)",
    "all_functions_covered": "L4  All supabase/functions/ dirs registered in validator scope",
    "env_var_validation":    "L4  SUPABASE env vars guarded before createClient()  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEdge Function API Contract Validator (4-layer)"))
    print("=" * 55)
    print(f"  {len(ALL_FUNCTIONS)} edge functions: {', '.join(ALL_FUNCTIONS)}\n")

    all_issues = []
    all_issues += check_cors_options(ALL_FUNCTIONS)
    all_issues += check_error_contract(ALL_FUNCTIONS)
    all_issues += check_input_validation(REQUIRED_FIELDS)
    all_issues += check_sow_content_format()
    all_issues += check_all_functions_covered(ALL_FUNCTIONS)
    all_issues += check_env_var_validation(ALL_FUNCTIONS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "edge_contracts",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("edge_contracts_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
