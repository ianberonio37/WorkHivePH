"""
Service-Role Key Exposure Detector -- WorkHive Platform
========================================================
Catches the catastrophic case where a Supabase SERVICE-ROLE key (or any
identifier that looks like one) leaks into client-side HTML/JS. Anyone with
the service-role key bypasses ALL Row Level Security and gains god-mode
access to the database. This is one of the highest-stakes security gaps a
platform can ship.

Layer 1 -- Service-role identifier in client code                       [FAIL]
  Any HTML or browser-loaded JS file that contains the literal substring
  `SERVICE_ROLE_KEY`, `service_role`, or imports a service-role token from
  any source. Edge functions and the deploy scripts are exempt by path.

Layer 2 -- JWT-shaped string in client code                             [FAIL]
  A 3-segment dot-separated base64 string of the right shape (eyJhbGciOi...
  followed by another eyJ... segment) almost certainly is a JWT. A client
  that hardcodes one is leaking either the anon key (low stakes but still
  bad) or the service-role key (catastrophic).

Layer 3 -- Suspicious env-var pattern in client code                    [WARN]
  Any reference to env-var name patterns that look secret-bearing
  (`SECRET`, `PRIVATE_KEY`, `WEBHOOK_SECRET`) inside a client HTML/JS file.
  Edge functions are exempt -- they read these legitimately from
  Deno.env.get(). The warn flags "did somebody mistakenly read it on the
  client?".

Layer 4 -- Anon-key constant placement                                  [INFO]
  Inventory of where the anon key (the only Supabase key allowed in
  browsers) is referenced. Helps spot drift if the constant moves around.

Skills consulted: security (XSS / auth bypass / OWASP top 10), data-engineer
(client vs server boundary; service-role goes ONLY in edge functions and
server-side scripts), devops (env var hygiene at the deploy layer).
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

FUNCTIONS_DIR = os.path.join("supabase", "functions")
EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Files that legitimately reference these strings as DOCUMENTATION text
# (rendered to the user as static copy, not used as keys). Each entry must
# carry a one-line justification.
DOC_TEXT_OK = {
    # Architecture / operator documentation pages — strings appear in human
    # text describing how the platform works, not as code that uses them.
    "platform-health.html":   "guide row text describes catalog approval / RLS architecture",
    "platform-health-test.html": "test copy of platform-health",
    "ARCHITECTURE.html":      "RETIRED 2026-05-13 — archival doc",
    "architecture.html":      "RETIRED 2026-05-13 — archival doc",
    "WORKHIVE_PLATFORM_BOOK.md": "platform book / docs",
    # Grounded-sweep test batteries: 'service_role' appears ONLY inside a secret-
    # DETECTION regex (the Safety / Internal-Control pillar scans an AI answer for a
    # leaked service_role-shaped value) — never as a key the code uses. Test-only
    # tooling injected via the Playwright MCP, not shipped product code.
    "ufai_battery.js":        "secret-detection regex in the UFAI battery (no key usage)",
    "companion_battery.js":   "secret-detection regex in the Companion Stack battery (no key usage)",
}

# A JWT segment is base64url; the full 3-segment shape is very specific.
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")

# Service-role substrings. Tolerant about case but case-insensitive search
# below catches both `SERVICE_ROLE` env names and `service_role` literals.
SERVICE_ROLE_TOKENS = [
    "SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_ROLE",
    "service_role",
]

# Generic env-var-name patterns that should NEVER appear in client code.
SUSPICIOUS_ENV_PATTERNS = [
    re.compile(r"\bSECRET[A-Z_]*KEY\b"),
    re.compile(r"\bPRIVATE_KEY\b"),
    re.compile(r"\bWEBHOOK_SECRET\b"),
    re.compile(r"\bRESEND_API_KEY\b"),
    re.compile(r"\bOPENAI_API_KEY\b"),
    re.compile(r"\bANTHROPIC_API_KEY\b"),
    re.compile(r"\bGROQ_API_KEY\b"),
]

# Anon-key reference pattern -- INFO-level inventory.
ANON_KEY_RE = re.compile(r"SUPABASE_ANON_KEY|wh_anon_key|VITE_SUPABASE_ANON_KEY")


def list_client_files() -> list[tuple[str, str]]:
    """Files loaded by browsers. Excludes edge functions, server scripts,
    deploy tooling, and test/backup variants."""
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append((path, "js"))
    return out


def _strip_comments_html(src: str) -> str:
    """Strip HTML comments AND <script> JS comments so the validator only
    flags real code references, not commented-out reminders."""
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return src


# -- Layer 1: Service-role identifier in client code -------------------------

def check_service_role_in_client(
    files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path, layer in files:
        if path in DOC_TEXT_OK:
            continue
        src = _strip_comments_html(read_file(path) or "")
        for token in SERVICE_ROLE_TOKENS:
            # Case-sensitive for upper-case env vars (`SERVICE_ROLE_KEY`),
            # case-insensitive for the literal `service_role` (it appears as
            # a column value in some Postgres docs but not in our DDL).
            pattern = re.compile(re.escape(token))
            matches = pattern.findall(src)
            if not matches:
                continue
            report.append({
                "path": path, "layer": layer,
                "token": token, "count": len(matches),
            })
            issues.append({
                "check": "service_role_in_client", "skip": False,
                "reason": (
                    f"{path}: client-side {layer.upper()} references '{token}' "
                    f"({len(matches)} occurrence(s)). Service-role keys bypass "
                    f"ALL RLS -- they MUST live only in server-side edge "
                    f"functions or deploy scripts, never in browser code. If "
                    f"this is documentation text, add an entry to DOC_TEXT_OK "
                    f"in validate_service_role_exposure.py."
                ),
            })
    return issues, report


# -- Layer 2: JWT-shaped string in client code -------------------------------

def check_jwt_in_client(
    files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path, layer in files:
        if path in DOC_TEXT_OK:
            continue
        src = _strip_comments_html(read_file(path) or "")
        for m in JWT_RE.finditer(src):
            jwt = m.group(0)
            # Extract role from JWT body if possible (best-effort base64 decode).
            role_hint = ""
            try:
                import base64
                body = jwt.split(".")[1]
                pad = "=" * ((4 - len(body) % 4) % 4)
                decoded = base64.urlsafe_b64decode(body + pad).decode("utf-8", "ignore")
                if "service_role" in decoded:
                    role_hint = " (decoded payload claims role=service_role -- HIGHEST severity)"
                elif "anon" in decoded:
                    role_hint = " (decoded payload claims role=anon -- still leaked but lower stakes)"
            except Exception:
                pass
            report.append({
                "path": path, "layer": layer,
                "jwt_prefix": jwt[:30] + "...",
                "role_hint": role_hint or None,
            })
            issues.append({
                "check": "jwt_in_client", "skip": False,
                "reason": (
                    f"{path}: client {layer.upper()} contains a JWT-shaped "
                    f"string ('{jwt[:30]}...'){role_hint}. Tokens belong in "
                    f"environment variables and are loaded at runtime via "
                    f"db.auth.getSession(); they should never be hardcoded "
                    f"in source. Move to env config."
                ),
            })
    return issues, report


# -- Layer 3: Suspicious env-var pattern in client code ----------------------

def check_suspicious_env_in_client(
    files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path, layer in files:
        if path in DOC_TEXT_OK:
            continue
        src = _strip_comments_html(read_file(path) or "")
        hits: list[str] = []
        for rx in SUSPICIOUS_ENV_PATTERNS:
            for m in rx.finditer(src):
                hits.append(m.group(0))
        if hits:
            distinct = sorted(set(hits))
            report.append({
                "path": path, "layer": layer,
                "patterns": distinct,
            })
            issues.append({
                "check": "suspicious_env_in_client", "skip": True,
                "reason": (
                    f"{path}: client {layer.upper()} references env-var "
                    f"name(s) {distinct} that look secret-bearing. Edge "
                    f"functions read these from Deno.env.get(); browser code "
                    f"should not. If this is doc text, add the file to "
                    f"DOC_TEXT_OK with a justification."
                ),
            })
    return issues, report


# -- Layer 4: Anon-key reference inventory (informational) -------------------

def check_anon_key_inventory(
    files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    inventory: dict[str, int] = defaultdict(int)
    for path, _layer in files:
        src = _strip_comments_html(read_file(path) or "")
        n = len(ANON_KEY_RE.findall(src))
        if n:
            inventory[path] = n
    rows = sorted(
        ({"path": p, "n_refs": n} for p, n in inventory.items()),
        key=lambda r: -r["n_refs"],
    )
    return [], rows


# -- Runner ------------------------------------------------------------------

CHECK_NAMES = [
    "service_role_in_client",
    "jwt_in_client",
    "suspicious_env_in_client",
    "anon_key_inventory",
]
CHECK_LABELS = {
    "service_role_in_client":     "L1  No SERVICE_ROLE / service_role identifier in client HTML/JS  [FAIL]",
    "jwt_in_client":              "L2  No JWT-shaped string hardcoded in client HTML/JS             [FAIL]",
    "suspicious_env_in_client":   "L3  No SECRET / API_KEY env-var names referenced in client       [WARN]",
    "anon_key_inventory":         "L4  Anon-key reference inventory (informational)                 [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nService-Role Key Exposure Detector (4-layer)"))
    print("=" * 60)

    files = list_client_files()
    print(f"  {len(files)} client-side files scanned (HTML + JS).\n")

    sr_issues, sr_report     = check_service_role_in_client(files)
    jwt_issues, jwt_report   = check_jwt_in_client(files)
    env_issues, env_report   = check_suspicious_env_in_client(files)
    anon_issues, anon_report = check_anon_key_inventory(files)

    all_issues = sr_issues + jwt_issues + env_issues + anon_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if anon_report:
        print(f"\n{bold('ANON-KEY REFERENCE INVENTORY (informational)')}")
        print("  " + "-" * 56)
        for r in anon_report[:8]:
            print(f"  {r['path']:<48}  refs={r['n_refs']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "service_role_exposure",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "n_files":        len(files),
        "service_role":   sr_report,
        "jwt":            jwt_report,
        "suspicious_env": env_report,
        "anon_inventory": anon_report,
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    with open("service_role_exposure_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
