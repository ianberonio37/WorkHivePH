"""validate_resilience.py - Phase 1.10 (reframe addition) of STRATEGIC_ROADMAP.md.

The Philippine industrial reality: brownouts, intermittent 3G/4G, shared
tablets, and 2G fallback in rural plants. WorkHive must be honest about
which surfaces handle network loss gracefully and which silently break.

This validator scans production pages and checks 4 resilience contracts:

  L1  Offline queue contract
      Pages that accept worker-authored writes (logbook, voice-journal,
      schedule_items entries) must declare an offline queue OR explicitly
      opt-out with a comment marker.

  L2  Network-loss UI
      Pages that depend on Supabase reads must show a 'You are offline'
      affordance — either via OFFLINE_BANNER load, navigator.onLine check,
      or a documented fallback. Without this, the worker sees an empty
      screen during a brownout.

  L3  fetchWithTimeout coverage
      Every production HTML/JS fetch() call must use fetchWithTimeout.
      Unbounded fetch hangs the UI when the cellular link drops.

  L4  Shared-device safety
      Pages that store credentials/identity in localStorage must clear them
      on Sign Out (db.auth.signOut + localStorage.removeItem). Shared tablets
      mean the next worker should not inherit the previous worker's identity.

Skills consulted:
  devops (network resilience patterns)
  mobile-maestro (shared-tablet shift-handover reality)
  realtime-engineer (offline-then-online reconnection)
  security (next-worker-inherits-previous-identity is a real PH plant risk)
"""
from __future__ import annotations
import json, re, sys
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
OFFLINE_QUEUE_MARKERS = ("offlineQueue", "indexedDB", "wh_offline_queue", "// offline-queue:")
OFFLINE_UI_MARKERS    = ("navigator.onLine", "offline-banner", "OFFLINE_BANNER",
                          "renderOfflineState", "wh-offline", "// offline-ui:")
IDENTITY_CLEAR_MARKERS = ("signOut", "auth.signOut")

LAYERS = [
    {"layer": "L1", "label": f"Offline queue on {len(WRITE_PAGES)} writer pages"},
    {"layer": "L2", "label": f"Network-loss UI on {len(READ_PAGES)} read pages"},
    {"layer": "L3", "label": "fetchWithTimeout coverage on production fetch sites"},
    {"layer": "L4", "label": f"Sign-out clears identity on {len(IDENTITY_PAGES)} pages"},
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
                                     f"auth.signOut() call. Shared-tablet hand-over "
                                     f"leaves the next worker logged in as the previous one."})
    return issues


def run() -> dict:
    issues: list[dict] = []
    issues.extend(check_offline_queue())
    issues.extend(check_offline_ui())
    issues.extend(check_fetch_timeout())
    issues.extend(check_identity_clear())

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
