"""
Nav Hub Registry Validator — WorkHive Platform
================================================
As WorkHive grows, new tools get added. Every new tool page must be
registered correctly in nav-hub.js. A page built but not registered
is invisible to workers. A misconfigured entry causes dead links,
blank tiles, or wrong active-state highlighting.

  Layer 1 — File integrity
    1.  All TOOLS hrefs exist      — every href resolves to a real file on disk
    2.  Retired pages not active   — parts-tracker / checklist not in TOOLS

  Layer 2 — TOOLS entry completeness
    3.  Every tool has a match[]   — getCurrentTool() needs match to highlight active page
    4.  Every tool has an icon     — missing icon = blank tile in production
    5.  No duplicate hrefs         — two tools pointing to same page = double nav entry

  Layer 3 — Runtime correctness
    6.  match[] values are unique  — two tools sharing a match value = wrong active highlight
    7.  All TOOLS pages use 3-key identity chain — wh_last_worker || wh_worker_name || workerName

  Layer 4 — Widget availability
    8.  All TOOLS pages load nav-hub.js — missing it = no navigation + no AI widget

Usage:  python validate_nav_registry.py
Output: nav_registry_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

NAV_HUB_JS    = "nav-hub.js"
RETIRED_PAGES = {"parts-tracker.html", "checklist.html"}
IDENTITY_KEYS = ["wh_last_worker", "wh_worker_name", "workerName"]
IDENTITY_EXEMPT = {"index.html"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_tools(nav_content):
    """Parse the TOOLS array from nav-hub.js into a list of dicts."""
    tools = []
    m = re.search(r"const TOOLS\s*=\s*\[([\s\S]+?)\];", nav_content)
    if not m:
        return tools
    block = m.group(1)
    for obj_m in re.finditer(r"\{([^{}]+)\}", block, re.DOTALL):
        obj = obj_m.group(1)
        label_m = re.search(r"label:\s*['\"]([^'\"]+)['\"]", obj)
        href_m  = re.search(r"href:\s*['\"]([^'\"]+)['\"]", obj)
        # match: ['...', '...']
        match_m = re.search(r"match:\s*\[([^\]]+)\]", obj)
        # icon: `...` or icon: '...' or icon: "..."
        has_icon = bool(re.search(r"\bicon\s*:", obj))
        if label_m and href_m:
            match_vals = re.findall(r"['\"]([^'\"]+)['\"]", match_m.group(1)) if match_m else []
            tools.append({
                "href":       href_m.group(1),
                "label":      label_m.group(1),
                "match":      match_vals,
                "has_match":  bool(match_m),
                "has_icon":   has_icon,
            })
    return tools


# ── Layer 1: File integrity ───────────────────────────────────────────────────

def check_files_exist(tools):
    return [{"check": "files_exist", "page": NAV_HUB_JS, "href": t["href"],
             "reason": f"nav-hub.js TOOLS references '{t['href']}' ('{t['label']}') but the file does not exist — workers get a 404"}
            for t in tools if not os.path.exists(t["href"])]


def check_retired_not_active(tools):
    return [{"check": "retired_not_active", "page": NAV_HUB_JS, "href": t["href"],
             "reason": f"Retired page '{t['href']}' ('{t['label']}') is still in TOOLS — workers navigate to a dead or outdated page"}
            for t in tools if t["href"] in RETIRED_PAGES]


# ── Layer 2: TOOLS entry completeness ────────────────────────────────────────

def check_match_arrays_present(tools):
    """
    Every tool needs a match[] array so getCurrentTool() can highlight the
    active page. Without it, the tool tile never shows as active/current —
    workers have no visual cue about where they are in the platform.
    """
    return [{"check": "match_arrays_present", "page": NAV_HUB_JS, "href": t["href"],
             "reason": f"'{t['label']}' ({t['href']}) has no match[] array — getCurrentTool() will never identify this as the active page"}
            for t in tools if not t["has_match"]]


def check_icons_present(tools):
    """
    Every tool must have an icon field. A missing icon renders as a blank
    space in the nav grid — visually broken and confusing on small screens.
    """
    return [{"check": "icons_present", "page": NAV_HUB_JS, "href": t["href"],
             "reason": f"'{t['label']}' ({t['href']}) has no icon — nav tile renders blank in the tool grid"}
            for t in tools if not t["has_icon"]]


def check_no_duplicate_hrefs(tools):
    """Two tools with the same href appear as duplicate entries in the nav grid."""
    seen  = {}
    issues = []
    for t in tools:
        if t["href"] in seen:
            issues.append({"check": "no_duplicate_hrefs", "page": NAV_HUB_JS, "href": t["href"],
                           "reason": f"href '{t['href']}' appears twice in TOOLS ('{seen[t['href']]}' and '{t['label']}') — duplicate nav tile"})
        else:
            seen[t["href"]] = t["label"]
    return issues


# ── Layer 3: Runtime correctness ─────────────────────────────────────────────

def check_match_values_unique(tools):
    """
    If two tools share a match[] value (e.g., both match 'hive'),
    getCurrentTool() always returns the first one — the second tool tile
    never highlights as active, no matter which page the worker is on.
    """
    seen   = {}
    issues = []
    for t in tools:
        for val in t["match"]:
            if val in seen:
                issues.append({"check": "match_values_unique", "page": NAV_HUB_JS,
                               "match_value": val,
                               "reason": f"match value '{val}' used by both '{seen[val]}' and '{t['label']}' — getCurrentTool() always returns the first match, second tool never shows as active"})
            else:
                seen[val] = t["label"]
    return issues


def check_identity_keys(tools):
    issues = []
    for t in tools:
        if t["href"] in IDENTITY_EXEMPT:
            continue
        content = read_file(t["href"])
        if not content:
            continue
        for key in IDENTITY_KEYS:
            if key not in content:
                issues.append({"check": "identity_keys", "page": t["href"], "key": key,
                               "reason": f"{t['href']} ('{t['label']}') missing identity key '{key}' — workers who set only this key are treated as anonymous"})
    return issues


# ── Layer 4: Widget availability ─────────────────────────────────────────────

def check_nav_hub_loaded(tools):
    issues = []
    for t in tools:
        content = read_file(t["href"])
        if not content:
            continue
        if 'src="nav-hub.js"' not in content and "src='nav-hub.js'" not in content:
            issues.append({"check": "nav_hub_loaded", "page": t["href"],
                           "reason": f"{t['href']} ('{t['label']}') is in TOOLS but does not load nav-hub.js — workers have no navigation widget and no AI assistant"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "files_exist", "retired_not_active",
    # L2
    "match_arrays_present", "icons_present", "no_duplicate_hrefs",
    # L3
    "match_values_unique", "identity_keys",
    # L4
    "nav_hub_loaded",
]

CHECK_LABELS = {
    # L1
    "files_exist":          "L1  All TOOLS hrefs point to existing files",
    "retired_not_active":   "L1  Retired pages not listed as active tools",
    # L2
    "match_arrays_present": "L2  Every tool has a match[] array",
    "icons_present":        "L2  Every tool has an icon",
    "no_duplicate_hrefs":   "L2  No duplicate hrefs in TOOLS",
    # L3
    "match_values_unique":  "L3  match[] values are unique across all tools",
    "identity_keys":        "L3  All TOOLS pages use 3-key identity chain",
    # L4
    "nav_hub_loaded":       "L4  All TOOLS pages load nav-hub.js",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nNav Hub Registry Validator (4-layer)"))
    print("=" * 55)

    nav_content = read_file(NAV_HUB_JS)
    if not nav_content:
        print(f"  ERROR: {NAV_HUB_JS} not found")
        sys.exit(1)

    tools = extract_tools(nav_content)
    print(f"  {len(tools)} tools in TOOLS array: {', '.join(t['label'] for t in tools)}\n")

    all_issues = []

    # L1
    all_issues += check_files_exist(tools)
    all_issues += check_retired_not_active(tools)

    # L2
    all_issues += check_match_arrays_present(tools)
    all_issues += check_icons_present(tools)
    all_issues += check_no_duplicate_hrefs(tools)

    # L3
    all_issues += check_match_values_unique(tools)
    all_issues += check_identity_keys(tools)

    # L4
    all_issues += check_nav_hub_loaded(tools)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "nav_registry",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "tools_found":  len(tools),
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("nav_registry_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
