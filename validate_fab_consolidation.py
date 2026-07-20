#!/usr/bin/env python3
"""
validate_fab_consolidation.py
Layer 0 — Forward-only ratchet for the bottom-right FAB consolidation (2026-07-20).

WHY CENTRALIZED (not page-by-page): the consolidation lives entirely in FOUR shared-
chrome JS files that are injected byte-identical on every nav-hub page. So the contract
is verified ONCE over those files here, and it holds on all ~30 pages — no per-page
Playwright walk needed. Ian: "why are we verifying page by page, do we have a
centralized framework for this?" — this is it.

The contract (Ian: "make the feedback, companion, and online widget be put in the
nav-hub… they overlap"): the nav-hub is the SOLE visible bottom-right FAB. Companion,
feedback and connectivity are launched/shown from INSIDE the hub. Each consolidated
widget keeps its script mounted (so the 'present on every page' gates + pages'
whConnectivityState() banner stay green) but hides its standalone corner element.

If any shared file drops a required marker, or re-introduces the retired reveal that
caused the tap-collision (journey-voice-companion-gates:802), this FAILs — so a future
edit can't silently un-consolidate the corner.
"""
import io
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# (file, description, [must-contain markers], [must-NOT-contain markers])
CONTRACT = [
    ("nav-hub.js", "hub is the single FAB + hosts the consolidated controls + adopts the patterns", [
        "wh-hub-conn-pill",       # live connectivity status pill in the header
        "wh-hub-open-companion",  # Companion launch row
        "wh-hub-open-feedback",   # Feedback launch row
        "wh-hub-conn-detail",     # inline connectivity detail (folded from the popover)
        "paintConnPill",          # the pill painter
        "--wh-panel-max-h",       # panel cap via the component token (C-P1/capPanel) — keeps the header on-screen
        "overflow-y: auto",       # panel scrolls (short-viewport clip fix)
        "wh-patterns.js",         # C-P3: loads the pattern library early
        "WHPatterns.launchPanel", # C-P3: launcher-defer idiom delegated
        "WHPatterns.clickOutside",# C-P3: close-on-click-outside idiom delegated
        "injectHeadBoilerplate",  # shared-<head> wave: centralized favicon + theme-color injection
        "favicon.svg",            # shared-<head>: the SVG favicon SSOT (0/32 pages linked it before)
    ], []),
    ("companion-launcher.js", "companion self-reveals via wh-companion-open, launched from the hub", [
        "wh-companion-open",      # self-contained reveal class
        "window.WHAssistant",     # open()/close() API the hub calls
        "WHPatterns.revealVia",   # C-P3: reveal-decouple idiom delegated
    ], [
        # the retired piggyback reveal that caused the collision must be gone
        "body.wh-hub-open #wh-ai-widget",
    ]),
    ("wh-patterns.js", "the 4 canonical behavioural idioms exist (Axis-3 pattern library)", [
        "window.WHPatterns",
        "launchPanel:", "clickOutside:", "revealVia:", "capPanel:",
    ], []),
    ("wh-feedback-fab.js", "standalone feedback FAB hidden; opened from the hub", [
        "window.WHFeedback",      # open()/close() API the hub calls
        ".wh-fb-fab { display: none",  # corner FAB retired (script still mounts)
    ], []),
    ("connectivity-widget.js", "corner chip/popover hidden; status shown in the hub", [
        "window.whConnectivitySnapshot",             # snapshot the hub pill reads
        ".wh-conn-chip, .wh-conn-popover { display: none",  # corner chip retired (engine still runs)
    ], []),
]


def check():
    passes, violations = [], []
    for fname, desc, must, must_not in CONTRACT:
        fp = ROOT / fname
        if not fp.exists():
            violations.append(f"{fname} — MISSING shared-chrome file")
            continue
        content = fp.read_text(encoding="utf-8", errors="replace")
        for marker in must:
            if marker in content:
                passes.append(f"{fname}: has '{marker}'")
            else:
                violations.append(f"{fname} — MISSING required marker '{marker}' ({desc})")
        for marker in must_not:
            if marker in content:
                violations.append(f"{fname} — re-introduced RETIRED marker '{marker}' (would restore the corner collision)")
            else:
                passes.append(f"{fname}: retired '{marker}' stays gone")
    return passes, violations


def main():
    passes, violations = check()
    print("\n" + "=" * 80)
    print("  FAB Consolidation Contract Validator (Layer 0)")
    print("=" * 80 + "\n")
    for p in passes:
        print(f"  OK  {p}")
    if violations:
        print(f"\n  VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  FAIL {v}")
        print("\nACTION: the bottom-right corner must stay consolidated into the nav-hub —")
        print("        restore the missing marker or remove the re-introduced standalone FAB.\n")
        return 1
    print(f"\nOK  Bottom-right FAB consolidation contract holds across all {len(CONTRACT)} shared files "
          f"(=> all nav-hub pages).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
