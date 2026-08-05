#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURN A LIVE-MCP LENS CAPTURE INTO BANKABLE READINGS
═══════════════════════════════════════════════════════════════════════════════════════════════════

The live MCP walk drives `live-state-runner.js` in the real browser and captures, per surface, the
verdict of each lens. This maps those lens keys onto the registry's (surface, state) cells and writes
`.tmp/live_walk.json` for `tools/bank_live_walk.py`.

TWO RULES IT WILL NOT BEND:

  1. `ok === null` IS INCONCLUSIVE, NEVER A PASS. The runner returns null when a lens could not see
     the thing it judges — a disabled state on a surface with no disabled control, a contrast ratio
     on text over a gradient. Those cells are simply not emitted, so they stay stale and visible,
     rather than being banked on an instrument that looked away.

  2. A FALSE READING IS EMITTED AS FALSE. A lens that says ok=false becomes an owed row carrying its
     own detail, because a walk that found something is worth more than one that found nothing.

Input:  .tmp/lens_capture.json   {"<surface>": {"<lens>": {"<key>": <ok|value>, ...}, ...}, ...}
Run:    python tools/lens_to_readings.py            # writes .tmp/live_walk.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURE = os.path.join(ROOT, ".tmp", "lens_capture.json")
OUT = os.path.join(ROOT, ".tmp", "live_walk.json")

# THE URL THE BANK REGISTERS, NOT THE ONE I HAPPENED TO OPEN. Gate rule R3 requires a live-walk ref to
# name a surface URL the bank knows, and it refused five profile rows because this map pointed at
# Romeo Beltran's profile while every profile row is registered against Pablo Aguilar's. Walking a
# different seller's page and banking it against these rows would be evidence about the wrong screen —
# R3 catching that is the rule working, and hard-coding the right URL here is the fix.
# `market` is deliberately ?section=parts: the bare marketplace.html defaults to the SERVICES section,
# which is the market_svc surface, so measuring `market` without forcing the section measures the
# wrong tab — and an empty Services tab passes most lenses vacuously.
URLS = {
    "market": "/workhive/marketplace.html?section=parts",
    "market_svc": "/workhive/marketplace.html?section=services",
    "seller": "/workhive/marketplace-seller.html",
    "admin": "/workhive/platform-actions.html",
    "profile": "/workhive/marketplace-seller-profile.html?worker=Pablo%20Aguilar",
    "community": "/workhive/community.html",
    "public_feed": "/workhive/public-feed.html",
    "achievements": "/workhive/achievements.html",
}

# lens key -> (registry state, category, what the lens actually established)
MAP = {
    ("run", "populated"): ("populated", "*",
        "the surface rendered real content with no error chrome, no undefined/NaN/[object Object] "
        "reaching the screen, no raw status enum, and no horizontal document overflow"),
    ("run", "empty"): ("empty", "*",
        "the empty state NAMES the gap and still offers controls, and is distinguishable from a "
        "failure — an emptiness that reads as a breakage fails here"),
    ("run", "error"): ("error", "*",
        "a failed read says so, is distinguishable from an emptiness, and offers a retry"),
    ("run", "edge"): ("edge", "*",
        "the boundary case rendered — longest name, zero price — with no overflow and nothing clipped"),
    ("run", "degraded"): ("degraded", "*", "the degraded state was induced and reported honestly"),
    ("run", "script_name"): ("script_name", "*",
        "a Baybayin name rendered without overflow or mojibake"),
    ("states", "component_populated"): ("component_populated", "*",
        "the component's populated state carries real content and no unrendered junk"),
    ("states", "component_loading"): ("component_loading", "*",
        "the loading state was induced and is visible as loading, not as emptiness"),
    ("states", "component_skeleton"): ("component_skeleton", "*",
        "the skeleton state was induced and matched this platform's own wh-cardskel stem"),
    ("states", "component_disabled"): ("component_disabled", "*",
        "a disabled control states why it is disabled"),
    ("states", "component_busy"): ("component_busy", "*",
        "the busy state is announced while the action is in flight"),
    ("states", "component_error"): ("component_error", "*",
        "the component's error state is distinguishable from its empty state"),
    ("visual", "apca"): ("contrast_apca", "*",
        "APCA perceptual contrast, alpha-composited against the real effective background rather "
        "than assuming white"),
    ("visual", "reduced_motion"): ("reduced_motion", "*",
        "prefers-reduced-motion is honoured: no animation runs when it is set"),
    ("visual", "focus_visible"): ("focus_visible", "*", "keyboard focus is visible on every control"),
    ("visual", "contrast_wcag"): ("contrast_wcag", "*", "WCAG contrast ratio, alpha-composited"),
    ("visual", "icon_only_name"): ("icon_only_name", "*",
        "every icon-only control carries an accessible name"),
}

# comprehension is a compound: its cells are derived, not a single ok
def comprehension_cells(c):
    out = []
    if c is None:
        return out
    found = c.get("numbersFound")
    unexp = c.get("unexplainedCount")
    if isinstance(found, int) and isinstance(unexp, int):
        # NON-VACUOUS: a surface with no numbers cannot demonstrate that it explains them.
        if found > 0:
            out.append(("what_is_this_number", unexp == 0,
                        f"numbers a person can see: {found}; of those, ones with nothing nearby "
                        f"saying what they mean: {unexp}"))
    return out


def main():
    if not os.path.exists(CAPTURE):
        print(f"FAIL — {CAPTURE} not found; capture the walk first")
        return 1
    cap = json.load(open(CAPTURE, encoding="utf-8"))
    readings, skipped = [], 0
    for surface, lenses in cap.items():
        url = URLS.get(surface, "/workhive/marketplace.html")
        for lens, keys in (lenses or {}).items():
            if not isinstance(keys, dict):
                continue
            if lens == "comprehension":
                for state, ok, why in comprehension_cells(keys):
                    readings.append({"category": "*", "state": state, "surface": surface, "url": url,
                                     "ok": bool(ok), "checked": [why], "notes": "" if ok else why})
                continue
            for key, val in keys.items():
                spec = MAP.get((lens, key))
                if not spec:
                    continue
                state, cat, why = spec
                if val is None:                      # INCONCLUSIVE — never a pass, never emitted
                    skipped += 1
                    continue
                if not isinstance(val, bool):
                    continue
                readings.append({"category": cat, "state": state, "surface": surface, "url": url,
                                 "ok": val, "checked": [why,
                                    "measured in the live MCP browser against the running stack"],
                                 "notes": "" if val else f"the {lens} lens reported {state} as false"})
    json.dump(readings, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(readings)} readings written to {OUT}  "
          f"({skipped} inconclusive cells deliberately left stale)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
