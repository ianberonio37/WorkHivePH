"""
Integration Security Baseline Validator — WorkHive Platform
============================================================
Enterprise integrations introduce new attack surfaces: external API calls,
webhook endpoints, OAuth tokens, and third-party service credentials.

  Layer 1 — Credential exposure
    1.  No webhook tokens in client code     — embedded tokens expose API access to anyone
    2.  No credentials logged to console     — tokens logged are captured by extensions/tools
    3.  Supabase key uses sb_publishable_ format — old JWT key causes 401 on all queries

  Layer 2 — Transport security
    4.  External fetch calls have timeout    — no timeout = hanging UI on slow external service
    5.  All external fetches use HTTPS       — HTTP sends auth headers unencrypted

  Layer 3 — Edge function hardening
    6.  CORS not wildcard on edge functions  — * allows any origin to call the API  [WARN]
    7.  getCorsHeaders(req) used (not static) — static origin breaks file:// local testing  [FAIL]
    8.  deploy-functions.ps1 covers all fns  — missing entry = edge fn stays on old code  [WARN]
    9.  No raw String(err) in responses      — stack traces must not reach the browser  [WARN]

Usage:  python validate_integration_security.py
Output: integration_security_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FUNCTIONS_DIR = os.path.join("supabase", "functions")

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html",
    "hive.html", "assistant.html", "skillmatrix.html",
    "dayplanner.html", "engineering-design.html", "index.html",
    "platform-health.html", "floating-ai.js", "nav-hub.js",
    "community.html",
    "marketplace.html",
    "public-feed.html",
]

ALLOWED_DOMAINS = {
    "supabase.co", "supabase.io",
    "workers.dev",
    "onrender.com",
    "googleapis.com",
    "groq.com",
    "localhost", "127.0.0.1", "0.0.0.0",
}

TOKEN_MIN_LENGTH = 20


def is_allowed_domain(url):
    return any(domain in url for domain in ALLOWED_DOMAINS)


# ── Layer 1: Credential exposure ──────────────────────────────────────────────

def check_webhook_tokens(pages):
    """External webhook URLs with embedded tokens in client code — anyone reading
    page source can call the webhook with arbitrary data."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "fetch(" not in line:
                continue
            url_m = re.search(r"""fetch\s*\(\s*['"]([^'"]+)['"]""", line)
            if not url_m:
                continue
            url = url_m.group(1)
            if is_allowed_domain(url) or not url.startswith("http"):
                continue
            path_parts = re.sub(r"https?://[^/]+", "", url).split("/")
            for part in path_parts:
                if len(part) >= TOKEN_MIN_LENGTH and re.match(r"^[a-zA-Z0-9_-]+$", part):
                    issues.append({"check": "webhook_tokens", "page": page,
                                   "skip": True,
                                   "reason": (f"{page}:{i + 1} external webhook URL with embedded "
                                              f"token in client code: '{url[:60]}' — move to a "
                                              f"Supabase Edge Function so the URL stays server-side")})
                    break
    return issues


def check_supabase_key_format(pages):
    """
    New Supabase projects (2024+) use the 'sb_publishable_...' key format.
    Old JWT anon keys start with 'eyJ'. Using an old-format key on a project
    that expects the publishable format causes 401 on every database query —
    all page data goes blank with no clear error in the UI. Both key types are
    safe to embed in frontend code (both are anon keys), but only the matching
    format for the project actually works.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        m = re.search(
            r'(?:SUPABASE_KEY|supabaseKey|ANON_KEY)\s*=\s*[\'"]([^\'"]{20,})[\'"]',
            content
        )
        if not m:
            continue
        key_val = m.group(1)
        if key_val.startswith("eyJ") and not key_val.startswith("sb_publishable_"):
            issues.append({
                "check": "supabase_key_format",
                "page": page,
                "reason": (f"{page} uses old JWT anon key (starts with 'eyJ') — "
                           f"new Supabase projects require 'sb_publishable_...' format; "
                           f"wrong key causes 401 on all queries silently")
            })
    return issues


def check_no_credential_logging(pages):
    """console.log() must never output token values, Bearer strings, or API keys —
    log output is captured by browser extensions and error monitoring services."""
    issues = []
    patterns = [
        r"console\.log\s*\([^)]*\btoken\b",
        r"console\.log\s*\([^)]*\bBearer\b",
        r"console\.log\s*\([^)]*\bapiKey\b",
        r"console\.log\s*\([^)]*\bapi_key\b",
        r"console\.log\s*\([^)]*\bpassword\b",
        r"console\.log\s*\([^)]*\bsecret\b",
    ]
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({"check": "no_credential_logging", "page": page,
                                   "line": i + 1,
                                   "reason": (f"{page}:{i + 1} console.log outputs a credential "
                                              f"value — tokens in console can be captured by "
                                              f"browser extensions: `{stripped[:60]}`")})
                    break
    return issues


# ── Layer 2: Transport security ───────────────────────────────────────────────

def check_fetch_timeout(pages):
    """Every external fetch() must have an AbortSignal timeout — no timeout means
    the browser hangs indefinitely when an external service is unresponsive."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "fetch(" not in line:
                continue
            url_m = re.search(r"""fetch\s*\(\s*[`'"]([^`'"]+)[`'"]""", line)
            if not url_m:
                if not re.search(r"WORKER_URL|workerUrl|PYTHON_DIAGRAM_API|onrender\.|workers\.dev", line):
                    continue
                url = "[external variable]"
            else:
                url = url_m.group(1)
                if is_allowed_domain(url):
                    continue
                if not url.startswith("http") and not url.startswith("${"):
                    continue
            window = "\n".join(lines[i:min(len(lines), i + 8)])
            if not re.search(r"AbortSignal|AbortController|signal\s*:|timeout\s*:", window):
                issues.append({"check": "fetch_timeout", "page": page, "skip": True,
                               "reason": (f"{page}:{i + 1} external fetch() has no timeout — "
                                          f"unresponsive external service hangs the browser indefinitely")})
    return issues


def check_https_only(pages):
    """External production fetch calls must use HTTPS — HTTP sends auth headers
    and user data unencrypted across the network."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            m = re.search(r"""fetch\s*\(\s*['"]http://([^'"]+)['"]""", line)
            if not m:
                continue
            domain = m.group(1).split("/")[0]
            if "localhost" in domain or "127.0.0.1" in domain:
                continue
            issues.append({"check": "https_only", "page": page, "line": i + 1,
                           "reason": (f"{page}:{i + 1} external fetch() uses HTTP: "
                                      f"'http://{m.group(1)[:50]}' — sends auth headers and "
                                      f"data unencrypted")})
    return issues


# ── Layer 3: Edge function hardening ─────────────────────────────────────────

def check_cors_not_wildcard():
    """
    All 7 edge functions use "Access-Control-Allow-Origin": "*" — any origin can
    make CORS requests to the API. For enterprise deployment where WorkHive is
    served from a single domain (workhiveph.com), restricting to that origin
    prevents malicious third-party websites from making authenticated cross-origin
    requests on behalf of logged-in workers.

    While JWT auth provides the primary protection, CORS restriction adds a second
    layer — a CSRF-like attack requires both a valid JWT AND matching origin. The
    wildcard removes the second layer entirely.

    Fix for production: replace "*" with "https://workhiveph.com" and add
    development override via an ALLOWED_ORIGIN env var.
    Reported as WARN — functions work correctly with wildcard during development.
    """
    issues = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    for func_name in sorted(os.listdir(FUNCTIONS_DIR)):
        func_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        content = read_file(func_path)
        if content is None:
            continue
        if not re.search(r"Access-Control-Allow-Origin", content):
            continue
        if re.search(r'Access-Control-Allow-Origin["\s:]+["\']\*["\']', content):
            issues.append({"check": "cors_not_wildcard", "func": func_name,
                           "skip": True,
                           "reason": (f"supabase/functions/{func_name}/index.ts uses "
                                      f"Access-Control-Allow-Origin: * — any origin can call "
                                      f"this API; restrict to 'https://workhiveph.com' for "
                                      f"enterprise deployment (add ALLOWED_ORIGIN env var "
                                      f"for local development override)")})
    return issues


def check_cors_dynamic_pattern():
    """
    Every edge function that sets Access-Control-Allow-Origin must use getCorsHeaders(req)
    from _shared/cors.ts. A static constant (const corsHeaders = { "Access-Control-Allow-Origin": ORIGIN })
    locks the origin to the production domain, breaking local file:// testing (Chrome sends
    Origin: null which never matches) and any dev environment without the ALLOWED_ORIGIN env var.

    The shared getCorsHeaders(req) echoes the request origin back when it is in the allow-list
    (production domain, env-var override, or "null" for file://), so local and production both work.
    """
    issues = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    for func_name in sorted(os.listdir(FUNCTIONS_DIR)):
        if func_name.startswith("_"):
            continue
        func_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        content = read_file(func_path)
        if content is None:
            continue
        if not re.search(r"Access-Control-Allow-Origin", content):
            continue
        if not re.search(r"getCorsHeaders\s*\(", content):
            issues.append({
                "check": "cors_dynamic_pattern",
                "func": func_name,
                "reason": (
                    f"supabase/functions/{func_name}/index.ts uses a static CORS origin instead of "
                    f"getCorsHeaders(req) from _shared/cors.ts — static origin breaks file:// local "
                    f"testing (Chrome sends Origin: null) and any non-production client; "
                    f"import getCorsHeaders and call it at the top of serve(async (req) => {{)"
                )
            })
    return issues


def check_deploy_script_coverage():
    """
    deploy-functions.ps1 must list every Supabase edge function directory.
    Any function missing from the script stays on old code after a git push — the
    frontend HTML gets Netlify auto-deploy but the edge function never gets updated.
    This is a silent mismatch: no error is shown, old behaviour persists.
    """
    issues = []
    deploy_script = read_file("deploy-functions.ps1")
    if deploy_script is None:
        return []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    deployed = set(re.findall(r"functions deploy\s+(\S+)\s+", deploy_script))
    for func_name in sorted(os.listdir(FUNCTIONS_DIR)):
        if func_name.startswith("_"):
            continue
        func_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        if not os.path.isfile(func_path):
            continue
        if func_name not in deployed:
            issues.append({
                "check": "deploy_script_coverage",
                "func": func_name,
                "skip": True,
                "reason": (
                    f"supabase/functions/{func_name}/ exists but is NOT in deploy-functions.ps1 — "
                    f"git push will update the frontend but this edge function stays at old code; "
                    f"add: npx supabase functions deploy {func_name} --no-verify-jwt"
                )
            })
    return issues


def check_raw_error_in_response():
    """
    Edge function catch blocks must not return String(err) or raw error.message
    in HTTP responses. These can leak internal implementation details:
    - Deno file paths from the call stack
    - Database column names from Postgres error messages
    - Internal variable names and state

    The secure pattern is: { error: "Internal server error" }
    or at most: { error: err instanceof Error ? err.message : "Internal error" }

    Dangerous pattern: { error: String(err) } — includes the full Error object
    stringification which may contain stack trace fragments in some Deno versions.
    """
    issues = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []
    for func_name in sorted(os.listdir(FUNCTIONS_DIR)):
        func_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        content = read_file(func_path)
        if content is None:
            continue
        # Find catch blocks that return String(err) in a Response
        for m in re.finditer(
            r"JSON\.stringify\s*\(\s*\{\s*error\s*:\s*String\s*\(err\b",
            content
        ):
            line_no = content[:m.start()].count("\n") + 1
            issues.append({"check": "raw_error_in_response", "func": func_name,
                           "skip": True,
                           "line": line_no,
                           "reason": (f"supabase/functions/{func_name}/index.ts:{line_no} "
                                      f"returns String(err) in HTTP response — can expose "
                                      f"stack traces or internal paths; use "
                                      f"{{ error: err instanceof Error ? err.message : 'Internal error' }}")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "webhook_tokens",
    "no_credential_logging",
    "supabase_key_format",
    "fetch_timeout",
    "https_only",
    "cors_not_wildcard",
    "cors_dynamic_pattern",
    "deploy_script_coverage",
    "raw_error_in_response",
]

CHECK_LABELS = {
    "webhook_tokens":         "L1  No webhook tokens hardcoded in client-side code  [WARN]",
    "no_credential_logging":  "L1  No API credentials or tokens logged to console",
    "supabase_key_format":    "L1  Supabase key uses sb_publishable_ format (not old JWT)",
    "fetch_timeout":          "L2  External fetch calls have AbortSignal timeout  [WARN]",
    "https_only":             "L2  All external fetch calls use HTTPS not HTTP",
    "cors_not_wildcard":      "L3  Edge function CORS not wildcard (enterprise hardening)  [WARN]",
    "cors_dynamic_pattern":   "L3  Edge functions use getCorsHeaders(req) not static origin  [FAIL]",
    "deploy_script_coverage": "L3  All edge functions listed in deploy-functions.ps1  [WARN]",
    "raw_error_in_response":  "L3  No String(err) in edge function HTTP responses  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nIntegration Security Baseline Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_webhook_tokens(LIVE_PAGES)
    all_issues += check_no_credential_logging(LIVE_PAGES)
    all_issues += check_supabase_key_format(LIVE_PAGES)
    all_issues += check_fetch_timeout(LIVE_PAGES)
    all_issues += check_https_only(LIVE_PAGES)
    all_issues += check_cors_not_wildcard()
    all_issues += check_cors_dynamic_pattern()
    all_issues += check_deploy_script_coverage()
    all_issues += check_raw_error_in_response()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "integration_security",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("integration_security_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
