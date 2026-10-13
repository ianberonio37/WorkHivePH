#!/usr/bin/env python3
"""validate_modal_back_helper.py — T42's lock: hardware Back closes an open modal instead of leaving
the page, through ONE owner per modal.

Walked live at 390 (T42, 2026-09-02): opening inventory's Add-Part modal pushed NO history entry, so
the phone Back gesture NAVIGATED AWAY from the whole page (inventory -> logbook) — a worker mid-form
lost the task and their input with one natural gesture.

★2026-10-12 (UFAI W4791 follow-through): TWO OWNERS WAS THE NEXT DEFECT. T42 shipped whModalHistory
for that modal and, the same day, folded the same contract into whModalA11y — which inventory ALSO
wired onto it. Every open pushed two entries owned by two stacks; the X and Cancel buttons passed the
click event as `fromBack`, so they never gave whModalHistory's entry back (it only drained because the
other stack's give-back happened to pop it). Separately, utils' whOverlayBackDismiss pushed a THIRD
kind of entry for every .sheet-overlay/.modal-overlay, all of which whSheetA11y also wires through
whModalA11y — two entries per open there too, and one left behind after every X-close (a Back that
did nothing). And marketplace's empty backdrop divs were wired as dialogs of their own: one Back closed
only the backdrop and the sheet stayed open. Measured live, then fixed to one owner per modal.

Lock (each reddens alone):
  1 no second modal-history stack: utils.js does not define whModalHistory, and no shipped page calls it;
  2 inventory's part-modal is wired by whModalA11y (its one Back owner);
  3 whOverlayBackDismiss only owns an overlay whModalA11y has NOT wired, and never a scrim;
  4 whSheetA11y wires the sibling .sheet of an empty scrim instead of the scrim (whScrimPartner).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["modal-back-helper"]

SECOND_STACK_RE = re.compile(r"window\.whModalHistory\s*=")
CALLS_RE = re.compile(r"whModalHistory\.(?:opened|closed)\(")
INV_WIRED_RE = re.compile(r"\[\s*'part-modal'[^\]]*\]\.forEach\([\s\S]{0,200}?whModalA11y\(el\)")
JA3_DEFERS_RE = re.compile(r"if\s*\(!all\[i\]\.__whModalA11y\s*&&\s*!all\[i\]\.__whScrim\)\s*return\s+all\[i\];")
SCRIM_RE = re.compile(r"function\s+whScrimPartner\([\s\S]{0,700}?function\s+whWireOverlay\([\s\S]{0,900}?"
                      r"window\.whModalA11y\(sheet\)")

_SKIP_DIRS = {"node_modules", ".tmp", "tests", "tools", "test-data-seeder", "playwright-report",
              "supabase", ".git", "substrate", "test-results", ".claude"}


def _pages() -> dict[str, str]:
    out = {}
    for p in ROOT.rglob("*"):
        if p.suffix not in (".html", ".js") or not p.is_file() or p.name == "sw.js":
            continue
        rel = p.relative_to(ROOT).parts
        if any(part in _SKIP_DIRS for part in rel[:-1]):
            continue
        try:
            src = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "whModalHistory" in src or p.name == "inventory.html":
            out[str(p.relative_to(ROOT)).replace("\\", "/")] = src
    return out


def problems_for(utils_src: str, pages: dict[str, str]) -> list[str]:
    out = []
    if SECOND_STACK_RE.search(utils_src):
        out.append("utils.js: a second modal-history stack (whModalHistory) is back - a modal wired by both it and "
                   "whModalA11y pushes two entries per open, and one is left behind as a dead Back")
    for label, src in pages.items():
        if CALLS_RE.search(src):
            line = src.count("\n", 0, CALLS_RE.search(src).start()) + 1
            out.append(f"{label}:{line}: calls whModalHistory - whModalA11y is the one Back owner for every modal")
    inv = pages.get("inventory.html", "")
    if not INV_WIRED_RE.search(inv):
        out.append("inventory.html: the part-modal is no longer wired by whModalA11y - hardware Back exits the page "
                   "mid-form again (the T42 defect)")
    if not JA3_DEFERS_RE.search(utils_src):
        out.append("utils.js: whOverlayBackDismiss owns overlays whModalA11y already owns (or a scrim) - two entries "
                   "per open, and an X-close leaves a Back that does nothing")
    if not SCRIM_RE.search(utils_src):
        out.append("utils.js: whSheetA11y wires an empty backdrop as a dialog again - one Back closes only the "
                   "backdrop and the sheet stays open (measured on marketplace 2026-10-12)")
    return out


def main() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    bad = problems_for(u, _pages())
    if bad:
        print("FAIL modal-back-helper:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS modal-back-helper - one Back owner per modal: no second history stack, inventory's part-modal "
          "wired by whModalA11y, whOverlayBackDismiss owns only unwired overlays, and an empty scrim hands its "
          "dialog role and Back entry to its sheet.")
    return 0


def self_test() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    pages = _pages()
    fails = []
    if problems_for(u, pages):
        fails.append("HEAD should PASS: " + "; ".join(problems_for(u, pages))[:300])
    if not any("second modal-history" in p for p in problems_for(u + "\nwindow.whModalHistory = {};", pages)):
        fails.append("re-adding whModalHistory must redden")
    called = dict(pages); called["x.html"] = "<script>whModalHistory.opened(f);</script>"
    if not any("x.html" in p for p in problems_for(u, called)):
        fails.append("a page calling whModalHistory must redden")
    unwired = dict(pages); unwired["inventory.html"] = INV_WIRED_RE.sub("void 0", pages.get("inventory.html", ""))
    if not any("part-modal" in p for p in problems_for(u, unwired)):
        fails.append("unwiring inventory's part-modal must redden")
    if not any("whOverlayBackDismiss" in p for p in problems_for(JA3_DEFERS_RE.sub("/* owns all */", u), pages)):
        fails.append("whOverlayBackDismiss owning wired overlays must redden")
    if not any("empty backdrop" in p for p in problems_for(SCRIM_RE.sub("/* wires scrims */", u), pages)):
        fails.append("wiring an empty scrim as a dialog must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_modal_back_helper self-test (second stack, a page calling it, unwired part-modal, "
          "double-owning overlay dismiss and a scrim wired as a dialog each redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
