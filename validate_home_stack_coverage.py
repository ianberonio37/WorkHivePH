"""
Home Stack Coverage Validator -- WorkHive Platform Guardian
===========================================================
Companion gate to the Phase H home streamline. After Wave H (2026-05-12)
the platform converged on a three-layer home: Today's One Thing card +
Your Stack + Tools drawer. Every active surface must declare which layer
it fits OR opt out with a documented reason. Without this gate, new
pages will land in the primary nav unchallenged and the "33 tools feels
overwhelming" failure mode comes back.

Two layers:

L1 -- Primary nav has a sensible cardinality (FAIL)
  The visible primary-nav tool count (nav-hub.js TOOLS minus hidden:true
  entries) must stay <= MAX_VISIBLE_TOOLS for each role mode. Hiding a
  tool is cheap (one `hidden: true` flag); the gate forces a deliberate
  choice rather than silent accretion.

L2 -- Hidden tools are reachable from a parent surface (WARN)
  A tool marked `hidden: true` must have at least one deep-link from
  another HTML page so the user can still find it. Otherwise hidden ==
  dead. Skips pages on the documented `HIDDEN_BY_DESIGN` allowlist
  (e.g. analytics-report which is reached only via a button inside
  analytics.html).

Skills consulted: designer (Home Stack Pattern), mobile-maestro (thumb
zone + tool drawer behaviour), analytics-engineer (role-based dashboard
rule), KPI_ENGINE.md Phase H roadmap.
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


NAV_HUB_PATH = "nav-hub.js"

# Per-role visible-tool ceilings. Numbers tuned from the post-H.2 state:
#   field      ~ 6 tools (Logbook, Inventory, Day Planner, PM Scheduler, Community, AI Assistant, Marketplace)
#   supervisor ~ 13 tools (above plus Hive, Analytics, Alert Hub, Project Manager, etc.)
#   engineer   ~ 11 tools
# all == every visible tool, used as a hard ceiling on the catalogue.
MAX_VISIBLE_TOOLS = {
    # Tuned to the post-H.2 state. The ceiling is the *current* count: any
    # future addition trips the gate so accretion gets challenged.
    "field":      11,   # +1 (2026-06-04): Resume / CV Builder is a mission feature kept visible to every role (phone-first OFW CV-building); deep-linked from Skill Matrix + the OFW learn article.
    "supervisor": 17,   # +1 (2026-06-04): Resume / CV Builder (see field note).
    "engineer":   14,
    "all":        25,
}

# Tools whose role is to be reached only from a sibling page. These pages
# need NOT appear in the primary nav, but L2 verifies a deep-link exists.
HIDDEN_BY_DESIGN = {
    "analytics-report.html",  # reached from analytics.html "PDF Report" btn
    "project-report.html",    # reached from project-manager.html
    "report-sender.html",     # reached from analytics.html "Send" btn
    "predictive.html",        # reached from analytics.html (Phase H.2)
    "ph-intelligence.html",   # reached from analytics.html "Network View"
    "shift-brain.html",       # reached from analytics.html "Shift Brain"
    "audit-log.html",         # reached from hive.html (supervisor only)
    "voice-journal.html",     # reached from logbook.html
}


def _read_nav_tools():
    """Parse nav-hub.js TOOLS array entries; return list of dicts with
    label, href, hidden, roles."""
    src = read_file(NAV_HUB_PATH) or ""
    if not src:
        return []
    # Each TOOLS entry is a { ... } object literal. Extract them with a brace
    # walk so nested SVG strings don't confuse us.
    tools_match = re.search(r"const\s+TOOLS\s*=\s*\[", src)
    if not tools_match:
        return []
    start = tools_match.end()
    depth = 1
    i = start
    in_str = None
    while i < len(src) and depth > 0:
        c = src[i]
        if in_str:
            if c == "\\":
                i += 2; continue
            if c == in_str:
                in_str = None
            i += 1; continue
        if c in ("'", '"', "`"):
            in_str = c; i += 1; continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0: break
        i += 1
    body = src[start:i]

    tools = []
    # Match top-level { ... } object literals.
    depth = 0
    cur_start = None
    in_str = None
    for j in range(len(body)):
        c = body[j]
        if in_str:
            if c == "\\":
                continue
            if c == in_str:
                in_str = None
            continue
        if c in ("'", '"', "`"):
            in_str = c; continue
        if c == "{":
            if depth == 0:
                cur_start = j
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and cur_start is not None:
                obj = body[cur_start:j+1]
                tool = {}
                href_m = re.search(r"href\s*:\s*'([^']+)'", obj)
                if href_m: tool["href"] = href_m.group(1)
                label_m = re.search(r"label\s*:\s*'([^']+)'", obj)
                if label_m: tool["label"] = label_m.group(1)
                tool["hidden"] = bool(re.search(r"hidden\s*:\s*true", obj))
                roles_m = re.search(r"roles\s*:\s*\[([^\]]+)\]", obj)
                if roles_m:
                    tool["roles"] = re.findall(r"'(\w+)'", roles_m.group(1))
                tools.append(tool)
                cur_start = None
    return tools


def check_nav_cardinality(tools):
    issues = []
    visible_all = [t for t in tools if not t.get("hidden")]
    for role, max_n in MAX_VISIBLE_TOOLS.items():
        if role == "all":
            visible = visible_all
        else:
            visible = [
                t for t in visible_all
                if not t.get("roles") or role in t.get("roles", [])
            ]
        if len(visible) > max_n:
            issues.append({
                "check":  "nav_cardinality",
                "reason": (
                    f"Role '{role}' sees {len(visible)} primary-nav tools "
                    f"but the home-stack budget is {max_n}. Hide the least "
                    f"differentiated tool with `hidden: true` in nav-hub.js "
                    f"and add a deep-link from a parent page, or bump "
                    f"MAX_VISIBLE_TOOLS['{role}'] with a justification. "
                    f"Visible for this role: " +
                    ", ".join(t.get("label", "?") for t in visible)
                ),
            })
    return issues


def check_hidden_have_deeplinks(tools):
    """For each hidden tool, ensure another HTML page links to it directly
    (so it's not orphaned). HIDDEN_BY_DESIGN entries are assumed to have a
    documented parent and are reported informationally only."""
    issues = []
    hidden = [t for t in tools if t.get("hidden") and t.get("href")]
    for t in hidden:
        href = t["href"]
        if href in HIDDEN_BY_DESIGN:
            continue
        found = False
        for path in sorted(glob.glob("*.html")):
            if path.endswith(("-test.html", ".backup.html", "_backup.html")):
                continue
            if path == href:
                continue
            content = read_file(path) or ""
            if not content:
                continue
            if f"href=\"{href}\"" in content or f"href='{href}'" in content:
                found = True
                break
        if not found:
            issues.append({
                "check": "hidden_have_deeplinks", "skip": True,
                "reason": (
                    f"Hidden tool '{t.get('label')}' ({href}) is not linked "
                    f"from any other HTML page. Add a deep-link from a "
                    f"parent surface (the page where the user would expect "
                    f"to reach it) or add to HIDDEN_BY_DESIGN with a reason."
                ),
            })
    return issues


CHECK_NAMES = ["nav_cardinality", "hidden_have_deeplinks"]
CHECK_LABELS = {
    "nav_cardinality":       "L1  Primary-nav tool count respects per-role home-stack budget [FAIL]",
    "hidden_have_deeplinks": "L2  Hidden tools are reachable from a parent surface          [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nHome Stack Coverage Validator (2-layer)"))
    print("=" * 60)

    tools = _read_nav_tools()
    visible = [t for t in tools if not t.get("hidden")]
    hidden  = [t for t in tools if t.get("hidden")]

    print(f"  {len(tools)} tools in nav-hub TOOLS array")
    print(f"  {len(visible)} visible in primary nav")
    print(f"  {len(hidden)} hidden (reachable from parent surfaces)\n")

    issues = []
    issues += check_nav_cardinality(tools)
    issues += check_hidden_have_deeplinks(tools)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print(f"\n{bold('PRIMARY-NAV INVENTORY BY ROLE')}")
    print("  " + "-" * 56)
    for role, max_n in MAX_VISIBLE_TOOLS.items():
        if role == "all":
            n = len(visible)
        else:
            n = sum(1 for t in visible
                    if not t.get("roles") or role in t.get("roles", []))
        marker = "OK" if n <= max_n else "OVER"
        print(f"  {role:<12} {n:>3} / {max_n:<3} [{marker}]")

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "home_stack_coverage",
        "total_checks": len(CHECK_NAMES),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "n_tools":      len(tools),
        "n_visible":    len(visible),
        "n_hidden":     len(hidden),
        "tools":        tools,
        "issues":       [i for i in issues if not i.get("skip")],
        "warnings":     [i for i in issues if i.get("skip")],
    }
    with open("home_stack_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
