"""
Nav Hub Registry Validator — WorkHive Platform
===============================================
As WorkHive grows, new tools get added. Every new tool page must be
registered in exactly the right places — nav-hub.js (so workers can
find it), and must follow the standard boot pattern (identity key,
nav widget). A page that is built but not registered is invisible.
A page that has the wrong identity key breaks session continuity.

From the Codebase Integrity and Architect skill files.

Four things checked:

  1. All TOOLS files exist on disk
     — Every href in the nav-hub.js TOOLS array must resolve to a real
       file. If a page is renamed or deleted without updating nav-hub.js,
       workers click the nav tile and get a 404 with no explanation.

  2. Retired pages not in TOOLS as active tools
     — parts-tracker.html and checklist.html are retired. They must not
       appear as active hrefs in the TOOLS array. A retired page in the
       nav is a dead link that confuses workers.

  3. All TOOLS pages use the 3-key identity fallback chain
     — Every app page in TOOLS must read the worker identity from all
       three localStorage keys in order:
         wh_last_worker || wh_worker_name || workerName
       Missing any key breaks identity resolution when workers switch
       devices or browsers where only one key was set.

  4. All TOOLS pages load nav-hub.js
     — Every page in TOOLS must include <script src="nav-hub.js"> before
       </body>. nav-hub.js provides both the navigation widget AND the
       floating AI assistant. A page missing it has no navigation and
       no AI help for the worker.

Usage:  python validate_nav_registry.py
Output: nav_registry_report.json
"""
import re, json, sys, os

NAV_HUB_JS = "nav-hub.js"

# Pages that are retired — must not appear as active tool hrefs
RETIRED_PAGES = {"parts-tracker.html", "checklist.html"}

# The 3-key fallback chain from the Codebase Integrity skill
# All 3 must appear in the identity lookup for full cross-device compatibility
IDENTITY_KEYS = ["wh_last_worker", "wh_worker_name", "workerName"]

# Pages that intentionally do NOT need a worker identity
# (landing page and admin/internal tools)
IDENTITY_EXEMPT = {"index.html"}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_tools(nav_content):
    """
    Parse the TOOLS array from nav-hub.js.
    Returns list of dicts with 'label' and 'href'.
    """
    tools = []
    m = re.search(r"const TOOLS\s*=\s*\[([\s\S]+?)\];", nav_content)
    if not m:
        return tools
    block = m.group(1)
    # Each tool object spans between consecutive { ... } blocks
    for obj_m in re.finditer(r"\{([^{}]+)\}", block, re.DOTALL):
        obj = obj_m.group(1)
        label_m = re.search(r"label:\s*['\"]([^'\"]+)['\"]", obj)
        href_m  = re.search(r"href:\s*['\"]([^'\"]+)['\"]", obj)
        if label_m and href_m:
            tools.append({"href": href_m.group(1), "label": label_m.group(1)})
    return tools


# ── Check 1: All TOOLS hrefs resolve to existing files ───────────────────────

def check_files_exist(tools):
    """
    Every href in the TOOLS array must be a file that actually exists.
    A dead link in the navigation is a confusing failure for workers —
    they tap a tile, the browser loads a blank page, and they don't know
    why the tool isn't working.
    """
    issues = []
    for tool in tools:
        href = tool["href"]
        if not os.path.exists(href):
            issues.append({
                "page":  NAV_HUB_JS,
                "href":  href,
                "label": tool["label"],
                "reason": (
                    f"nav-hub.js TOOLS references '{href}' (label: '{tool['label']}') "
                    f"but the file does not exist — workers will get a 404 when "
                    f"tapping this nav tile"
                ),
            })
    return issues


# ── Check 2: Retired pages not in TOOLS as active tools ──────────────────────

def check_retired_not_active(tools):
    """
    Retired pages must not appear as active tool hrefs in the TOOLS array.
    If they do, workers navigate to a page that either 404s or shows
    outdated, unmaintained functionality.
    """
    issues = []
    for tool in tools:
        if tool["href"] in RETIRED_PAGES:
            issues.append({
                "page":   NAV_HUB_JS,
                "href":   tool["href"],
                "label":  tool["label"],
                "reason": (
                    f"Retired page '{tool['href']}' ('{tool['label']}') is "
                    f"still listed as an active tool in nav-hub.js TOOLS — "
                    f"remove it or mark it as retired"
                ),
            })
    return issues


# ── Check 3: All TOOLS pages use the 3-key identity fallback chain ───────────

def check_identity_keys(tools):
    """
    Every app page must read the worker identity from all three localStorage
    keys in the standard fallback order:
      localStorage.getItem('wh_last_worker') ||
      localStorage.getItem('wh_worker_name') ||
      localStorage.getItem('workerName')

    Missing any key breaks identity when a worker's device has only the
    older key set. For example, a worker who signed in before the key was
    renamed would have 'workerName' but not 'wh_last_worker' — missing the
    fallback means the app thinks they're anonymous.
    """
    issues = []
    for tool in tools:
        href = tool["href"]
        if href in IDENTITY_EXEMPT:
            continue
        content = read_file(href)
        if content is None:
            continue

        for key in IDENTITY_KEYS:
            if key not in content:
                issues.append({
                    "page":  href,
                    "key":   key,
                    "label": tool["label"],
                    "reason": (
                        f"{href} ('{tool['label']}') does not reference identity "
                        f"key '{key}' — workers whose session used this key "
                        f"will be treated as anonymous on this page"
                    ),
                })
    return issues


# ── Check 4: All TOOLS pages load nav-hub.js ─────────────────────────────────

def check_nav_hub_loaded(tools):
    """
    Every page in TOOLS must load nav-hub.js before </body>.
    nav-hub.js provides:
    - The navigation hub widget (tile grid, recents, quick access)
    - The floating AI assistant
    - The page context detection for AI responses

    A page missing nav-hub.js means the worker has no navigation
    between tools and no AI assistant — they're stranded on that page.
    """
    issues = []
    for tool in tools:
        href = tool["href"]
        content = read_file(href)
        if content is None:
            continue

        if 'src="nav-hub.js"' not in content and "src='nav-hub.js'" not in content:
            issues.append({
                "page":  href,
                "label": tool["label"],
                "reason": (
                    f"{href} ('{tool['label']}') is in the TOOLS array but does "
                    f"not load nav-hub.js — workers on this page have no navigation "
                    f"widget and no AI assistant"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Nav Hub Registry Validator")
print("=" * 70)

nav_content = read_file(NAV_HUB_JS)
if not nav_content:
    print(f"\n  ERROR: {NAV_HUB_JS} not found")
    sys.exit(1)

tools = extract_tools(nav_content)
print(f"\n  Found {len(tools)} tools in TOOLS array: "
      f"{', '.join(t['label'] for t in tools)}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] All TOOLS hrefs point to existing files",
        check_files_exist(tools),
        "FAIL",
    ),
    (
        "[2] Retired pages not listed as active tools in TOOLS",
        check_retired_not_active(tools),
        "FAIL",
    ),
    (
        "[3] All TOOLS pages use the 3-key identity fallback chain",
        check_identity_keys(tools),
        "FAIL",
    ),
    (
        "[4] All TOOLS pages load nav-hub.js",
        check_nav_hub_loaded(tools),
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

with open("nav_registry_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved nav_registry_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll nav registry checks PASS.")
