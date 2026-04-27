"""
Integration Security Baseline Validator — WorkHive Platform
============================================================
Enterprise integrations introduce new attack surfaces: external API calls,
webhook endpoints, OAuth tokens, and third-party service credentials.
The #1 cause of integration security incidents is credential exposure
in client-side code during development. The #2 is unbounded fetch calls
that hang the UI when external services are slow or unavailable.

From the Integration Engineer skill (authentication method, error handling),
Research Topic 3 (SSO/SAML security checklist), OWASP integration patterns.

Four things checked:

  1. No third-party webhook tokens in client-side HTML/JS
     — External webhook URLs that embed authentication tokens (32+ char
       random strings as URL path components) should not be hardcoded in
       HTML/JS files served to browsers. Anyone who reads the page source
       can call that webhook with arbitrary data — spamming early access
       forms, triggering automations, or flooding the webhook queue.
       The Make.com webhook should be proxied through a Supabase Edge
       Function so the URL is server-side only.

  2. External fetch calls have timeout (AbortSignal or AbortController)
     — Every fetch() to an external URL (AI worker, diagram API, third-party
       webhook) must have a timeout. Without it, a slow or unresponsive
       external service hangs the worker's browser indefinitely — they
       can't close the loading state, can't navigate away cleanly, and
       the call never resolves. AbortSignal.timeout(N) is the modern pattern.

  3. No API credentials or tokens logged to console
     — console.log() must never output token values, Bearer strings,
       API keys, or passwords. Log output is captured by browser extensions,
       developer tools recordings, and error monitoring services. This is
       the forward guard: currently clean, regression check as integrations
       are added.

  4. All external fetch calls use HTTPS, not HTTP
     — Any fetch() to a production external service must use https://.
       HTTP sends all data (including auth headers, user emails, sensor
       readings) unencrypted across the network. This is a FAIL for any
       non-localhost external URL using http://.

Usage:  python validate_integration_security.py
Output: integration_security_report.json
"""
import re, json, sys

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html",
    "hive.html", "assistant.html", "skillmatrix.html",
    "dayplanner.html", "engineering-design.html", "index.html",
    "platform-health.html", "floating-ai.js", "nav-hub.js",
]

# Known legitimate internal/partner domains — not flagged for token check
ALLOWED_DOMAINS = {
    "supabase.co",
    "supabase.io",
    "workers.dev",    # Cloudflare Workers
    "onrender.com",   # Render.com Python API
    "googleapis.com",
    "groq.com",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}

# Minimum token length that looks like an authentication credential
TOKEN_MIN_LENGTH = 20


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def is_allowed_domain(url):
    """Returns True if the URL is to a known safe/internal domain."""
    return any(domain in url for domain in ALLOWED_DOMAINS)


# ── Check 1: No third-party webhook tokens in client-side code ────────────────

def check_webhook_tokens(pages):
    """
    External webhook URLs that embed authentication tokens directly in
    client-side code should be proxied server-side instead.

    Detection pattern: fetch() to a third-party domain where the URL
    path contains a 20+ character alphanumeric segment (token-like string).

    Example of the pattern to flag:
      fetch('https://hook.us2.make.com/AbCdEfGhIjKlMnOpQrSt', ...)
      fetch('https://hooks.zapier.com/hooks/catch/1234/abcdefgh/', ...)

    These webhook receivers use the URL path as an authentication token.
    Any browser user who reads the page source can call them directly.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "fetch(" not in line:
                continue
            # Find fetch URL
            url_m = re.search(r"""fetch\s*\(\s*['"]([^'"]+)['"]""", line)
            if not url_m:
                continue
            url = url_m.group(1)
            if is_allowed_domain(url):
                continue
            if not url.startswith("http"):
                continue

            # Does the URL path contain a token-like segment?
            path_parts = re.sub(r"https?://[^/]+", "", url).split("/")
            for part in path_parts:
                if len(part) >= TOKEN_MIN_LENGTH and re.match(r"^[a-zA-Z0-9_-]+$", part):
                    issues.append({
                        "page":  page,
                        "line":  i + 1,
                        "url":   url[:60] + ("..." if len(url) > 60 else ""),
                        "reason": (
                            f"{page}:{i + 1} — external webhook URL with embedded "
                            f"token hardcoded in client code: '{url[:60]}' — "
                            f"anyone who reads the page source can call this endpoint. "
                            f"Move to a Supabase Edge Function so the URL stays server-side"
                        ),
                    })
                    break
    return issues


# ── Check 2: External fetch calls have timeout ────────────────────────────────

def check_fetch_timeout(pages):
    """
    Every fetch() to an external URL must have a timeout so the UI doesn't
    hang indefinitely when the external service is slow or unavailable.

    Modern pattern: signal: AbortSignal.timeout(30000)
    Legacy pattern: const controller = new AbortController(); setTimeout(() => controller.abort(), N);

    User-facing external calls (AI worker, diagram API) MUST have timeouts.
    Background/fire-and-forget calls (embed-entry, webhooks) SHOULD have them.
    """
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
                # Try template literal with variable
                if not re.search(r"fetch\s*\(", line):
                    continue
                # Variable URL — check context for WORKER_URL, PYTHON_DIAGRAM_API etc.
                if not re.search(
                    r"WORKER_URL|workerUrl|PYTHON_DIAGRAM_API|onrender\.|workers\.dev",
                    line
                ):
                    continue
                url = "[external variable]"
            else:
                url = url_m.group(1)
                if is_allowed_domain(url):
                    continue
                if not url.startswith("http") and not url.startswith("${"):
                    continue

            # Check if timeout/signal appears in the fetch options (next 8 lines)
            window = "\n".join(lines[i:min(len(lines), i + 8)])
            has_timeout = bool(re.search(
                r"AbortSignal|AbortController|signal\s*:|timeout\s*:",
                window
            ))
            if not has_timeout:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "url":  url[:50],
                    "reason": (
                        f"{page}:{i + 1} — external fetch() has no timeout "
                        f"(AbortSignal.timeout or AbortController) — if the "
                        f"external service is unresponsive, this call hangs "
                        f"the user's browser indefinitely"
                    ),
                })
    return issues


# ── Check 3: No credentials logged to console ─────────────────────────────────

def check_no_credential_logging(pages):
    """
    console.log() must never output token values, Bearer strings, API keys,
    or passwords. Log output is captured by browser extensions, DevTools
    recording tools, and error monitoring services (Sentry, Datadog).

    Patterns to flag:
    - console.log(token), console.log(apiKey)
    - console.log("Bearer " + something)
    - console.log({ token: ... })
    """
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
                    issues.append({
                        "page": page,
                        "line": i + 1,
                        "reason": (
                            f"{page}:{i + 1} — console.log outputs a credential "
                            f"value — tokens logged to console can be captured "
                            f"by browser extensions and monitoring tools: "
                            f"`{stripped[:60]}`"
                        ),
                    })
                    break
    return issues


# ── Check 4: All external fetch calls use HTTPS not HTTP ──────────────────────

def check_https_only(pages):
    """
    Any fetch() to an external production service must use https://.
    HTTP sends all data unencrypted: auth headers, user emails, sensor
    readings, and API responses are all visible on the network.

    Localhost URLs (127.0.0.1, localhost) are exempt — they stay on the
    local machine and don't traverse a network.
    """
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
            # Find fetch to http:// (not https://)
            m = re.search(r"""fetch\s*\(\s*['"]http://([^'"]+)['"]""", line)
            if not m:
                continue
            domain = m.group(1).split("/")[0]
            if "localhost" in domain or "127.0.0.1" in domain:
                continue   # local development — acceptable
            issues.append({
                "page": page,
                "line": i + 1,
                "url":  f"http://{m.group(1)[:50]}",
                "reason": (
                    f"{page}:{i + 1} — external fetch() uses HTTP (not HTTPS): "
                    f"'http://{m.group(1)[:50]}' — all data sent unencrypted "
                    f"including auth headers, user data, and API responses"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Integration Security Baseline Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] No third-party webhook tokens hardcoded in client-side code",
        check_webhook_tokens(LIVE_PAGES),
        "WARN",
    ),
    (
        "[2] External fetch calls have timeout (AbortSignal / AbortController)",
        check_fetch_timeout(LIVE_PAGES),
        "WARN",
    ),
    (
        "[3] No API credentials or tokens logged to console",
        check_no_credential_logging(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[4] All external fetch calls use HTTPS not HTTP",
        check_https_only(LIVE_PAGES),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("integration_security_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved integration_security_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll integration security checks PASS.")
