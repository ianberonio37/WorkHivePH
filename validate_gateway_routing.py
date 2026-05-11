"""
AI Gateway Routing -- WorkHive Platform
========================================
Validates the ai-gateway's AGENT_ROUTES registry. The gateway is the
single entry point for AI calls; if its routes are out of sync with
the deployed edge functions, requests for valid agents return 4xx
silently to the user.

Layer 1 -- Gateway present                                               [FAIL]
  supabase/functions/ai-gateway/index.ts must exist with the AGENT_ROUTES
  constant. Without it, the platform reverts to direct-call orchestrator
  invocation and the centralised PII / memory / rate-gate is bypassed.

Layer 2 -- Every routed fn exists                                        [FAIL]
  Each value in AGENT_ROUTES must reference an edge function directory
  that exists on disk AND has a config.toml entry. Otherwise the
  gateway returns a 502 forever for that agent_id.

Layer 3 -- Every specialist agent is reachable via gateway               [WARN]
  AI orchestrators in the canonical list (asset-brain-query, analytics-
  orchestrator, project-orchestrator, shift-planner-orchestrator, voice-
  logbook-entry, voice-report-intent) should appear as targets in
  AGENT_ROUTES so the gateway is a true single entry point.

Layer 4 -- Routing inventory (informational)                             [INFO]
  Per-agent: route description, target fn, fn directory present.

Skills consulted: ai-engineer (multi-agent routing patterns), architect
(single entry point, registry-of-routes pattern), devops (deploy-time
sync between code registry and config.toml).
"""
from __future__ import annotations

import re
import json
import sys
import os

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


GATEWAY_FILE  = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
FUNCTIONS_DIR = os.path.join("supabase", "functions")
CONFIG_TOML   = os.path.join("supabase", "config.toml")

# Canonical specialist orchestrators that should be routable through the
# gateway. Each entry needs a one-line justification if it's NOT in
# AGENT_ROUTES (typically: "internal-only", "not user-facing").
EXPECTED_AGENTS = {
    "asset-brain-query":         "asset-specific Q&A; user-facing",
    "analytics-orchestrator":    "OEE / MTBF analytics; user-facing",
    "project-orchestrator":      "project Q&A; user-facing",
    "shift-planner-orchestrator": "shift planning; user-facing",
    "voice-logbook-entry":       "voice -> logbook entry; user-facing",
    "voice-report-intent":       "voice -> report sender; user-facing",
}
# Specialists allowed to NOT appear in gateway routes (e.g., cron-only,
# internal callers, scheduled-agents which is itself an orchestrator).
GATEWAY_EXEMPT = {
    "ai-orchestrator":          "deprecated direct orchestrator; superseded by gateway",
    "scheduled-agents":         "cron-driven only; never invoked via user flow",
    "engineering-calc-agent":   "calc UI invokes directly; not a chat agent",
    "engineering-bom-sow":      "calc UI invokes directly; not a chat agent",
    "fmea-populator":           "internal; called from asset-hub only",
    "failure-signature-scan":   "cron-driven daily",
    "intelligence-report":      "cron-driven scheduled report builder",
    "asset-brain-query":        "(not exempt; included to centralise list)",
    "analytics-orchestrator":   "(not exempt; included to centralise list)",
    "project-orchestrator":     "(not exempt; included to centralise list)",
    "shift-planner-orchestrator": "(not exempt; included to centralise list)",
    "voice-logbook-entry":      "(not exempt; included to centralise list)",
    "voice-report-intent":      "(not exempt; included to centralise list)",
}

AGENT_ROUTES_RE = re.compile(
    r"""const\s+AGENT_ROUTES\s*:\s*Record<string,\s*\{[^}]*\}>\s*=\s*\{(?P<body>[\s\S]*?)\n\};""",
)
ROUTE_ENTRY_RE = re.compile(
    r"""['"`]?(?P<agent>[a-z0-9_-]+)['"`]?\s*:\s*\{\s*
        fn\s*:\s*['"`](?P<fn>[a-z0-9_-]+)['"`]""",
    re.VERBOSE,
)


def parse_routes() -> dict[str, str]:
    src = read_file(GATEWAY_FILE) or ""
    m = AGENT_ROUTES_RE.search(src)
    if not m:
        return {}
    body = m.group("body")
    out: dict[str, str] = {}
    for entry in ROUTE_ENTRY_RE.finditer(body):
        out[entry.group("agent")] = entry.group("fn")
    return out


# -- Layer 1: Gateway present ---------------------------------------------

def check_gateway_present() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    exists = os.path.isfile(GATEWAY_FILE)
    routes = parse_routes() if exists else {}
    report.append({
        "gateway_path":   GATEWAY_FILE,
        "gateway_exists": exists,
        "n_routes":       len(routes),
    })
    if not exists:
        issues.append({
            "check": "gateway_present", "skip": False,
            "reason": (
                f"{GATEWAY_FILE} not found. The AI gateway is the single "
                f"entry point for AI calls; without it, PII redaction and "
                f"memory hydration are bypassed."
            ),
        })
        return issues, report
    if not routes:
        issues.append({
            "check": "gateway_present", "skip": False,
            "reason": (
                f"{GATEWAY_FILE} exists but AGENT_ROUTES could not be "
                f"parsed. Check the constant declaration shape."
            ),
        })
    return issues, report


# -- Layer 2: Routed fns exist on disk ------------------------------------

def check_routes_exist(routes: dict[str, str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    cfg = read_file(CONFIG_TOML) or ""
    for agent, fn in routes.items():
        fn_dir   = os.path.join(FUNCTIONS_DIR, fn)
        fn_index = os.path.join(fn_dir, "index.ts")
        in_cfg   = bool(re.search(rf"\[functions\.{re.escape(fn)}\]", cfg))
        present  = os.path.isfile(fn_index)
        report.append({
            "agent":     agent,
            "fn":        fn,
            "on_disk":   present,
            "in_config": in_cfg,
        })
        if not present:
            issues.append({
                "check": "routes_exist", "skip": False,
                "reason": (
                    f"AGENT_ROUTES['{agent}'] -> '{fn}' but "
                    f"{fn_index} does not exist. Gateway returns 502 "
                    f"for this agent."
                ),
            })
        if not in_cfg:
            issues.append({
                "check": "routes_exist", "skip": True,
                "reason": (
                    f"AGENT_ROUTES['{agent}'] -> '{fn}' has source on "
                    f"disk but no [functions.{fn}] entry in config.toml. "
                    f"Edge fn won't deploy."
                ),
            })
    return issues, report


# -- Layer 3: All canonical agents reachable via gateway ------------------

def check_canonical_coverage(routes: dict[str, str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    routed_fns = set(routes.values())
    for fn in EXPECTED_AGENTS:
        present = fn in routed_fns
        report.append({"expected_fn": fn, "routed_via_gateway": present})
        if present:
            continue
        if fn in GATEWAY_EXEMPT and not GATEWAY_EXEMPT[fn].startswith("(not exempt"):
            continue
        issues.append({
            "check": "canonical_coverage", "skip": True,
            "reason": (
                f"Specialist agent '{fn}' is not reachable via the "
                f"gateway. Frontend has to invoke it directly, missing "
                f"centralised PII / memory / rate gate. Add to "
                f"AGENT_ROUTES or list in GATEWAY_EXEMPT with a reason."
            ),
        })
    return issues, report


# -- Layer 4: Routing inventory (informational) ---------------------------

def check_inventory(routes: dict[str, str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for agent, fn in sorted(routes.items()):
        rows.append({
            "agent":   agent,
            "fn":      fn,
            "on_disk": os.path.isfile(os.path.join(FUNCTIONS_DIR, fn, "index.ts")),
        })
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "gateway_present",
    "routes_exist",
    "canonical_coverage",
    "inventory",
]
CHECK_LABELS = {
    "gateway_present":     "L1  ai-gateway file present with parsable AGENT_ROUTES        [FAIL]",
    "routes_exist":        "L2  Every routed fn has source + config.toml entry            [FAIL]",
    "canonical_coverage":  "L3  Every canonical specialist is reachable via gateway       [WARN]",
    "inventory":           "L4  Per-agent routing inventory (informational)               [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAI Gateway Routing (4-layer)"))
    print("=" * 60)

    routes = parse_routes()
    print(f"  {len(routes)} agent route(s) parsed from gateway.\n")

    l1_issues, l1_report = check_gateway_present()
    l2_issues, l2_report = check_routes_exist(routes)
    l3_issues, l3_report = check_canonical_coverage(routes)
    l4_issues, l4_report = check_inventory(routes)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('AGENT ROUTING INVENTORY (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            mark = "OK" if r["on_disk"] else "MISSING"
            print(f"  {r['agent']:<24} -> {r['fn']:<32}  {mark}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":          "gateway_routing",
        "total_checks":       total,
        "passed":             n_pass,
        "warned":             n_warn,
        "failed":             n_fail,
        "n_routes":           len(routes),
        "gateway_present":    l1_report,
        "routes_exist":       l2_report,
        "canonical_coverage": l3_report,
        "inventory":          l4_report,
        "issues":             [i for i in all_issues if not i.get("skip")],
        "warnings":           [i for i in all_issues if i.get("skip")],
    }
    with open("gateway_routing_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
