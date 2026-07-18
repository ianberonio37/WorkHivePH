"""
Hardcoded Secret Detector -- WorkHive Platform
===============================================
Catches API keys, passwords, and provider tokens hardcoded in source
code. Sister gate to `validate_service_role_exposure` (which catches
SUPABASE service-role keys specifically) and `validate_env_secret_coverage`
(which catches missing env-var declarations on the deploy side). This
gate covers the third dimension: tokens for OpenAI, Anthropic, Resend,
GitHub, etc. that should live in `.env` / Deno.env.get(...) but
sometimes get pasted into source during a debug session and never moved
out.

Layer 1 -- Provider-specific token prefix in source                     [FAIL]
  Strings matching the well-known token prefixes of major providers:
    sk-...              OpenAI
    sk-ant-...          Anthropic
    re_...              Resend
    ghp_..., gho_..., ghu_...   GitHub
    xoxb-..., xoxa-..., xoxp-...   Slack
    AIza...             Google Cloud / Gemini
  Each prefix is followed by a base64-ish body of sufficient length
  that random words don't match.

Layer 2 -- Generic password assignment                                  [WARN]
  Patterns like `password = "literal"` / `secret: "literal"` /
  `apiKey = "literal"` outside the `.env*` files. Lower stakes than
  L1 but still worth surfacing.

Layer 3 -- Provider distribution (informational)                        [INFO]
  Per-provider count of hits. Helps spot whether a single sloppy
  commit dropped tokens across multiple files.

Layer 4 -- Files exempt by allowlist (informational)                    [INFO]
  Inventory of files that are allowed to contain literal secrets:
  `.env*`, deploy templates, sample env files. These are tracked so
  the gate's exemption surface stays auditable.

Skills consulted: security (OWASP top 10 secrets management), devops
(env var hygiene at deploy time, Supabase project secrets), enterprise-
compliance (audit traceability for secret rotation events).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
import subprocess
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Files that are intentionally allowed to contain example / placeholder
# secret strings (env templates, README excerpts, deploy docs).
ALLOWLISTED_PATHS = {
    ".env",
    ".env.example",
    ".env.local",
    ".env.production",
    "supabase/functions/.env",
    "supabase/functions/.env.example",
    "_headers",
}
ALLOWLIST_DIRS = (
    "test-data-seeder",
    "node_modules",
    ".git",
    "video_marketing_app",
    "substrate",   # harvested EXTERNAL content, not our code (2026-07-18): keep out of doc-scan noise
    ".tmp",        # disposable intermediates
)

# Patterns. Each: (provider_name, regex). The bodies require enough chars
# to avoid stumbling over short strings that happen to match the prefix.
PROVIDER_PATTERNS = [
    ("OpenAI",     re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("Anthropic",  re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{32,}")),
    ("Resend",     re.compile(r"\bre_[A-Za-z0-9]{16,}")),
    ("GitHub",     re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}")),
    ("Slack",      re.compile(r"\b(xoxb|xoxa|xoxp|xoxs|xoxr)-[A-Za-z0-9\-]{16,}")),
    ("Google API", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}")),
    ("Groq",       re.compile(r"\bgsk_[A-Za-z0-9]{40,}")),
    ("Cerebras",   re.compile(r"\bcsk?-[A-Za-z0-9]{32,}")),   # real keys are csk-...; the old cs- prefix MISSED them (2026-07-18 leak)
    ("DeepSeek",   re.compile(r"\bsk-deepseek-[A-Za-z0-9]{20,}")),
    ("Voyage",     re.compile(r"\bpa-[A-Za-z0-9_]{40,}\b")),  # Voyage AI embed keys (2026-07-18 leak); no hyphen in body avoids slug false-positives
    ("Jina",       re.compile(r"\bjina_[A-Za-z0-9_]{30,}")),  # Jina embed keys (2026-07-18 leak)
]

# Generic password / secret assignment.
GENERIC_RE = re.compile(
    r"""(?P<key>password|secret|api[-_]?key|access[-_]?key|private[-_]?key)
        \s*[:=]\s*['"`](?P<val>[^'"`]{8,})['"`]""",
    re.IGNORECASE | re.VERBOSE,
)
# Whitelist values that look like placeholders, not real secrets.
PLACEHOLDER_RE = re.compile(
    r"^(your[-_]?\w*|placeholder|xxx|example|<.*>|change.?me|todo|test|sample|undefined|null|none|\$\{[^}]+\})$",
    re.IGNORECASE,
)


def _is_allowlisted(path: str) -> bool:
    rel = path.replace("\\", "/").lstrip("./")
    if rel in ALLOWLISTED_PATHS:
        return True
    parts = rel.split("/")
    return any(p in ALLOWLIST_DIRS for p in parts)


def _tracked_doc_files() -> list[str]:
    """Git-TRACKED docs + config (.md/.txt/.sh/.ps1/.yml/.yaml) — the public-leak surface the
    code-only globs above never scanned. On 2026-07-18 a real Groq/Cerebras/Voyage/Jina key block
    pasted into a tracked .md deploy-notes doc (PHASE_1_5_2_DEPLOYMENT.md) leaked to the PUBLIC repo
    and tripped GitHub secret-scanning; neither this gate (code-only) nor validate_committed_env_secret
    (.env-only) covered a .md. Scanning the tracked doc set closes that exact crack. Tracked-only =
    exactly the set that can leak; avoids walking node_modules."""
    try:
        res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    exts = (".md", ".txt", ".sh", ".ps1", ".yml", ".yaml")
    return [f for f in res.stdout.splitlines() if f.lower().endswith(exts)]


def list_scannable_files() -> list[str]:
    out: list[str] = []
    # Top-level HTML / JS / CSS / TS
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append(path)
    # Supabase fns + shared
    for path in sorted(glob.glob("supabase/functions/**/*.ts", recursive=True)):
        out.append(path)
    # Python API
    for path in sorted(glob.glob("python-api/**/*.py", recursive=True)):
        out.append(path)
    # Validators / orchestrator scripts
    for path in sorted(glob.glob("*.py")):
        out.append(path)
    # Docs + config (2026-07-18 leak): pasted provider keys in tracked .md/.txt/.sh/.ps1/.yml
    out.extend(_tracked_doc_files())
    out = sorted(set(out))
    return [p for p in out if not _is_allowlisted(p)]


# -- Layer 1: Provider-specific tokens --------------------------------------

def check_provider_tokens(files: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in files:
        src = read_file(path) or ""
        # Strip block comments to avoid false positives where a comment
        # mentions an example like `// e.g., sk-...`.
        # Don't strip line comments because some provider keys appear in
        # actual code on the same line as `#` etc.
        cleaned = re.sub(r"/\*[\s\S]*?\*/", "", src)
        for provider, rx in PROVIDER_PATTERNS:
            for m in rx.finditer(cleaned):
                # Skip if surrounded by `redact(` or appears in a comment.
                start = m.start()
                # Look at preceding chars; if `//` appears on same line
                # before the match, treat as comment-only.
                line_start = cleaned.rfind("\n", 0, start) + 1
                line_prefix = cleaned[line_start:start]
                if "//" in line_prefix or "#" in line_prefix:
                    continue
                token = m.group(0)
                report.append({
                    "path":     path,
                    "provider": provider,
                    "preview":  token[:12] + "...",
                    "line":     cleaned.count("\n", 0, start) + 1,
                })
                issues.append({
                    "check": "provider_tokens", "skip": False,
                    "reason": (
                        f"{path}:{cleaned.count(chr(10), 0, start) + 1}: "
                        f"{provider} token starting `{token[:12]}...` is "
                        f"hardcoded in source. Move to .env / "
                        f"Deno.env.get('{provider.upper().replace(' ', '_')}_KEY') "
                        f"and rotate the leaked key immediately."
                    ),
                })
    return issues, report


# -- Layer 2: Generic password assignment -----------------------------------

def check_generic_assignments(files: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in files:
        src = read_file(path) or ""
        cleaned = re.sub(r"/\*[\s\S]*?\*/", "", src)
        for m in GENERIC_RE.finditer(cleaned):
            val = m.group("val")
            # Skip placeholder values
            if PLACEHOLDER_RE.match(val.strip()):
                continue
            # Skip env-var references (Deno.env.get / process.env.X)
            if "env." in val.lower() or val.startswith("Deno"):
                continue
            # Skip values that look like CSS / config tokens (hex colors,
            # short alphanumeric flags).
            if re.fullmatch(r"#?[0-9a-f]{6,8}", val):
                continue
            start = m.start()
            line = cleaned.count("\n", 0, start) + 1
            line_start = cleaned.rfind("\n", 0, start) + 1
            line_prefix = cleaned[line_start:start]
            if "//" in line_prefix or "#" in line_prefix:
                continue
            report.append({
                "path":  path,
                "line":  line,
                "key":   m.group("key"),
                "preview": val[:12] + "...",
            })
            issues.append({
                "check": "generic_assignments", "skip": True,
                "reason": (
                    f"{path}:{line}: `{m.group('key')}` assigned a literal "
                    f"value `{val[:12]}...`. If this is a real secret, "
                    f"move to environment variables. If it is a non-secret "
                    f"config flag, rename it (e.g., `apiVersion`)."
                ),
            })
    return issues, report


# -- Layer 3: Provider hit distribution (informational) -------------------

def check_provider_distribution(report_l1: list[dict]) -> tuple[list[dict], list[dict]]:
    counter: dict[str, int] = defaultdict(int)
    for r in report_l1:
        counter[r["provider"]] += 1
    rows = [
        {"provider": k, "count": v}
        for k, v in sorted(counter.items(), key=lambda kv: -kv[1])
    ]
    return [], rows


# -- Layer 4: Allowlist inventory (informational) -------------------------

def check_allowlist_inventory() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for p in sorted(ALLOWLISTED_PATHS):
        if os.path.exists(p):
            rows.append({"path": p, "status": "exists"})
        else:
            rows.append({"path": p, "status": "absent"})
    for d in ALLOWLIST_DIRS:
        rows.append({"path": d, "status": "dir_pattern"})
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "provider_tokens",
    "generic_assignments",
    "provider_distribution",
    "allowlist_inventory",
]
CHECK_LABELS = {
    "provider_tokens":       "L1  No provider-specific token (sk-, re_, ghp_, AIza, ...) in source [FAIL]",
    "generic_assignments":   "L2  No password/secret = 'literal' outside .env files                [WARN]",
    "provider_distribution": "L3  Per-provider hit distribution (informational)                    [INFO]",
    "allowlist_inventory":   "L4  Allowlisted-paths inventory (informational)                      [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nHardcoded Secret Detector (4-layer)"))
    print("=" * 60)

    files = list_scannable_files()
    print(f"  {len(files)} file(s) scanned (allowlisted paths excluded).\n")

    l1_issues, l1_report = check_provider_tokens(files)
    l2_issues, l2_report = check_generic_assignments(files)
    l3_issues, l3_report = check_provider_distribution(l1_report)
    l4_issues, l4_report = check_allowlist_inventory()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('PROVIDER HIT DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report:
            print(f"  {r['provider']:<24}  count={r['count']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "hardcoded_secrets",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "n_files":               len(files),
        "provider_tokens":       l1_report,
        "generic_assignments":   l2_report,
        "provider_distribution": l3_report,
        "allowlist_inventory":   l4_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("hardcoded_secrets_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
