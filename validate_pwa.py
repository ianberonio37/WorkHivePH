"""
PWA Integrity Validator — WorkHive Platform
============================================
WorkHive is installed as a Progressive Web App by field workers on mobile.
A broken PWA means: no home screen install, no offline shell, browser chrome
that flickers between pages, and lost user data when storage fills up.

Four things checked:

  1. manifest.json completeness  — required fields must all be present and
                                   valid: name, short_name, start_url, display,
                                   background_color, theme_color, and icons with
                                   both 192px and 512px entries.

  2. Manifest link on all pages  — every live page must have
                                   <link rel="manifest" href="/manifest.json">
                                   in its <head>. Missing it means workers on
                                   that page cannot install WorkHive to their
                                   home screen from that entry point.

  3. theme-color meta tag        — every live page must have
                                   <meta name="theme-color" content="...">
                                   matching the manifest theme_color value.
                                   Missing or mismatched = browser chrome flickers
                                   between colors as the worker navigates pages
                                   (destroys the native-app illusion on mobile).
                                   Reported as WARN.

  4. Unguarded localStorage      — localStorage.setItem(JSON.stringify(...)) calls
                                   with no try/catch risk a silent crash on iOS
                                   Safari when the 5 MB storage quota is hit.
                                   The exam draft saves in skillmatrix.html are
                                   the highest-risk case (workers lose exam progress).

Usage:  python validate_pwa.py
Output: pwa_report.json
"""
import re, json, sys, os

MANIFEST_FILE = "manifest.json"

LIVE_PAGES = [
    "index.html",
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "nav-hub.html",
]

# Required top-level fields in manifest.json
REQUIRED_MANIFEST_FIELDS = [
    "name", "short_name", "start_url", "display",
    "background_color", "theme_color", "icons",
]

# display values that qualify as installable
VALID_DISPLAY_VALUES = {"standalone", "fullscreen", "minimal-ui"}

# Required icon sizes
REQUIRED_ICON_SIZES = {"192x192", "512x512"}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: manifest.json completeness ──────────────────────────────────────

def check_manifest(path):
    """
    Validates that manifest.json has all required fields with valid values.
    A missing or misconfigured manifest breaks the PWA install prompt entirely.
    """
    issues = []
    content = read_file(path)
    if content is None:
        return [{"page": path, "reason": "manifest.json not found — PWA install impossible"}]

    try:
        manifest = json.loads(content)
    except json.JSONDecodeError as e:
        return [{"page": path, "reason": f"manifest.json is invalid JSON: {e}"}]

    # Check required top-level fields
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            issues.append({
                "page":   path,
                "field":  field,
                "reason": f"manifest.json missing required field '{field}'",
            })

    # Check display value is installable
    display = manifest.get("display", "")
    if display and display not in VALID_DISPLAY_VALUES:
        issues.append({
            "page":   path,
            "field":  "display",
            "reason": (
                f"manifest.json display='{display}' is not installable — "
                f"must be one of: {', '.join(sorted(VALID_DISPLAY_VALUES))}"
            ),
        })

    # Check icons include both required sizes
    icons = manifest.get("icons", [])
    declared_sizes = set()
    for icon in icons:
        for size in icon.get("sizes", "").split():
            declared_sizes.add(size)
    for required_size in REQUIRED_ICON_SIZES:
        if required_size not in declared_sizes:
            issues.append({
                "page":   path,
                "field":  "icons",
                "reason": (
                    f"manifest.json missing {required_size} icon — "
                    f"Android requires 192px; splash screen requires 512px"
                ),
            })

    return issues


# ── Check 2: Manifest link present on all live pages ─────────────────────────

def check_manifest_link(pages):
    """
    Every live page must link to the manifest in its <head>.
    Without this, a worker arriving on that page cannot trigger the
    PWA install prompt — the browser doesn't even know it's a PWA.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(r'<link[^>]+rel=["\']manifest["\']', content, re.IGNORECASE):
            issues.append({
                "page": page,
                "reason": (
                    f"{page} is missing <link rel=\"manifest\" href=\"/manifest.json\"> "
                    f"— workers on this page cannot install WorkHive to their home screen"
                ),
            })
    return issues


# ── Check 3: theme-color meta tag on all live pages (WARN) ───────────────────

def check_theme_color(pages, manifest_theme_color):
    """
    Every live page should have <meta name="theme-color" content="..."> matching
    the manifest theme_color. Without it, the browser's address bar and system UI
    revert to the default colour when the worker navigates to that page, breaking
    the native-app feel on Android Chrome and iOS Safari.
    Reported as WARN — functional but degrades the installed app experience.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        m = re.search(
            r'<meta[^>]+name=["\']theme-color["\'][^>]*content=["\']([^"\']+)["\']'
            r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']theme-color["\']',
            content, re.IGNORECASE
        )
        if not m:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} missing <meta name=\"theme-color\" content=\"{manifest_theme_color}\"> "
                    f"— browser chrome reverts to default colour on this page "
                    f"(breaks native-app appearance on mobile)"
                ),
            })
        else:
            page_color = (m.group(1) or m.group(2) or "").strip().upper()
            if manifest_theme_color and page_color != manifest_theme_color.upper():
                issues.append({
                    "page": page,
                    "reason": (
                        f"{page} theme-color is '{page_color}' but manifest says "
                        f"'{manifest_theme_color}' — colour mismatch causes visible "
                        f"flicker when navigating between pages on mobile"
                    ),
                })
    return issues


# ── Check 4: Unguarded localStorage quota writes ─────────────────────────────

def check_localstorage_quota(pages):
    """
    localStorage.setItem(JSON.stringify(...)) calls must be wrapped in try/catch.
    iOS Safari (and some Android browsers) enforce a hard 5 MB quota and throw
    a QuotaExceededError when it's hit. Without try/catch, the error is unhandled:
    - The current operation silently fails
    - No feedback to the worker
    - On skillmatrix.html: the worker loses their in-progress exam draft

    Safe pattern:
      try { localStorage.setItem(key, JSON.stringify(val)); } catch (_) {}

    Unsafe pattern:
      localStorage.setItem(key, JSON.stringify(val));
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            if "localStorage.setItem" not in line or "JSON.stringify" not in line:
                continue
            # Check if try { appears within 3 lines before this line
            window_before = "\n".join(lines[max(0, i - 3):i + 1])
            if not re.search(r"\btry\s*\{", window_before):
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "code": line.strip()[:80],
                    "reason": (
                        f"{page}:{i + 1} — unguarded localStorage.setItem(JSON.stringify(...)) "
                        f"— a QuotaExceededError on iOS Safari silently discards this write "
                        f"with no feedback to the worker: `{line.strip()[:60]}`"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("PWA Integrity Validator")
print("=" * 70)

# Read manifest theme_color for cross-check
manifest_theme_color = ""
manifest_raw = read_file(MANIFEST_FILE)
if manifest_raw:
    try:
        manifest_theme_color = json.loads(manifest_raw).get("theme_color", "")
    except Exception:
        pass

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] manifest.json completeness (required fields + icon sizes)",
        check_manifest(MANIFEST_FILE),
        "FAIL",
    ),
    (
        "[2] Manifest link present on all live pages",
        check_manifest_link(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[3] theme-color meta tag on all live pages",
        check_theme_color(LIVE_PAGES, manifest_theme_color),
        "WARN",
    ),
    (
        "[4] Unguarded localStorage quota writes (try/catch missing)",
        check_localstorage_quota(LIVE_PAGES),
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

with open("pwa_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved pwa_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll PWA checks PASS (warnings may need review).")
