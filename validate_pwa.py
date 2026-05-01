"""
PWA Integrity Validator — WorkHive Platform
============================================
WorkHive is installed as a Progressive Web App by field workers on mobile.
A broken PWA means: no home screen install, no offline shell, browser chrome
that flickers between pages, and lost user data when storage fills up.

  Layer 1 — Manifest validity
    1.  manifest.json completeness    — required fields + valid display + icon sizes

  Layer 2 — Page-level manifest presence
    2.  Manifest link on all pages    — every live page links to /manifest.json

  Layer 3 — Theme consistency
    3.  theme-color meta tag          — all pages match manifest theme_color  [WARN]

  Layer 4 — Storage safety
    4.  Unguarded localStorage        — setItem(JSON.stringify) must be in try/catch

  Layer 5 — App shell integrity
    5.  Service worker offline mode   — sw.js must have a fetch handler for offline  [WARN]
    6.  Install prompt on app pages   — beforeinstallprompt only on index, missed on app pages  [WARN]

  Layer 6 — Cache freshness
    7.  SW cache not stale            — any SHELL_FILE committed after sw.js = stale cache
    8.  Logbook IndexedDB queue       — offline entry queue present

Usage:  python validate_pwa.py
Output: pwa_report.json
"""
import re, json, sys, os, subprocess

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MANIFEST_FILE = "manifest.json"
SW_FILE       = "sw.js"

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
    "community.html",
    "marketplace.html",
    "marketplace-admin.html",
    "marketplace-seller.html",
    "public-feed.html",
]

APP_PAGES = [p for p in LIVE_PAGES if p != "index.html"]

REQUIRED_MANIFEST_FIELDS = [
    "name", "short_name", "start_url", "display",
    "background_color", "theme_color", "icons",
]

VALID_DISPLAY_VALUES = {"standalone", "fullscreen", "minimal-ui"}
REQUIRED_ICON_SIZES  = {"192x192", "512x512"}


# ── Layer 1: Manifest validity ────────────────────────────────────────────────

def check_manifest_completeness(path):
    content = read_file(path)
    if content is None:
        return [{"check": "manifest_completeness", "page": path,
                 "reason": "manifest.json not found — PWA install impossible"}]
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError as e:
        return [{"check": "manifest_completeness", "page": path,
                 "reason": f"manifest.json is invalid JSON: {e}"}]

    issues = []
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            issues.append({"check": "manifest_completeness", "page": path,
                           "reason": f"manifest.json missing required field '{field}'"})

    display = manifest.get("display", "")
    if display and display not in VALID_DISPLAY_VALUES:
        issues.append({"check": "manifest_completeness", "page": path,
                       "reason": (f"manifest.json display='{display}' is not installable — "
                                  f"must be one of: {', '.join(sorted(VALID_DISPLAY_VALUES))}")})

    icons = manifest.get("icons", [])
    declared_sizes = {s for icon in icons for s in icon.get("sizes", "").split()}
    for size in REQUIRED_ICON_SIZES:
        if size not in declared_sizes:
            issues.append({"check": "manifest_completeness", "page": path,
                           "reason": (f"manifest.json missing {size} icon — "
                                      f"Android requires 192px; splash screen requires 512px")})
    return issues


# ── Layer 2: Manifest link on all pages ───────────────────────────────────────

def check_manifest_link(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(r'<link[^>]+rel=["\']manifest["\']', content, re.IGNORECASE):
            issues.append({"check": "manifest_link", "page": page,
                           "reason": (f"{page} missing <link rel=\"manifest\" href=\"/manifest.json\"> "
                                      f"— workers on this page cannot install WorkHive to their home screen")})
    return issues


# ── Layer 3: Theme-color consistency (WARN) ───────────────────────────────────

def check_theme_color(pages, manifest_theme_color):
    """
    Every live page should have <meta name="theme-color"> matching the manifest
    theme_color. Mismatch causes address bar flicker when navigating on Android
    Chrome, breaking the native-app illusion on installed PWAs.
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
            issues.append({"check": "theme_color", "page": page, "skip": True,
                           "reason": (f"{page} missing <meta name=\"theme-color\" content=\"{manifest_theme_color}\"> "
                                      f"— browser chrome reverts to default colour (breaks native-app appearance on mobile)")})
        else:
            page_color = (m.group(1) or m.group(2) or "").strip().upper()
            if manifest_theme_color and page_color != manifest_theme_color.upper():
                issues.append({"check": "theme_color", "page": page, "skip": True,
                               "reason": (f"{page} theme-color is '{page_color}' but manifest says "
                                          f"'{manifest_theme_color}' — colour mismatch causes visible flicker "
                                          f"when navigating between pages on mobile")})
    return issues


# ── Layer 4: Storage safety ───────────────────────────────────────────────────

def check_localstorage_quota(pages):
    """
    localStorage.setItem(JSON.stringify(...)) must be wrapped in try/catch.
    iOS Safari enforces a hard 5 MB quota and throws QuotaExceededError.
    Without try/catch the write silently fails — on skillmatrix.html this
    means a worker loses their in-progress exam draft with no warning.
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
            window_before = "\n".join(lines[max(0, i - 3):i + 1])
            if not re.search(r"\btry\s*\{", window_before):
                issues.append({"check": "localstorage_quota", "page": page, "line": i + 1,
                               "reason": (f"{page}:{i + 1} unguarded localStorage.setItem(JSON.stringify(...)) "
                                          f"— QuotaExceededError on iOS Safari silently discards this write: "
                                          f"`{line.strip()[:60]}`")})
    return issues


# ── Layer 5: App shell integrity ──────────────────────────────────────────────

def check_sw_offline_capability(sw_path):
    """
    sw.js must have a fetch event handler to serve cached responses when offline.
    A service worker that only unregisters itself provides no offline capability —
    workers lose access to the app entirely when network drops on the factory floor.
    The current sw.js is a cleanup worker (unregisters itself) with no fetch handler.
    """
    content = read_file(sw_path)
    if content is None:
        return [{"check": "sw_offline_capability", "page": sw_path, "skip": True,
                 "reason": "sw.js not found — no service worker, no offline support"}]

    has_fetch   = re.search(r"addEventListener\s*\(\s*['\"]fetch['\"]", content) is not None
    has_unreg   = "unregister" in content
    has_install = re.search(r"addEventListener\s*\(\s*['\"]install['\"]", content) is not None

    if has_install and has_unreg and not has_fetch:
        return [{"check": "sw_offline_capability", "page": sw_path, "skip": True,
                 "reason": ("sw.js is a cleanup/unregister worker (no fetch handler) — WorkHive has no offline "
                            "cache strategy. Workers lose app access when network drops on the factory floor. "
                            "Add a fetch handler with a cache-first strategy to serve the app shell offline.")}]
    if not has_fetch:
        return [{"check": "sw_offline_capability", "page": sw_path, "skip": True,
                 "reason": "sw.js has no fetch event handler — no offline fallback when network drops"}]
    return []


def check_sw_cache_staleness(sw_path):
    """
    Any file listed in sw.js SHELL_FILES that was committed more recently than
    sw.js itself will be served from the stale cache — users never see the update.

    Root cause of April 2026 incident: nav-hub.js was updated with the Community
    link in commit baa4bcc, but sw.js CACHE_NAME was last bumped in 7295fc8
    (an earlier commit). The service worker kept serving the old nav-hub.js
    without Community to all installed PWA users until a hard refresh.

    This check uses git commit timestamps so it catches the gap automatically:
    if any SHELL_FILE commit timestamp > sw.js commit timestamp → FAIL.
    """
    sw_content = read_file(sw_path)
    if not sw_content:
        return []

    # Parse SHELL_FILES from sw.js dynamically — stays in sync with actual config
    shell_match = re.search(r"SHELL_FILES\s*=\s*\[([^\]]+)\]", sw_content, re.DOTALL)
    if not shell_match:
        return []
    shell_files = [
        f.lstrip("/")
        for f in re.findall(r"['\"]([^'\"]+)['\"]", shell_match.group(1))
    ]

    def git_commit_time(path):
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", "--", path],
                capture_output=True, text=True, timeout=5
            )
            ts = result.stdout.strip()
            return int(ts) if ts else 0
        except Exception:
            return 0

    sw_time = git_commit_time(sw_path)
    if sw_time == 0:
        return []  # not in a git repo or file not tracked — skip

    issues = []
    for f in shell_files:
        file_time = git_commit_time(f)
        if file_time > sw_time:
            issues.append({
                "check": "sw_cache_staleness",
                "reason": (
                    f"'{f}' was committed more recently than sw.js — "
                    f"service worker serves the stale cached version to all PWA users; "
                    f"bump CACHE_NAME in sw.js (e.g. v4→v5) whenever any SHELL_FILE changes"
                )
            })
    return issues


def check_logbook_offline_queue():
    """
    logbook.html must have an IndexedDB offline entry queue so field workers in
    dead zones can log jobs and have them auto-sync on reconnect. This is the
    correct PWA offline pattern for data entry (as opposed to a Service Worker
    cache which only covers static assets).
    """
    content = read_file("logbook.html")
    if not content:
        return [{"check": "logbook_offline_queue", "page": "logbook.html",
                 "reason": "logbook.html not found"}]
    tokens = {
        "indexedDB.open(":                "IndexedDB not opened — no persistent offline store",
        "queueEntryOffline":              "queueEntryOffline() missing — no way to save entry offline",
        "syncOfflineQueue":               "syncOfflineQueue() missing — queue never drains on reconnect",
        "window.addEventListener('online'": "online event listener missing — sync never triggered",
    }
    missing = [reason for token, reason in tokens.items() if token not in content]
    if missing:
        return [{"check": "logbook_offline_queue", "page": "logbook.html",
                 "reason": "Logbook offline queue incomplete — " + "; ".join(missing)}]
    return []


def check_install_prompt_scope(pages):
    """
    beforeinstallprompt must be captured on app pages, not just the landing page.
    If a worker's first interaction is opening hive.html directly (e.g., from a
    bookmark), they never see the install prompt because it was only captured on
    index.html. Either handle beforeinstallprompt in a shared JS (nav-hub.js,
    utils.js) or on every app page.
    """
    shared_js_files = ["nav-hub.js", "utils.js", "floating-ai.js"]
    for js_file in shared_js_files:
        content = read_file(js_file)
        if content and "beforeinstallprompt" in content:
            return []

    pages_with_prompt = []
    for page in pages:
        content = read_file(page)
        if content and "beforeinstallprompt" in content:
            pages_with_prompt.append(page)

    if not pages_with_prompt:
        return [{"check": "install_prompt_scope", "page": "all pages", "skip": True,
                 "reason": "beforeinstallprompt not found on any page or shared JS — workers cannot install WorkHive from any entry point"}]

    missing = [p for p in pages if p not in pages_with_prompt]
    app_pages_missing = [p for p in missing if p != "index.html"]
    if app_pages_missing:
        return [{"check": "install_prompt_scope", "page": ", ".join(app_pages_missing[:3]) + ("..." if len(app_pages_missing) > 3 else ""), "skip": True,
                 "reason": (f"beforeinstallprompt only captured on {pages_with_prompt} — "
                            f"workers entering through app pages miss the install prompt. "
                            f"Move the handler to a shared JS file (nav-hub.js or utils.js).")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "manifest_completeness",
    "manifest_link",
    "theme_color",
    "localstorage_quota",
    "sw_offline_capability",
    "install_prompt_scope",
    "sw_cache_staleness",
    "logbook_offline_queue",
]

CHECK_LABELS = {
    "manifest_completeness":  "L1  manifest.json has required fields + valid display + icon sizes",
    "manifest_link":          "L2  All live pages link to /manifest.json",
    "theme_color":            "L3  All pages have matching theme-color meta tag  [WARN]",
    "localstorage_quota":     "L4  localStorage.setItem(JSON.stringify) wrapped in try/catch",
    "sw_offline_capability":  "L5  sw.js has fetch handler for offline mode  [WARN]",
    "install_prompt_scope":   "L5  beforeinstallprompt captured on app pages or shared JS  [WARN]",
    "sw_cache_staleness":     "L6  SHELL_FILES not committed after sw.js (cache is fresh)",
    "logbook_offline_queue":  "L6  Logbook has IndexedDB offline entry queue",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPWA Integrity Validator (6-layer)"))
    print("=" * 55)

    manifest_theme_color = ""
    manifest_raw = read_file(MANIFEST_FILE)
    if manifest_raw:
        try:
            manifest_theme_color = json.loads(manifest_raw).get("theme_color", "")
        except Exception:
            pass

    all_issues = []
    all_issues += check_manifest_completeness(MANIFEST_FILE)
    all_issues += check_manifest_link(LIVE_PAGES)
    all_issues += check_theme_color(LIVE_PAGES, manifest_theme_color)
    all_issues += check_localstorage_quota(LIVE_PAGES)
    all_issues += check_sw_offline_capability(SW_FILE)
    all_issues += check_install_prompt_scope(LIVE_PAGES)
    all_issues += check_sw_cache_staleness(SW_FILE)
    all_issues += check_logbook_offline_queue()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "pwa",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("pwa_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
