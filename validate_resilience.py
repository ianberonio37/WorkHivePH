"""validate_resilience.py - Phase 1.10 + Phase 2 of STRATEGIC_ROADMAP.md.

The Philippine industrial reality: brownouts, intermittent 3G/4G, shared
tablets, and 2G fallback in rural plants. WorkHive must be honest about
which surfaces handle network loss gracefully and which silently break.

Phase 2 introduced 5 shared helpers that this validator enforces:
  - offline-queue.js (IDB-backed queue helper, registry pattern)
  - connectivity-widget.js (online/offline + queue-depth chip)
  - form-autosave.js (brownout-safe state, silent restore on mount)
  - session-timeout.js (shared-tablet hand-over: idle prompt + hard clear)
  - device-fingerprint.js (new_device audit event when fingerprint changes)

Layers:
  L1  Offline queue contract — writer pages declare an offline queue
      (logbook's local IDB queue OR offline-queue.js via whCreateQueue).
  L2  Network-loss UI — read pages show 'offline' affordance (offline-banner.js,
      connectivity-widget.js, navigator.onLine, or documented fallback).
  L3  fetchWithTimeout coverage — every production fetch() is bounded.
  L4  Shared-device sign-out — identity pages clear on signOut.
  L5  Phase 2 connectivity widget loaded on production pages.
  L6  Phase 2 session-timeout loaded on identity pages.
  L7  Phase 2 device-fingerprint loaded on identity pages.

Skills consulted:
  devops (network resilience patterns)
  mobile-maestro (shared-tablet shift-handover reality)
  realtime-engineer (offline-then-online reconnection)
  security (next-worker-inherits-previous-identity, detective controls)
"""
from __future__ import annotations
import json, re, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent

# Pages that ACCEPT user-authored writes. These need offline queues.
WRITE_PAGES = [
    "logbook.html",
    "voice-journal.html",
    "dayplanner.html",
    "pm-scheduler.html",
]

# Pages that depend on reads and should show offline UI.
READ_PAGES = [
    "logbook.html",
    "asset-hub.html",
    "alert-hub.html",
    "dayplanner.html",
    "analytics.html",
    "predictive.html",
    "voice-journal.html",
    "skillmatrix.html",
    "pm-scheduler.html",
]

# Pages that hold identity in localStorage. These need a Sign Out that clears.
IDENTITY_PAGES = [
    "logbook.html",
    "hive.html",
    "asset-hub.html",
    "alert-hub.html",
    "dayplanner.html",
    "voice-journal.html",
    "skillmatrix.html",
]

# Resilience markers (any one of these counts as compliance for L1/L2).
OFFLINE_QUEUE_MARKERS = ("offlineQueue", "indexedDB", "wh_offline_queue",
                          "whCreateQueue", "offline-queue.js", "// offline-queue:")
OFFLINE_UI_MARKERS    = ("navigator.onLine", "offline-banner", "OFFLINE_BANNER",
                          "renderOfflineState", "wh-offline",
                          "connectivity-widget.js", "// offline-ui:")
IDENTITY_CLEAR_MARKERS = ("signOut", "auth.signOut", "session-timeout.js")

# Phase 2 shared helpers — pages must opt in via <script> tag.
CONNECTIVITY_WIDGET = "connectivity-widget.js"
SESSION_TIMEOUT     = "session-timeout.js"
DEVICE_FINGERPRINT  = "device-fingerprint.js"

# Production pages that should load the connectivity widget (any user-facing
# surface where a worker may be writing or reading during a brownout).
CONNECTIVITY_WIDGET_PAGES = [
    "hive.html", "logbook.html", "pm-scheduler.html", "inventory.html",
    "asset-hub.html", "shift-brain.html", "dayplanner.html", "report-sender.html",
]
# Pages that hold identity → must load session-timeout + device-fingerprint
SESSION_TIMEOUT_PAGES    = list(CONNECTIVITY_WIDGET_PAGES)
DEVICE_FINGERPRINT_PAGES = list(CONNECTIVITY_WIDGET_PAGES)

LAYERS = [
    {"layer": "L1", "label": f"Offline queue on {len(WRITE_PAGES)} writer pages"},
    {"layer": "L2", "label": f"Network-loss UI on {len(READ_PAGES)} read pages"},
    {"layer": "L3", "label": "fetchWithTimeout coverage on production fetch sites"},
    {"layer": "L4", "label": f"Sign-out clears identity on {len(IDENTITY_PAGES)} pages"},
    {"layer": "L5", "label": f"connectivity-widget.js on {len(CONNECTIVITY_WIDGET_PAGES)} production pages"},
    {"layer": "L6", "label": f"session-timeout.js on {len(SESSION_TIMEOUT_PAGES)} identity pages"},
    {"layer": "L7", "label": f"device-fingerprint.js on {len(DEVICE_FINGERPRINT_PAGES)} identity pages"},
]

# Pre-existing-debt allowlist. As resilience hardening lands page by page,
# entries can be removed. Today's reality: most pages do NOT yet have these
# affordances — listing them here keeps the gate at PASS while the roadmap
# tackles each page deliberately.
DEFERRED_PAGES_OFFLINE_QUEUE = {
    "voice-journal.html",   # planned Phase 2 (offline transcript queue)
    "dayplanner.html",      # planned Phase 2
    "pm-scheduler.html",    # planned Phase 2
    # logbook.html already has an IndexedDB queue (April 2026)
}
DEFERRED_PAGES_OFFLINE_UI = {
    "analytics.html",
    "predictive.html",
    "skillmatrix.html",
    "pm-scheduler.html",
    "voice-journal.html",
    "dayplanner.html",
    "alert-hub.html",
    "asset-hub.html",
}
DEFERRED_PAGES_FETCH_TIMEOUT: set[str] = {
    # Pre-existing unbounded fetch sites as of 2026-05-13. These predate the
    # fetchWithTimeout wrapper. Each entry must be tracked in PRODUCTION_FIXES.md
    # with a target wrap date. The roadmap's Phase 1.5 explicitly addressed
    # 8 sites (logbook, pm-scheduler, skillmatrix, assistant ×3, engineering-
    # design ×2, floating-ai). The rest are deferred to a dedicated pass.
    "analytics.html",          # analytics-orchestrator wrap planned next batch
    "analytics-report.html",   # server-side renderer trigger
    "marketplace-seller.html", # Stripe Connect endpoints (Phase 5 marketplace)
    "marketplace.html",        # Stripe checkout endpoints (Phase 5 marketplace)
    "platform-health.html",    # retired surface (see memory project_platform_health_retired)
    "report-sender.html",      # email send + voice transcribe + scheduled-agents
    "voice-journal.html",      # voice-transcribe (will be wrapped with Phase 2 voice harden)
    "voice-handler.js",        # shared voice helper (same Phase 2 batch)
    "validator-catalog.html",  # P1 roadmap 2026-05-27 — admin-only validator browser. Uses inline AbortController+setTimeout (8s) instead of fetchWithTimeout because the page is self-contained and doesn't load utils.js (allowlisted in validate_loads_utils_js).
    "llm-observability.html",  # P1 roadmap 2026-05-27 — admin-only LLM observability. Reads ai_cost_log via supabase client (singleton), no bare fetch.
}
DEFERRED_PAGES_IDENTITY_CLEAR = {
    "logbook.html",        # signOut wiring deferred (no SignOut button on logbook itself)
    "asset-hub.html",
    "alert-hub.html",
    "dayplanner.html",
    "voice-journal.html",
    "skillmatrix.html",
}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _has_any(src: str, markers: tuple) -> bool:
    return any(m in src for m in markers)


def check_offline_queue() -> list[dict]:
    issues: list[dict] = []
    for name in WRITE_PAGES:
        if name in DEFERRED_PAGES_OFFLINE_QUEUE:
            continue
        p = ROOT / name
        if not p.exists():
            continue
        src = _read(p)
        if not _has_any(src, OFFLINE_QUEUE_MARKERS):
            issues.append({"check": "offline_queue", "layer": "L1", "page": name,
                           "reason": f"{name} accepts writes but has no offline queue. "
                                     f"Brownout writes are lost silently. Add an IndexedDB queue "
                                     f"or add to DEFERRED_PAGES_OFFLINE_QUEUE."})
    return issues


def check_offline_ui() -> list[dict]:
    issues: list[dict] = []
    for name in READ_PAGES:
        if name in DEFERRED_PAGES_OFFLINE_UI:
            continue
        p = ROOT / name
        if not p.exists():
            continue
        src = _read(p)
        if not _has_any(src, OFFLINE_UI_MARKERS):
            issues.append({"check": "offline_ui", "layer": "L2", "page": name,
                           "reason": f"{name} reads from Supabase but never checks "
                                     f"navigator.onLine or shows an offline banner. "
                                     f"During a brownout the page renders an empty state with "
                                     f"no explanation."})
    return issues


def check_fetch_timeout() -> list[dict]:
    issues: list[dict] = []
    # Scan production HTML + project-level .js for bare 'await fetch(' or
    # '= await fetch(' that doesn't use fetchWithTimeout.
    targets: list[Path] = []
    for ext in ("*.html", "*.js"):
        for p in sorted(ROOT.glob(ext)):
            name = p.name.lower()
            if any(b in name for b in ("backup", "-test.html", "_test.")):
                continue
            if name == "sw.js":
                continue   # service worker has its own pattern
            targets.append(p)

    bare_fetch = re.compile(r"\bawait\s+fetch\s*\(")
    wrapper    = "fetchWithTimeout"
    for p in targets:
        if p.name in DEFERRED_PAGES_FETCH_TIMEOUT:
            continue
        src = _read(p)
        if not src:
            continue
        if "await fetch(" in src and wrapper not in src:
            for m in bare_fetch.finditer(src):
                line = src.count("\n", 0, m.start()) + 1
                issues.append({"check": "fetch_timeout", "layer": "L3",
                               "page": p.name,
                               "reason": f"{p.name}:{line} uses bare 'await fetch('. "
                                         f"Wrap with fetchWithTimeout(url, opts, ms) so "
                                         f"a hung server doesn't strand the user."})
                break
    return issues


def check_identity_clear() -> list[dict]:
    issues: list[dict] = []
    for name in IDENTITY_PAGES:
        if name in DEFERRED_PAGES_IDENTITY_CLEAR:
            continue
        p = ROOT / name
        if not p.exists():
            continue
        src = _read(p)
        if not _has_any(src, IDENTITY_CLEAR_MARKERS):
            issues.append({"check": "identity_clear", "layer": "L4", "page": name,
                           "reason": f"{name} stores identity but lacks an "
                                     f"auth.signOut() call or session-timeout.js. "
                                     f"Shared-tablet hand-over leaves the next worker "
                                     f"logged in as the previous one."})
    return issues


def _check_script_loaded(pages: list[str], script_name: str, layer: str, friendly: str) -> list[dict]:
    issues: list[dict] = []
    for name in pages:
        p = ROOT / name
        if not p.exists():
            continue
        src = _read(p)
        if script_name not in src:
            issues.append({"check": f"{layer.lower()}_{script_name.replace('.js','')}",
                           "layer": layer, "page": name,
                           "reason": f"{name} does not load <script src=\"{script_name}\">. "
                                     f"{friendly}"})
    return issues


def check_connectivity_widget() -> list[dict]:
    issues = _check_script_loaded(
        CONNECTIVITY_WIDGET_PAGES, CONNECTIVITY_WIDGET, "L5",
        "Without it, the worker has no visible indicator of offline state + queue depth.")
    # Layout contract: the chip MUST clear the nav-hub FAB stack at the
    # bottom-right corner (FAB sits at bottom:24px, ~50px tall = ~74px
    # footprint). Walkthrough 2026-05-13 caught the chip at bottom:0.75rem
    # rendering hidden behind the FAB at the same z-index.
    widget = ROOT / CONNECTIVITY_WIDGET
    if widget.exists():
        src = _read(widget)
        # Strip C-style block comments first — a comment like
        # `/* chip was at bottom:0.75rem */` inside the rule would otherwise
        # be matched by the regex and produce a false positive.
        src_stripped = re.sub(r"/\*[\s\S]*?\*/", "", src)
        m = re.search(r"\.wh-conn-chip\s*\{[^}]*?bottom:\s*([\d.]+)\s*rem", src_stripped, re.DOTALL)
        if m:
            try:
                bottom_rem = float(m.group(1))
                if bottom_rem < 5.0:
                    issues.append({
                        "layer": "L5", "page": CONNECTIVITY_WIDGET, "check": "chip_position",
                        "reason": (
                            f"{CONNECTIVITY_WIDGET}: .wh-conn-chip bottom is {bottom_rem}rem; "
                            f"must be >= 5rem to clear the nav-hub FAB at bottom:24px+50px. "
                            f"Below 5rem the chip is hidden behind the FAB at the same z-index."
                        ),
                    })
            except ValueError:
                pass
        else:
            issues.append({
                "layer": "L5", "page": CONNECTIVITY_WIDGET, "check": "chip_position",
                "reason": (
                    f"{CONNECTIVITY_WIDGET}: could not parse .wh-conn-chip `bottom:` value. "
                    f"Expected `bottom: <N>rem` inside the chip CSS rule."
                ),
            })
    return issues


def check_session_timeout() -> list[dict]:
    return _check_script_loaded(
        SESSION_TIMEOUT_PAGES, SESSION_TIMEOUT, "L6",
        "Without it, an idle shared tablet stays signed in as the previous worker.")


def check_device_fingerprint() -> list[dict]:
    return _check_script_loaded(
        DEVICE_FINGERPRINT_PAGES, DEVICE_FINGERPRINT, "L7",
        "Without it, a sign-in from a new device produces no audit event for the supervisor.")


def run() -> dict:
    issues: list[dict] = []
    issues.extend(check_offline_queue())
    issues.extend(check_offline_ui())
    issues.extend(check_fetch_timeout())
    issues.extend(check_identity_clear())
    issues.extend(check_connectivity_widget())
    issues.extend(check_session_timeout())
    issues.extend(check_device_fingerprint())

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "resilience", "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": [],
            "deferred": {
                "offline_queue":   sorted(DEFERRED_PAGES_OFFLINE_QUEUE),
                "offline_ui":      sorted(DEFERRED_PAGES_OFFLINE_UI),
                "fetch_timeout":   sorted(DEFERRED_PAGES_FETCH_TIMEOUT),
                "identity_clear":  sorted(DEFERRED_PAGES_IDENTITY_CLEAR),
            }}


def main() -> int:
    out = run()
    print(f"\nResilience Validator ({len(out['layers'])}-layer)")
    print("=" * 55)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"][:20]:
            page = i.get("page", "")
            print(f"  [FAIL] [{i['check']}]  {page}: {i['reason']}")
        if len(out["issues"]) > 20:
            print(f"  ...and {len(out['issues']) - 20} more")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "resilience_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
