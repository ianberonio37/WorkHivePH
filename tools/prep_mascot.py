#!/usr/bin/env python3
"""
prep_mascot.py - cut the WorkHive bee mascot out of its poster background for video use.
==============================================================================
Ian supplied a 3D-rendered mascot (hard hat, hi-vis, holding a phone) as a full
POSTER: the character sits in a factory scene with a headline panel on the left.
Dropping that whole image into the reel would paste a second, competing layout
on top of the video.

So this isolates the character:
  * detect the character band (the poster's left third is the text panel, the
    right side is the phone/backdrop) and crop to the subject
  * build an alpha matte by flood-filling the background from the frame edges
    in LAB space, which survives the gradient factory backdrop far better than
    a single-colour key
  * feather the matte 2px so the composite does not read as a sticker
  * trim to content and write a 4-channel PNG the renderer can place anywhere

Writes remotion_scenes/public/mascot-cut.png.

CLI:
    python tools/prep_mascot.py                       # uses brand_assets/mascot-bee.png
    python tools/prep_mascot.py --src <path> --left 0.30 --right 0.78
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
    ap.add_argument("--left", type=float, default=0.24,
                    help="left crop as a fraction of width (skip the text panel)")
    ap.add_argument("--right", type=float, default=0.80,
                    help="right crop as a fraction of width (skip the phone)")
    ap.add_argument("--tol", type=float, default=26.0,
                    help="background match tolerance in LAB units")
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"No mascot at {src}.\n"
              f"Save the image Ian shared to that path (or pass --src) and re-run.")
        return 1

    import numpy as np
    from PIL import Image, ImageFilter
    import cv2

    im = Image.open(src).convert("RGB")
    W, H = im.size
    x0, x1 = int(W * a.left), int(W * a.right)
    im = im.crop((x0, 0, x1, H))
    arr = np.asarray(im)

    # Background estimate from the frame border, in LAB (perceptually even, so
    # one tolerance works across the dark factory gradient).
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    band = np.concatenate([lab[:8].reshape(-1, 3), lab[-8:].reshape(-1, 3),
                           lab[:, :8].reshape(-1, 3), lab[:, -8:].reshape(-1, 3)])
    bg = np.median(band, axis=0)
    dist = np.linalg.norm(lab - bg, axis=2)

    # Seeded flood from the edges: only background CONNECTED to the border is
    # removed, so dark parts of the character (boots, visor) are not punched out.
    seed = (dist < a.tol).astype(np.uint8)
    ff = np.zeros((h + 2, w + 2), np.uint8)
    filled = seed.copy()
    for pt in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
               (w // 2, 0), (w // 2, h - 1)]:
        if seed[pt[1], pt[0]]:
            cv2.floodFill(filled, ff, pt, 2)
    alpha = np.where(filled == 2, 0, 255).astype(np.uint8)

    # clean specks, then feather so it composites instead of stickering
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, k)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, k)
    out = Image.fromarray(np.dstack([arr, alpha]).astype(np.uint8), "RGBA")
    out.putalpha(out.getchannel("A").filter(ImageFilter.GaussianBlur(1.6)))

    bbox = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        out = out.crop(bbox)

    kept = (np.asarray(out.getchannel("A")) > 8).mean()
    print(f"subject kept: {kept:.1%} of the cropped frame")
    if kept > 0.97:
        print("  WARNING: almost nothing was removed - the backdrop may not be "
              "separable by colour. Try a tighter --left/--right or raise --tol.")
    elif kept < 0.05:
        print("  WARNING: almost everything was removed - lower --tol.")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    out.save(DEST)
    print(f"-> {DEST.relative_to(ROOT)}  {out.size[0]}x{out.size[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
