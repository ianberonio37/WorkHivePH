#!/usr/bin/env python3
"""hub-panel-on-screen - §BRH.11 AN: the hub's opened panel stays on the screen (2026-10-26).

Ian, in his own hands: "when you open or tap it it becomes invisible when opened ... when you put it at the top, all
of it is being swallowed at the top, it is not the same in iOS that it will also adjust to keep it not being
swallowed." Measured in nav-hub.js: #wh-hub-panel was anchored by `bottom` and grew UPWARD from the FAB wherever the
FAB rested; the drag clamped the FAB's bottom to innerHeight - 80 and said nothing about the panel; nothing read
env(safe-area-inset-top); the stored position was clamped once at load and never again, while iOS changes innerHeight
every time Safari's toolbar collapses. A FAB dragged to the top opened a panel whose body was above the viewport.

THE FIX (nav-hub.js): placePanel() measures the room above and below the FAB (safe-area insets read through the
--wh-sat / --wh-sab custom properties) and anchors the panel on the side that has it (#wh-hub.wh-panel-below), capped
to that room; clampBottom() honours the top inset and takes off the lift a page's fixed bottom bar adds (--wh-fab-lift);
the position is re-clamped on every resize.

TWO HALVES, BOTH REQUIRED:
  static   nav-hub.js carries the flip (wh-panel-below), reads the top inset, re-clamps on resize, openHub() calls
           placePanel(), and clampBottom() subtracts the inset and the lift - a revert of any one reddens this gate
           without a browser
  measured hub_panel_on_screen_report.json (tools/prove_hub_panel_on_screen.mjs) holds 0 failing cases AND was
           taken against THIS nav-hub.js (its nav_hub_sha) - a changed hub demands a re-run, so the report cannot
           vouch for code it never saw (feedback_a_freshness_stamp_tracks_its_content)

    python tools/validate_hub_panel_on_screen.py
    python tools/validate_hub_panel_on_screen.py --self-test
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "nav-hub.js"
REPORT = ROOT / "hub_panel_on_screen_report.json"

# every pattern of a fact must match; the CSS rule and the JS toggle of the flip sit ~850 lines apart, so they are two
# patterns of one fact rather than one pattern with a window (the first version's 400-char window read the fixed file as
# missing its own flip - a false red the teeth test caught). The clamp facts are bounded by the next `function`, not by a
# character count: clampBottom's comment grew past a 300-char window (a false red), and a wider one reaches placePanel()'s
# own safeInset('top') right below it, so a clamp that dropped the inset would still read green
CLAMP_BODY = r"function clampBottom\((?:(?!\bfunction\b)[\s\S]){0,2000}?"
STATIC = {
    "the flip class (wh-panel-below) is styled and toggled": (re.compile(r"#wh-hub\.wh-panel-below\s+#wh-hub-panel\s*\{"),
                                                              re.compile(r"""classList\.toggle\(\s*['"]wh-panel-below['"]""")),
    "the top safe-area inset is read": (re.compile(r"safe-area-inset-top"),),
    "the stored position is re-clamped on resize": (re.compile(r"""addEventListener\(\s*['"]resize['"][\s\S]{0,600}clampBottom\("""),),
    "openHub() places the panel": (re.compile(r"function openHub\(\)[\s\S]{0,600}placePanel\(\)"),),
    "the drag clamp honours the inset": (re.compile(CLAMP_BODY + r"safeInset\(\s*['\"]top['\"]\s*\)"),),
    "the drag clamp takes off a fixed bottom bar's lift": (re.compile(CLAMP_BODY + r"--wh-fab-lift"),
                                                          # a subtraction, not the "-lift" inside the property's own name
                                                          re.compile(CLAMP_BODY + r"(?<![\w-])-\s*lift\b")),
}


def static_findings(src: str) -> list[str]:
    return [name for name, rxs in STATIC.items() if not all(rx.search(src) for rx in rxs)]


def report_findings(src: str, rep: dict | None) -> list[str]:
    if rep is None:
        return ["no hub_panel_on_screen_report.json - run: node tools/prove_hub_panel_on_screen.mjs (and --engine webkit)"]
    sha = hashlib.sha256(src.encode("utf-8")).hexdigest()[:12]
    out = []
    if rep.get("nav_hub_sha") != sha:
        out.append(f"the report was taken against nav-hub.js {rep.get('nav_hub_sha')}, the file is now {sha} - re-run the prover")
    bad = [c for c in rep.get("cases") or [] if not c.get("ok")]
    for c in bad[:12]:
        out.append(f"FAIL {c.get('engine')} {c.get('viewport')} {c.get('page')} {c.get('case')}: {c.get('why')}")
    if len(bad) > 12:
        out.append(f"... and {len(bad) - 12} more failing case(s)")
    if not rep.get("cases"):
        out.append("the report holds no cases")
    engines = {c.get("engine") for c in rep.get("cases") or []}
    if "webkit" not in engines:
        out.append("no webkit cases in the report - the engine that bit Ian: run with --engine webkit")
    return out


def self_test() -> int:
    good = ("#wh-hub.wh-panel-below #wh-hub-panel { top: 68px } ... hub.classList.toggle('wh-panel-below', goBelow) "
            "env(safe-area-inset-top, 0px) window.addEventListener('resize', function () { applyPosition(snapSide, clampBottom(1)) }) "
            "function openHub() { x(); placePanel(); } function clampBottom(b) { var lift = css('--wh-fab-lift'); "
            "return Math.min(b, window.innerHeight - 80 - safeInset('top') - lift); }")
    bad = "#wh-hub-panel { bottom: 68px } function openHub() { x(); } Math.max(16, Math.min(saved.bottom, window.innerHeight - 80))"
    # the clamp dropped its inset and lift, but the function right below it still reads both - must stay red
    leaky = good.replace("- safeInset('top') - lift", "").replace("css('--wh-fab-lift')", "0") + \
        " function placePanel() { var a = safeInset('top'); var lift = css('--wh-fab-lift'); x - lift; }"
    ok = not static_findings(good) and len(static_findings(bad)) == len(STATIC)
    ok = ok and set(static_findings(leaky)) == {"the drag clamp honours the inset", "the drag clamp takes off a fixed bottom bar's lift"}
    sha = hashlib.sha256(good.encode("utf-8")).hexdigest()[:12]
    rep_ok = {"nav_hub_sha": sha, "cases": [{"ok": True, "engine": "chromium"}, {"ok": True, "engine": "webkit"}]}
    rep_stale = {"nav_hub_sha": "000000000000", "cases": [{"ok": True, "engine": "chromium"}, {"ok": False, "engine": "webkit", "why": "x"}]}
    ok = ok and not report_findings(good, rep_ok) and len(report_findings(good, rep_stale)) == 2 and len(report_findings(good, None)) == 1
    print(("PASS" if ok else "FAIL") + " hub-panel-on-screen self-test")
    return 0 if ok else 1


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        return self_test()
    src = HUB.read_text(encoding="utf-8", errors="replace")
    rep = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else None
    findings = static_findings(src) + report_findings(src, rep)
    cases = (rep or {}).get("cases") or []
    print("hub-panel-on-screen (§BRH.11 AN): the opened nav-hub panel stays inside the viewport")
    print(f"  static: {len(STATIC) - len(static_findings(src))}/{len(STATIC)} facts hold in nav-hub.js")
    print(f"  measured: {sum(1 for c in cases if c.get('ok'))}/{len(cases)} cases pass"
          + (f" ({', '.join(sorted({c.get('engine', '?') for c in cases}))})" if cases else ""))
    for f in findings:
        print(f"  - {f}")
    print("PASS" if not findings else "FAIL")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
