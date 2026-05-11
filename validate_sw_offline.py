"""
Service Worker Offline Coverage -- WorkHive Platform
======================================================
Catches the offline-blank-page bug: a worker on the factory floor
loses Wi-Fi, opens logbook.html / inventory.html on their PWA, and
the page is empty because the shell isn't cached. Companion to
validate_cache_invalidation -- that gate keeps CACHE_NAME fresh;
this gate ensures the SHELL_FILES list COVERS the pages workers
expect to use offline.

Layer 1 -- Worker-critical pages in SHELL_FILES                          [WARN]
  WORKER_CRITICAL_PAGES (logbook, inventory, pm-scheduler, parts,
  shift-brain, asset-hub, hive) should each appear in the sw.js
  SHELL_FILES array OR be opt-out via SW_OFFLINE_OK with a reason.

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


def check_critical_in_shell() -> tuple[list[dict], list[dict]]:
    issues, report = [], []
    shell = shell_files()
    for page in WORKER_CRITICAL_PAGES:
        if page in shell:
            continue
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
    rows = []
    register_re = re.compile(r"navigator\.serviceWorker\.register")
    for page in list_pages():
        src = read_file(page) or ""
        if register_re.search(src):
            rows.append({"page": page})
    return [], rows


CHECK_NAMES = [
    "critical_in_shell", "shell_offline_fallback",
    "resilience_distribution", "sw_register_coverage",
]
CHECK_LABELS = {
    "critical_in_shell":       "L1  Worker-critical pages live in SHELL_FILES                  [WARN]",
    "shell_offline_fallback":  "L2  SHELL_FILES pages declare offline fallback                 [WARN]",
    "resilience_distribution": "L3  Per-page online/offline signal use (informational)         [INFO]",
    "sw_register_coverage":    "L4  Pages that register sw.js (informational)                  [INFO]",
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
    all_issues = l1_i + l2_i + l3_i + l4_i
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
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("sw_offline_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
