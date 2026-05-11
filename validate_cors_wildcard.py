"""
CORS Wildcard Audit -- WorkHive Platform
=========================================
Catches edge functions that return `Access-Control-Allow-Origin: *` for
hive-scoped data. Wildcard CORS is correct for server-to-server webhook
endpoints (Stripe / Resend POSTing in) but wrong for any function whose
response carries data from one hive that another origin should not see.
A malicious page hosted at `evil.example` can fetch the data from a
worker's browser the moment they sign in elsewhere.

Layer 1 -- Hardcoded wildcard origin                                    [WARN]
  Any edge fn that literally returns `'Access-Control-Allow-Origin': '*'`
  in its response headers, unless the fn is allowlisted as a server-to-
  server webhook (CORS_WILDCARD_OK).

Layer 2 -- Wildcard on data-returning fn                                [WARN]
  Any fn that BOTH returns wildcard CORS AND reads from a Supabase
  table (`db.from(...)` or `createClient(...)`). The wildcard origin
  combined with hive-scoped data is the cross-origin-leak shape.

Layer 3 -- CORS strategy distribution (informational)                   [INFO]
  Per-fn classification: dynamic (uses _shared/cors.ts helper), static
  (hardcodes `_PROD` constant), wildcard, none-explicit (relies on
  Supabase default), or no-CORS-headers.

Layer 4 -- Origin echo without allowlist (informational)                [INFO]
  Functions that echo `req.headers.get('origin')` directly into the
  response without an allowlist check. The `_shared/cors.ts` helper
  does the allowlist; ad-hoc echoes can leak.

Skills consulted: security (CORS is the front-line for cross-origin
data exfiltration), enterprise-compliance (data residency relies on
strict origin allowlists), notifications (webhook fns are the legit
exception that the gate must allow without false-flagging).
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


FUNCTIONS_DIR = os.path.join("supabase", "functions")

# Webhook / server-to-server fns that legitimately use wildcard CORS.
CORS_WILDCARD_OK = {
    "marketplace-webhook":  "Stripe webhook; called server-to-server, no browser CORS surface",
    "stripe-webhook":       "(reserved) Stripe webhook style endpoint",
}

WILDCARD_RE = re.compile(
    r"""['"]Access-Control-Allow-Origin['"]\s*:\s*['"]\*['"]""",
    re.IGNORECASE,
)
ECHO_ORIGIN_RE = re.compile(
    r"""['"]Access-Control-Allow-Origin['"]\s*:\s*req\.headers\.get\s*\(\s*['"]origin['"]""",
    re.IGNORECASE,
)
DYNAMIC_HELPER_RE = re.compile(
    r"""getCorsHeaders\s*\(""",
)
DB_FROM_RE = re.compile(r"""\.from\s*\(\s*['"]\w+['"]\s*\)""")
CREATE_CLIENT_RE = re.compile(r"""createClient\s*\(""")


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


# -- Layer 1: Hardcoded wildcard --------------------------------------------

def check_hardcoded_wildcard(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in CORS_WILDCARD_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        if not WILDCARD_RE.search(src):
            continue
        report.append({"fn": name, "path": path})
        issues.append({
            "check": "hardcoded_wildcard", "skip": True,
            "reason": (
                f"{name}/index.ts returns `'Access-Control-Allow-Origin': '*'` "
                f"in its response headers. Replace with the dynamic helper "
                f"`getCorsHeaders(req)` from `_shared/cors.ts`, or add "
                f"'{name}' to CORS_WILDCARD_OK with a justification (e.g., "
                f"server-to-server webhook called by Stripe / Resend / "
                f"GitHub, with no browser CORS surface)."
            ),
        })
    return issues, report


# -- Layer 2: Wildcard + data-returning ------------------------------------

def check_wildcard_on_data_fn(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in CORS_WILDCARD_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        has_wildcard = bool(WILDCARD_RE.search(src))
        has_data = bool(DB_FROM_RE.search(src) or CREATE_CLIENT_RE.search(src))
        if has_wildcard and has_data:
            report.append({"fn": name, "path": path})
            issues.append({
                "check": "wildcard_on_data_fn", "skip": True,
                "reason": (
                    f"{name}/index.ts has wildcard CORS AND reads/writes a "
                    f"Supabase table -- ANY origin can fetch this fn's "
                    f"output from a signed-in worker's browser. Switch to "
                    f"the dynamic helper or scope the fn to a specific "
                    f"allowlisted origin via _shared/cors.ts."
                ),
            })
    return issues, report


# -- Layer 3: CORS strategy distribution (informational) -------------------

def classify(src: str, name: str) -> str:
    if name in CORS_WILDCARD_OK:
        return "wildcard_ok"
    if WILDCARD_RE.search(src):
        return "wildcard"
    if DYNAMIC_HELPER_RE.search(src):
        return "dynamic_helper"
    if ECHO_ORIGIN_RE.search(src):
        return "echo_origin"
    if "Access-Control-Allow-Origin" in src:
        return "static"
    return "no_cors_headers"


def check_strategy_distribution(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    counter: dict[str, list[str]] = defaultdict(list)
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        counter[classify(src, name)].append(name)
    rows: list[dict] = []
    for strategy, fns_in in sorted(counter.items()):
        rows.append({
            "strategy": strategy,
            "count":    len(fns_in),
            "sample":   sorted(fns_in)[:5],
        })
    return [], rows


# -- Layer 4: Origin echo without allowlist (informational) ----------------

def check_echo_without_allowlist(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        if not ECHO_ORIGIN_RE.search(src):
            continue
        # Allow if file ALSO references getCorsHeaders helper (centralizes).
        if DYNAMIC_HELPER_RE.search(src):
            continue
        # Heuristic: look for an allowlist constant (string literal `https://`).
        has_allowlist = bool(re.search(
            r"""(?:ALLOWED_ORIGINS?|allowedOrigins?)\s*[:=]""", src
        ))
        if has_allowlist:
            continue
        rows.append({"fn": name})
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "hardcoded_wildcard",
    "wildcard_on_data_fn",
    "strategy_distribution",
    "echo_without_allowlist",
]
CHECK_LABELS = {
    "hardcoded_wildcard":      "L1  No edge fn hardcodes Access-Control-Allow-Origin: *         [WARN]",
    "wildcard_on_data_fn":     "L2  No data-returning fn returns wildcard CORS                  [WARN]",
    "strategy_distribution":   "L3  CORS strategy classification per fn (informational)         [INFO]",
    "echo_without_allowlist":  "L4  Origin echo paired with allowlist (informational)           [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCORS Wildcard Audit (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned (CORS_WILDCARD_OK={len(CORS_WILDCARD_OK)}).\n")

    l1_issues, l1_report = check_hardcoded_wildcard(fns)
    l2_issues, l2_report = check_wildcard_on_data_fn(fns)
    l3_issues, l3_report = check_strategy_distribution(fns)
    l4_issues, l4_report = check_echo_without_allowlist(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('CORS STRATEGY DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report:
            sample = ", ".join(r["sample"][:3])
            tail = f" ({sample}{'...' if len(r['sample']) >= 3 else ''})" if r["sample"] else ""
            print(f"  {r['strategy']:<24}  count={r['count']:<3}{tail}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "cors_wildcard",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "n_fns":                 len(fns),
        "hardcoded_wildcard":    l1_report,
        "wildcard_on_data":      l2_report,
        "strategy_distribution": l3_report,
        "echo_without_allowlist": l4_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("cors_wildcard_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
