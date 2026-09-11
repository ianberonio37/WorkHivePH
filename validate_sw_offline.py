"""
Service Worker Offline Coverage -- WorkHive Platform
======================================================
Catches the offline-blank-page bug: a worker on the factory floor
loses Wi-Fi, opens logbook.html / inventory.html on their PWA, and
the page is empty because the shell isn't cached. Companion to
validate_cache_invalidation -- that gate keeps CACHE_NAME fresh;
this gate ensures the SHELL_FILES list COVERS the pages workers
expect to use offline.

Layer 1 -- Worker-critical pages survive a dropped request               [WARN]
  WORKER_CRITICAL_PAGES (logbook, inventory, pm-scheduler, parts,
  shift-brain, asset-hub, hive) must each be RECOVERABLE when the network
  drops mid-request - by living in SHELL_FILES, by being kept through the
  handler's network-first cache-on-visit for app navigations, or by an
  explicit SW_OFFLINE_OK opt-out with a reason. It asks whether the
  property holds, not which of the three delivers it: precaching a 404KB
  app page bills every user at install and then serves stale HTML until a
  CACHE_NAME bump, so naming it the only acceptable answer would argue
  with a better one.

Layer 2 -- Shell pages have an offline fallback message                  [WARN]
  Every page in SHELL_FILES should reference `navigator.onLine` /
  `online` / `offline` event handlers OR have a `<noscript>` /
  `data-offline` fallback element. Without these, network-down
  flashes blank content before the cached HTML renders.

Layer 3 -- Per-page network-resilience signal (informational)            [INFO]
  Pages that already reference offline/online handlers.

Layer 4 -- Service worker registration coverage (informational)          [INFO]
  Pages that include `navigator.serviceWorker.register` -- shows
  which pages actually wire the sw.js they declare.

Skills consulted: mobile-maestro (PWA semantics on iOS / Android),
performance (offline-first design beats cache-then-network for
factory-floor latency).
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


SW_FILE = "sw.js"
EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

WORKER_CRITICAL_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "parts-tracker.html",
    "shift-brain.html",
    "asset-hub.html",
    "hive.html",
]

SW_OFFLINE_OK: dict[str, str] = {
    # 2026-05-11: SW shell + offline banner BOTH shipped.
    # CACHE_NAME bumped to 'workhive-shell-v29' (offline-banner.js added).
    # All 8 worker-critical pages include offline-banner.js which wires
    # window.addEventListener('offline'|'online'). Closes PRODUCTION_FIXES #54.
}

SHELL_ARRAY_RE = re.compile(
    r"""const\s+SHELL_FILES\s*=\s*\[(?P<body>[\s\S]*?)\];""",
)
SHELL_ENTRY_RE = re.compile(r"""['"`](?P<file>[^'"`]+)['"`]""")
OFFLINE_SIGNAL_RES = [
    re.compile(r"\bnavigator\.onLine\b"),
    re.compile(r"""addEventListener\s*\(\s*['"`](?:offline|online)['"`]"""),
    re.compile(r"""data-offline"""),
    re.compile(r"""<noscript[\s>]"""),
    # Shared offline-banner.js wires window addEventListener('offline'|'online');
    # treat the include as compliance evidence per PRODUCTION_FIXES #54.
    re.compile(r"""<script\s+src=["']offline-banner\.js["']"""),
]


def list_pages() -> list[str]:
    return sorted(p for p in glob.glob("*.html")
                  if not any(x in p.lower() for x in EXCLUDED_HTML_PATTERNS))


def shell_files() -> set[str]:
    src = read_file(SW_FILE) or ""
    m = SHELL_ARRAY_RE.search(src)
    if not m:
        return set()
    out: set[str] = set()
    for em in SHELL_ENTRY_RE.finditer(m.group("body")):
        f = em.group("file").lstrip("/")
        out.add(f)
    return out


def has_offline_signal(src: str) -> bool:
    return any(rx.search(src) for rx in OFFLINE_SIGNAL_RES)


def app_navs_are_cached() -> bool:
    """Does sw.js keep a copy of an app-page NAVIGATION for the bad day?

    ★A THIRD WAY TO BE COVERED, AND THE GATE COULD ONLY SEE TWO (2026-09-10). This check asked one
    question - "is the page in SHELL_FILES?" - and so reported logbook.html uncovered on the day it
    stopped being uncovered. Precaching is not the only way to have a page when the network drops, and
    for a 404KB app page it is the WORST way: it bills every user at install for a page most never
    open, and cache-first then serves yesterday's HTML until a CACHE_NAME bump. The handler now
    answers navigations network-FIRST and stores what was actually visited, which gives the same
    protection with neither cost. A gate that names one acceptable implementation is a gate that
    argues with a better one - so it asks whether the PROPERTY holds, and only then how.
    """
    src = read_file("sw.js") or ""
    return bool(re.search(r"_appNav\s*=", src) and re.search(r"mode\s*===\s*['\"]navigate['\"]", src)
                and re.search(r"caches\.open\(CACHE_NAME\)", src))


def check_critical_in_shell() -> tuple[list[dict], list[dict]]:
    issues, report = [], []
    shell = shell_files()
    nav_cached = app_navs_are_cached()
    for page in WORKER_CRITICAL_PAGES:
        if page in shell:
            continue
        if nav_cached:
            continue        # covered by network-first cache-on-visit; see app_navs_are_cached
        if page in SW_OFFLINE_OK:
            continue
        report.append({"page": page})
        issues.append({
            "check": "critical_in_shell", "skip": True,
            "reason": (
                f"{page} is worker-critical (factory floor, mobile, "
                f"offline-prone) but not in sw.js SHELL_FILES. Add it "
                f"to the SHELL_FILES array OR list in SW_OFFLINE_OK "
                f"with a justification."
            ),
        })
    return issues, report


def check_shell_offline_fallback() -> tuple[list[dict], list[dict]]:
    issues, report = [], []
    shell = shell_files()
    for f in shell:
        if not f.endswith(".html"):
            continue
        path = f
        if not os.path.isfile(path):
            continue
        src = read_file(path) or ""
        if has_offline_signal(src):
            continue
        if f in SW_OFFLINE_OK:
            continue
        report.append({"shell_file": f})
        issues.append({
            "check": "shell_offline_fallback", "skip": True,
            "reason": (
                f"{f} is in SHELL_FILES but contains no offline / online "
                f"event handler or <noscript> fallback. Network-down "
                f"flashes blank content. Add `navigator.onLine` check + "
                f"toast or a <noscript> banner."
            ),
        })
    return issues, report


def check_resilience_distribution() -> tuple[list[dict], list[dict]]:
    rows = []
    for page in list_pages():
        src = read_file(page) or ""
        signals = [rx.pattern for rx in OFFLINE_SIGNAL_RES if rx.search(src)]
        if signals:
            rows.append({"page": page, "signals": signals})
    return [], rows


def check_sw_register_coverage() -> tuple[list[dict], list[dict]]:
    """Which pages end up with the worker registered - INCLUDING via a script they load.

    ★THIS COUNTED THE CALL AND NOT THE COVERAGE, AND THE UNDERCOUNT READS AS A CATASTROPHE
    (2026-09-10). It scanned page HTML for `navigator.serviceWorker.register` and found TWO -
    report-sender.html and marketplace-seller.html - so anyone reading this line concluded that the
    precache, the offline fallback and the network-first navigation copy reached almost nobody. That
    is false, and it cost this session a real detour: `nav-hub.js:1946` registers the worker, with a
    DERIVED root, and 31 pages load nav-hub. The registration hole this check was built to watch was
    already closed by moving the call into shared chrome - which is exactly the fix that made a
    page-only scan blind to it. A check that looks for a call in one file can never see a platform
    that shares its chrome, so this one now follows the <script src> edges too.
    """
    rows = []
    register_re = re.compile(r"navigator\s*\.\s*serviceWorker\s*\.\s*register")
    script_re = re.compile(r"""<script[^>]+src=["'](?!https?:)([^"']+)["']""", re.I)
    registering_scripts = {
        js for js in glob.glob("*.js") if register_re.search(read_file(js) or "")
    }
    for page in list_pages():
        src = read_file(page) or ""
        if register_re.search(src):
            rows.append({"page": page, "via": "its own markup"})
            continue
        for m in script_re.finditer(src):
            js = m.group(1).lstrip("./")
            if js in registering_scripts:
                rows.append({"page": page, "via": js})
                break
    return [], rows


# a script this many pages load is shared chrome, not a page's own helper
WIDELY_LOADED = 10


def check_shared_scripts_recoverable() -> tuple[list[dict], list[dict]]:
    """A script most pages depend on should still be there when one request is lost.

    ★THE PRECACHE LIST INVERTED ITS OWN PRIORITY, MEASURED RATHER THAN ARGUED (2026-09-10).
    `utils.js` is loaded by 38 pages, is 363KB, and defines `getDb` - every database call on the
    platform goes through it - and it is in NO SHELL_FILES entry. Meanwhile `wh-help.js` (10KB, ONE
    page) and `form-autosave.js` (6KB, three pages) are precached. Lose utils.js to a dropped request
    and the page throws `window.getDb is not a function`, which is exactly what one offline-3g row
    reported. Asking the question as "is it in the list" would be the L1 mistake again, so this asks
    whether the property HOLDS: precached, or kept by a cache-on-visit path, are both fine.

    WARN, never FAIL, and deliberately so - the two honest fixes trade against each other and the
    choice is a design decision, not a lint. Precaching utils.js bills every install 363KB for a file
    many visitors never need; network-first-with-a-kept-copy (what app navigations already do) costs
    nothing up front but keeps only what was actually visited. browser-floor.js re-requesting a dropped
    same-origin script covers the DROPPED case but not the OFFLINE one, so it is not counted here.

    SCRIPTS ONLY, AND THAT SCOPE WAS MEASURED RATHER THAN ASSUMED: the same question asked of
    stylesheets comes back clean - tokens.css (31 pages) and components.css (14) are both precached,
    and the only uncovered sheet is wh-tw.css at 9 pages, under the threshold. The inversion was
    specific to scripts, so widening this check today would add a lens that finds nothing. If a
    stylesheet ever crosses the threshold uncovered, the fix is to widen the selector below, not to
    conclude it was never considered.
    """
    issues, report = [], []
    shell = shell_files()
    src_sw = read_file("sw.js") or ""
    # does the handler keep a copy of same-origin SCRIPTS it fetched? (not navigations - L1 asks that)
    scripts_kept = bool(re.search(r"destination\s*===\s*['\"]script['\"]", src_sw))
    script_re = re.compile(r"""<script[^>]+src=["'](?!https?:)([^"']+)["']""", re.I)
    loaded: dict[str, int] = {}
    for page in list_pages():
        for m in script_re.finditer(read_file(page) or ""):
            js = m.group(1).lstrip("./")
            loaded[js] = loaded.get(js, 0) + 1
    for js, n in sorted(loaded.items(), key=lambda kv: -kv[1]):
        if n < WIDELY_LOADED or js in shell or scripts_kept:
            continue
        kb = round(os.path.getsize(js) / 1024) if os.path.isfile(js) else -1
        report.append({"script": js, "pages": n, "kb": kb})
        issues.append({
            "check": "shared_scripts_recoverable", "skip": True,
            "reason": (
                f"{js} is loaded by {n} pages ({kb}KB) and can be served by no route when its "
                f"request is lost: it is not in SHELL_FILES and sw.js keeps no copy of same-origin "
                f"scripts. Either add it to SHELL_FILES (costs every install {kb}KB) or extend the "
                f"fetch handler to keep a copy of same-origin scripts the way it already does for "
                f"app navigations (costs nothing up front, keeps only what was visited)."
            ),
        })
    return issues, report


CHECK_NAMES = [
    "critical_in_shell", "shell_offline_fallback",
    "resilience_distribution", "sw_register_coverage",
    "shared_scripts_recoverable",
]
CHECK_LABELS = {
    "critical_in_shell":       "L1  Worker-critical pages survive a dropped request                  [WARN]",
    "shell_offline_fallback":  "L2  SHELL_FILES pages declare offline fallback                 [WARN]",
    "resilience_distribution": "L3  Per-page online/offline signal use (informational)         [INFO]",
    "sw_register_coverage":    "L4  Pages that end up with sw.js registered (informational)    [INFO]",
    "shared_scripts_recoverable": "L5  Widely-loaded scripts survive a dropped request           [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nService Worker Offline Coverage (4-layer)"))
    print("=" * 60)
    pages = list_pages()
    shell = shell_files()
    print(f"  {len(pages)} pages, {len(shell)} SHELL_FILES entries.\n")
    l1_i, l1_r = check_critical_in_shell()
    l2_i, l2_r = check_shell_offline_fallback()
    l3_i, l3_r = check_resilience_distribution()
    l4_i, l4_r = check_sw_register_coverage()
    l5_i, l5_r = check_shared_scripts_recoverable()
    all_issues = l1_i + l2_i + l3_i + l4_i + l5_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "sw_offline", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "critical_in_shell": l1_r, "shell_offline_fallback": l2_r,
              "resilience_distribution": l3_r, "sw_register_coverage": l4_r,
              "shared_scripts_recoverable": l5_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("sw_offline_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
