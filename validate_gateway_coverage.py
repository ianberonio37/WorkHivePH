"""
Platform Gateway Coverage -- WorkHive Platform
==================================================
Catches the gateway-bypass bug class: edge fns callable directly from
the frontend, each re-implementing auth, rate-limit, and audit logging
independently. Drift between implementations is inevitable.

Phase 2.1 of the roadmap: the platform-gateway is the single entry
point. Each edge fn is either routed through it OR explicitly opted
out (cron-only, webhook receivers, etc.) with a justification.

Layer 1 -- platform-gateway edge fn present                              [FAIL]
  supabase/functions/platform-gateway/ must exist with a PLATFORM_ROUTES
  registry. Without it Phase 2.1 is not started.

Layer 2 -- Every PLATFORM_ROUTES target exists on disk                   [FAIL]
  Each fn name advertised by the gateway must have its own
  supabase/functions/<name>/index.ts. Phantom routes return 502.

Layer 3 -- Every user-facing edge fn is routed or allowlisted            [WARN]
  Any callable edge fn not in PLATFORM_ROUTES and not in
  GATEWAY_BYPASS_OK is a candidate for migration. Forward-looking
  ratchet -- DEFERRED until adoption catches up.

Layer 4 -- Gateway routing inventory (informational)                     [INFO]
  Per-fn map: routed / bypassed / cron-only / webhook / ai-only.

Skills consulted: ai-engineer (gateway pattern), security (single
choke point for auth/rate-limit), architect (single-entry-point vs
sidecar trade-off).
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


FUNCTIONS_DIR     = os.path.join("supabase", "functions")
PLATFORM_GATEWAY  = os.path.join(FUNCTIONS_DIR, "platform-gateway", "index.ts")
AI_GATEWAY        = os.path.join(FUNCTIONS_DIR, "ai-gateway", "index.ts")

# Fns legitimately not routed through platform-gateway. Each entry needs
# a one-line justification.
GATEWAY_BYPASS_OK = {
    # Gateways themselves.
    "platform-gateway":           "The gateway itself; routes other fns",
    "ai-gateway":                 "AI router (heavier per-call work); routes specialist agents",
    # Cron-only / scheduled.
    "scheduled-agents":           "pg_cron-only invocation; no user surface",
    "ai-eval-runner":             "Cron-only nightly eval pass",
    "batch-risk-scoring":         "Cron-only batch job",
    "trigger-ml-retrain":         "Cron-only training trigger",
    # Webhook receivers (external systems POST in; cannot be wrapped).
    "marketplace-webhook":        "Stripe webhook signing; raw body required",
    "cmms-webhook-receiver":      "External CMMS webhook signing; raw body required",
    # Specialist agents called BY the gateways themselves.
    "asset-brain-query":          "Specialist routed by ai-gateway",
    "analytics-orchestrator":     "Specialist routed by ai-gateway",
    "project-orchestrator":       "Specialist routed by ai-gateway",
    "shift-planner-orchestrator": "Specialist routed by ai-gateway",
    "voice-logbook-entry":        "Specialist routed by ai-gateway",
    "voice-report-intent":        "Specialist routed by ai-gateway",
    "voice-journal-agent":        "Specialist routed by ai-gateway",
    "engineering-calc-agent":     "Public calc endpoint; opt-out for now",
    "engineering-bom-sow":        "Public BOM/SOW endpoint; opt-out for now",
    # Cross-tenant / cross-hive.
    "cmms-sync":                  "Initiated server-side from hive admin tooling",
    "cmms-push-completion":       "Server-side dispatch from analytics-orchestrator",
    "parts-staging-recommender":  "Server-side dispatch from analytics-orchestrator",
    "marketplace-connect-onboard": "Stripe redirect dance; opt-out for now",
    "embed-entry":                "Write-only embedding pipeline; not user-facing",
    "ai-orchestrator":            "Legacy orchestrator; superseded by ai-gateway",
    "project-progress":           "Server-side rollup helper; not user-facing",
    "failure-signature-scan":     "Server-side analytics job; not user-facing",
    "fmea-populator":             "Server-side populate; opt-out for now",
    "benchmark-compute":          "Internal benchmark trigger; not user-facing",
}

# Forward-looking ratchet — Phase 2.1 is partially adopted. Every fn
# above (or routed through platform-gateway) accounts for the full set.
GATEWAY_COVERAGE_DEFERRED = True


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            if d.startswith("_"):
                continue   # _shared
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _parse_platform_routes() -> dict[str, str]:
    """Extract { route_key: target_fn } from PLATFORM_ROUTES registry."""
    out: dict[str, str] = {}
    src = read_file(PLATFORM_GATEWAY)
    if not src:
        return out
    m = re.search(
        r"""PLATFORM_ROUTES\s*:\s*Record<string,\s*\{[^}]*\}>\s*=\s*\{(?P<body>[\s\S]*?)\n\};""",
        src,
    )
    if not m:
        return out
    body = m.group("body")
    for entry in re.finditer(
        r"""['"]([a-z0-9_-]+)['"]\s*:\s*\{[^{}]*?fn\s*:\s*['"]([a-z0-9_-]+)['"]""",
        body, re.DOTALL,
    ):
        out[entry.group(1)] = entry.group(2)
    return out


# -- Layer 1: platform-gateway present ----------------------------------

def check_platform_gateway_present() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    present = os.path.isfile(PLATFORM_GATEWAY)
    routes  = _parse_platform_routes() if present else {}
    report = [{
        "gateway_present": present,
        "n_routes":        len(routes),
    }]
    if not present:
        issues.append({
            "check": "platform_gateway_present", "skip": False,
            "reason": (
                f"{PLATFORM_GATEWAY} not found. Phase 2.1 not started -- "
                f"non-AI edge fns each re-implement auth + rate-limit "
                f"independently."
            ),
        })
    elif not routes:
        issues.append({
            "check": "platform_gateway_present", "skip": True,
            "reason": (
                "platform-gateway present but PLATFORM_ROUTES registry "
                "is empty -- nothing is actually being routed."
            ),
        })
    return issues, report


# -- Layer 2: Every routed target exists on disk ------------------------

def check_routes_exist() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    routes = _parse_platform_routes()
    for key, target in sorted(routes.items()):
        path = os.path.join(FUNCTIONS_DIR, target, "index.ts")
        ok = os.path.isfile(path)
        report.append({"route": key, "target": target, "exists": ok})
        if not ok:
            issues.append({
                "check": "routes_exist", "skip": False,
                "reason": (
                    f"PLATFORM_ROUTES advertises '{key}' -> '{target}' "
                    f"but {path} does not exist -- requests will 502."
                ),
            })
    return issues, report


# -- Layer 3: Every fn is routed or allowlisted ------------------------

def check_coverage(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    routes  = _parse_platform_routes()
    routed_targets = set(routes.values())
    for name, _ in fns:
        if name in GATEWAY_BYPASS_OK:
            report.append({"fn": name, "status": "bypass_ok"})
            continue
        if name in routed_targets:
            report.append({"fn": name, "status": "routed"})
            continue
        report.append({"fn": name, "status": "uncovered"})
        issues.append({
            "check": "coverage", "skip": GATEWAY_COVERAGE_DEFERRED,
            "reason": (
                f"{name}: callable edge fn not routed through "
                f"platform-gateway and not in GATEWAY_BYPASS_OK. Add a "
                f"PLATFORM_ROUTES entry OR list in GATEWAY_BYPASS_OK "
                f"with a justification."
            ),
        })
    return issues, report


# -- Layer 4: Gateway routing inventory --------------------------------

def check_inventory(fns) -> tuple[list[dict], list[dict]]:
    routes = _parse_platform_routes()
    routed_targets = set(routes.values())
    counts: dict[str, int] = defaultdict(int)
    rows: list[dict] = []
    for name, _ in fns:
        if name in routed_targets:
            kind = "routed"
        elif name in GATEWAY_BYPASS_OK:
            kind = "bypass_ok"
        else:
            kind = "uncovered"
        counts[kind] += 1
        rows.append({"fn": name, "kind": kind})
    return [], [{"counts": dict(counts)}, *rows]


# -- Runner ------------------------------------------------------------

CHECK_NAMES = [
    "platform_gateway_present",
    "routes_exist",
    "coverage",
    "inventory",
]
CHECK_LABELS = {
    "platform_gateway_present": "L1  platform-gateway edge fn present + has routes              [FAIL]",
    "routes_exist":             "L2  Every PLATFORM_ROUTES target exists on disk                [FAIL]",
    "coverage":                 "L3  Every user-facing fn is routed or allowlisted              [WARN]",
    "inventory":                "L4  Per-fn routing kind inventory                              [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nPlatform Gateway Coverage (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    routes = _parse_platform_routes()
    print(f"  {len(fns)} edge fn(s), {len(routes)} routed, GATEWAY_BYPASS_OK={len(GATEWAY_BYPASS_OK)}.\n")

    l1_issues, l1_report = check_platform_gateway_present()
    l2_issues, l2_report = check_routes_exist()
    l3_issues, l3_report = check_coverage(fns)
    l4_issues, l4_report = check_inventory(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('GATEWAY ROUTING INVENTORY')}")
        print("  " + "-" * 56)
        counts = l4_report[0].get("counts", {})
        for kind, n in sorted(counts.items()):
            print(f"  {kind:<14}  {n}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":                "gateway_coverage",
        "total_checks":             total,
        "passed":                   n_pass,
        "warned":                   n_warn,
        "failed":                   n_fail,
        "n_fns":                    len(fns),
        "n_routes":                 len(routes),
        "platform_gateway_present": l1_report,
        "routes_exist":             l2_report,
        "coverage":                 l3_report,
        "inventory":                l4_report,
    }
    try:
        with open("gateway_coverage_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
