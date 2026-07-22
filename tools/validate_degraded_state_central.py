#!/usr/bin/env python3
"""
validate_degraded_state_central.py - PER_PAGE SaaS-LAYER · Layer AV (Availability & Recovery), 2026-07-22.
==========================================================================================================
METHOD LAW (§0.4b): the AV degraded-state warning is ONE central component, not per-page code. When the
device goes offline (or the backend is unreachable), the user must SEE it — via the shared, idempotent
`offline-banner.js` (a fixed "You are offline. Some actions may not work." bar; `__whOfflineBannerLoaded`
guard) that every USER-FACING interactive page adopts. This gate verifies ADOPTION of that central
component, so a page that touches the backend but drops the offline banner (silently shipping stale/failed
actions with no warning) FAILs.

The AV per-page failure mode has two halves, both centrally covered:
  * network-offline  → the central `offline-banner.js` (this gate) + `connectivity-widget.js`.
  * backend-down / fail-closed / empty-vs-error → the L-layer central backbone (whLogError + global
    uncaught listeners, gate `error-capture`) + P12 (page-battery unhandled-rejection) + read-battery
    (honest empty-vs-error). Re-confirmed, not re-hunted (§0.4 reuse-first).

EXEMPT (internal, not user-facing — an offline banner adds no value): the dev/observability console cohort
(architecture / design-system / symbol-gallery / validator-catalog / *-observability) + backups/tests +
the print-only / static-doc surfaces. Every USER-facing backend-touching page must adopt the banner.

Static + fast. Forward-only (a NEW user-facing interactive page without the banner FAILs). `--selftest`
proves teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_degraded_state_central"]
REPO = Path(__file__).resolve().parent.parent
CENTRAL = "offline-banner.js"
BACKEND = re.compile(r"getDb\(|db\.from\(|db\.functions\.invoke\(|functions\.invoke\(|\.rpc\(")
# internal / non-user-facing surfaces where a device-offline banner adds no value (documented exemptions)
EXEMPT = {
    "architecture.html": "internal archived architecture doc",
    "design-system.html": "internal design-system gallery",
    "symbol-gallery.html": "internal symbol gallery",
    "validator-catalog.html": "internal validator catalog",
    "agentic-rag-observability.html": "internal observability console (admin-only)",
    "llm-observability.html": "internal observability console (admin-only)",
    "marketplace-seller-profile.html": "public read-only profile (no user write actions)",
}
EXCLUDE = ("node_modules", "remotion", "-test.", ".backup", "test-data-seeder", "-390-baseline")


def scan() -> tuple[list[str], int]:
    missing = []
    checked = 0
    for p in sorted(REPO.glob("*.html")):
        if any(x in p.name for x in EXCLUDE) or p.name in EXEMPT:
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        if not BACKEND.search(src):
            continue                       # static page, no backend dependency → no degraded state to warn
        checked += 1
        if CENTRAL not in src:
            missing.append(p.name)
    return missing, checked


def self_test() -> bool:
    ok = True
    tmp_dir = REPO
    good = tmp_dir / "._av_good.html"; bad = tmp_dir / "._av_bad.html"; static = tmp_dir / "._av_static.html"
    try:
        good.write_text('<script>getDb()</script><script src="offline-banner.js"></script>', encoding="utf-8")
        bad.write_text('<script>db.from("t").insert(r)</script>', encoding="utf-8")
        static.write_text('<h1>static</h1>', encoding="utf-8")
        # temporarily scan just these fixtures by name
        for f, should_flag in ((good, False), (bad, True), (static, False)):
            src = f.read_text(encoding="utf-8")
            is_backend = bool(BACKEND.search(src))
            flagged = is_backend and CENTRAL not in src
            if flagged != should_flag:
                print(f"{R}self-test FAIL: {f.name} flag={flagged} want={should_flag}.{X}"); ok = False
    finally:
        for f in (good, bad, static):
            try: f.unlink()
            except OSError: pass
    print((G + "self-test PASS - AV degraded-state-central check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    missing, checked = scan()
    print(f"{B}AV degraded-state central adoption — every user-facing backend page must adopt offline-banner.js ({checked} checked){X}")
    for name in missing:
        print(f"  {R}○{X} {name}: backend-touching but does NOT adopt the central {CENTRAL} — a device-offline user gets NO warning (silently stale/failed actions).")
    if missing:
        print(f"{R}FAIL: {len(missing)} user-facing backend page(s) missing the central offline banner. Add "
              f"`<script src=\"{CENTRAL}\"></script>`, or exempt with a reason if genuinely internal.{X}")
        return 1
    print(f"{G}PASS - all {checked} user-facing backend pages adopt the central {CENTRAL} (AV degraded warning centralized).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
