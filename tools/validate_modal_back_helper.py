#!/usr/bin/env python3
"""validate_modal_back_helper.py — T42's lock: hardware Back closes an open modal instead of
leaving the page.

Walked live at 390 (T42): opening inventory's Add-Part modal pushed NO history entry, so the phone
Back gesture NAVIGATED AWAY from the whole page (inventory -> logbook) — a worker mid-form lost
the task and their input with one natural gesture; no page wired Back to modal state. Fixed
2026-09-02: utils.js ships whModalHistory (opened(closeFn) pushes one entry; popstate closes the
top modal; closed() consumes the entry on explicit close — re-entrancy safe), and inventory's
part-modal is the first wired consumer. Verified live BOTH directions: Back closed the modal and
STAYED on inventory; X-close consumed its entry (history balanced, no spare-entry regression).

Lock: (1) utils.js ships whModalHistory with the push/popstate/consume contract; (2) inventory's
part-modal calls opened() on show and closed() on explicit close. Teeth: each shape reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["modal-back-helper"]

HELPER_RE = re.compile(r"whModalHistory\s*=\s*\{[\s\S]{0,900}?history\.pushState[\s\S]{0,900}?addEventListener\(\s*'popstate'")
WIRE_OPEN_RE = re.compile(r"whModalHistory\.opened\(")
WIRE_CLOSE_RE = re.compile(r"whModalHistory\.closed\(\)")


def problems_for(utils_src: str, inv_src: str) -> list[str]:
    out = []
    if not HELPER_RE.search(utils_src):
        out.append("utils.js: whModalHistory (pushState on open + popstate closes the modal) is gone — "
                   "hardware Back exits the page mid-form again (the T42 defect)")
    if not WIRE_OPEN_RE.search(inv_src):
        out.append("inventory.html: the part-modal no longer calls whModalHistory.opened() on show")
    if not WIRE_CLOSE_RE.search(inv_src):
        out.append("inventory.html: the part-modal's explicit close no longer consumes its history entry "
                   "(whModalHistory.closed()) — every open leaves a spare Back step")
    return out


def main() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    i = io.open(ROOT / "inventory.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(u, i)
    if bad:
        print("FAIL modal-back-helper:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS modal-back-helper — whModalHistory shipped in utils.js and inventory's part-modal is "
          "wired both directions (Back closes the modal in place; explicit close balances history).")
    return 0


def self_test() -> int:
    u = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    i = io.open(ROOT / "inventory.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(u, i):
        fails.append("HEAD should PASS")
    if not any("gone" in p for p in problems_for(u.replace("whModalHistory", "whModalHistoryX"), i)):
        fails.append("removing the helper must redden")
    if not any("opened()" in p for p in problems_for(u, WIRE_OPEN_RE.sub("void(", i))):
        fails.append("unwiring the open must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_modal_back_helper self-test (missing helper + unwired open both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
