#!/usr/bin/env python3
"""validate_photo_pickers_allow_gallery.py - a photo picker lets a person choose a saved photo, not only take one
(gate photo-pickers-allow-gallery, 2026-11-10; holds ENH436..ENH438).

★"I CANNOT ATTACH MY SAVED PHOTOS TO INVENTORIES, IT IS ONLY TAKING A PHOTO" (Ian, 2026-11-10). inventory.html's part
photo input carried `capture="environment"`, and on a phone that attribute opens the camera and skips the gallery. The
logbook's own Attach Photo input has no `capture`, so the phone offers the camera AND saved photos - the parity Ian
asked for. Two more pickers had the same flaw: the logbook's photo defect capture and its nameplate scan, where the
asset-register guide itself tells a crew to photograph nameplates on the walk and load them later.

The measurement is enhancement_inventory._gallery (class G) - called here, never re-derived, so the gate and the seeded
rows read one rule: an image file input with `capture` and no gallery-capable image input beside it.

    python tools/validate_photo_pickers_allow_gallery.py [--self-test]
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from enhancement_inventory import _gallery  # noqa: E402


def _self_test() -> int:
    as_it_was = {"inventory.html": '<input id="f-photo-input" type="file" accept="image/*" capture="environment" class="hidden" />'}
    as_fixed = {"inventory.html": '<input id="f-photo-input" type="file" accept="image/*" class="hidden" />'}
    paired = {"resume.html": ('<input type="file" id="file-photo" accept="image/*" capture="environment" multiple>'
                              '<input type="file" id="file-any" accept="image/*,application/pdf">')}
    fails = []
    if not _gallery(as_it_was):
        fails.append("inventory's camera-only picker, as it was, must fail")
    if _gallery(as_fixed):
        fails.append("the same picker without capture must pass")
    if _gallery(paired):
        fails.append("a camera picker paired with a gallery-capable one must pass")
    print("FAIL photo-pickers-allow-gallery self-test - " + "; ".join(fails) if fails
          else "self-test OK: the camera-only picker fails, the fixed and the paired pickers pass")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    cells = _gallery(None)
    for c in cells:
        print(f"  BAD {c['page']} #{c['key']}: {c['detail'][:200]}")
    if cells:
        print(f"FAIL photo-pickers-allow-gallery - {len(cells)} photo picker(s) force the camera, so a saved photo "
              "cannot be attached")
        return 1
    print("PASS photo-pickers-allow-gallery - every photo picker on a production page lets a person take a photo or "
          "choose a saved one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
