#!/usr/bin/env python3
"""
prep_mascot.py - cut the WorkHive bee mascot out of its poster background.
==========================================================================
Ian's mascot arrives as a full POSTER: the 3D character stands in a lit
factory, with a headline panel on the left and a phone on the right. For the
video the CHARACTER has to come out of that scene cleanly.

Colour keying does not work here and the first version proved it: a LAB
flood-fill from the frame edges kept 91.9% of the crop, i.e. removed almost
nothing, because the backdrop is a busy photographic scene rather than a flat
colour. So this uses GRABCUT - an iterative graph-cut segmentation seeded with
a rectangle around the subject. It models foreground/background colour
distributions instead of matching one background value, which is exactly the
problem a photographic backdrop poses. OpenCV ships it, so there is no model
download.

Pipeline: crop to the subject band -> GrabCut (5 iterations) -> keep the
largest connected component (drops stray background islands the cut leaves
behind) -> close small holes -> feather 1.5px -> autocrop -> RGBA PNG.

Writes remotion_scenes/public/mascot-cut.png.

CLI:
    python tools/prep_mascot.py
    python tools/prep_mascot.py --left 0.22 --right 0.66 --top 0.02
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "brand_assets" / "mascot-bee.png"
DEST = ROOT / "remotion_scenes" / "public" / "mascot-cut.png"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--left", type=float, default=0.21)
    ap.add_argument("--right", type=float, default=0.67)
    ap.add_argument("--top", type=float, default=0.0)
    ap.add_argument("--bottom", type=float, default=1.0)
    ap.add_argument("--iters", type=int, default=6)
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"No mascot at {src}. Run tools/find_mascot.py --stage first.")
        return 1

    import cv2
    import numpy as np
    from PIL import Image, ImageFilter

    im = Image.open(src).convert("RGB")
    W, H = im.size
    box = (int(W * a.left), int(H * a.top), int(W * a.right), int(H * a.bottom))
    im = im.crop(box)
    arr = np.asarray(im)
    h, w = arr.shape[:2]

    # GrabCut seeded with a rect inset from the crop: everything outside the
    # inset is treated as probable background, inside as probable foreground.
    mask = np.zeros((h, w), np.uint8)
    inset = (int(w * 0.04), int(h * 0.02), int(w * 0.92), int(h * 0.97))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), mask, inset,
                bgd, fgd, a.iters, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # keep only the LARGEST component - grabcut routinely leaves islands of
    # backdrop that survive as floating debris in the composite
    n, lab, stats, _ = cv2.connectedComponentsWithStats((fg > 0).astype(np.uint8), 8)
    if n > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = np.where(lab == biggest, 255, 0).astype(np.uint8)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k)          # fill pinholes
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k)           # drop specks

    out = Image.fromarray(np.dstack([arr, fg]).astype(np.uint8))
    out.putalpha(out.getchannel("A").filter(ImageFilter.GaussianBlur(1.5)))

    bbox = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        out = out.crop(bbox)

    kept = float((np.asarray(out.getchannel("A")) > 8).mean())
    print(f"subject kept: {kept:.1%} of its bounding box")
    if kept > 0.95:
        print("  WARNING: nothing was removed - the rect probably contains only "
              "subject, or the backdrop is inseparable. Check the preview.")
        return 1
    if kept < 0.15:
        print("  WARNING: almost everything was removed - widen --left/--right.")
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    out.save(DEST)
    print(f"-> {DEST.relative_to(ROOT)}  {out.size[0]}x{out.size[1]}")

    prev = ROOT / ".tmp" / "_cut_on_white.png"
    canvas = Image.new("RGBA", out.size, (13, 25, 40, 255))
    canvas.alpha_composite(out)
    canvas.convert("RGB").save(prev)
    print(f"   preview on navy: {prev.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
