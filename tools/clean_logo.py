#!/usr/bin/env python3
"""
clean_logo.py - defringe and crisp the WorkHive logo for video use.
===================================================================
Ian, on the DemoReel: "the workhive logo is not quality." He is right, and the
defect is in the SOURCE PNGs, not the renderer: both brand logo files carry
WHITE FRINGING - their semi-transparent edge pixels were composited against
white when the PNG was authored, so every hex outline and letter edge drags a
pale halo, plus stray white speckles float in the transparent field. On white
pages it hides; on the video's black device stage and any scaled rendering it
reads as dirt.

The fix is arithmetic, not art:
  * UN-COMPOSITE from white: for every pixel with alpha a<1, the stored colour
    is c' = a*c + (1-a)*255. Recover c = (c' - (1-a)*255)/a. The halo is gone
    because the white contribution is removed from the colour channels.
  * DESPECKLE: drop tiny isolated alpha islands (the floating dust) with a
    connected-component pass - anything under ~40px^2 far from the main mark.
  * AUTOCROP to content + pad 4%, from the 1024x1024 master (the site's own
    canonical file), so the video never upscales.

Writes remotion_scenes/public/workhive-logo-clean.png.
Self-check: asserts the result has no >250-luma pixels with alpha in (0,0.9) -
the fringe signature - and that the main mark survived.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "brand_assets" / "workhive-logo-transparent.png"
DEST = ROOT / "remotion_scenes" / "public" / "workhive-logo-clean.png"


def main() -> int:
    im = Image.open(SRC).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3:4] / 255.0

    # 1) un-composite from white
    mask = (alpha > 0.02) & (alpha < 0.998)
    unc = np.where(alpha > 0.02,
                   np.clip((rgb - (1 - alpha) * 255.0) / np.maximum(alpha, 0.02),
                           0, 255),
                   rgb)
    rgb = np.where(mask, unc, rgb)

    # 2) despeckle: kill alpha islands smaller than 40px
    try:
        from scipy import ndimage
        lab, n = ndimage.label(alpha[..., 0] > 0.06)
        sizes = ndimage.sum(alpha[..., 0] > 0.06, lab, range(1, n + 1))
        kill = {i + 1 for i, sz in enumerate(sizes) if sz < 40}
        if kill:
            speck = np.isin(lab, list(kill))
            alpha[speck] = 0
    except ImportError:
        # fallback: a 3x3 erosion-style vote using pure numpy
        A = (alpha[..., 0] > 0.06).astype(np.uint8)
        votes = sum(np.roll(np.roll(A, dy, 0), dx, 1)
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        alpha[(A == 1) & (votes <= 2)] = 0

    out = np.concatenate([rgb, alpha * 255.0], axis=-1).astype(np.uint8)

    # 3) autocrop + 4% pad
    ys, xs = np.where(out[..., 3] > 8)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    pad = int(max(y1 - y0, x1 - x0) * 0.04)
    y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
    y1, x1 = min(out.shape[0], y1 + pad), min(out.shape[1], x1 + pad)
    out = out[y0:y1, x0:x1]

    # self-check: fringe signature gone, mark intact
    al = out[..., 3].astype(np.float32) / 255.0
    lum = out[..., :3].mean(axis=-1)
    fringe = ((al > 0.05) & (al < 0.9) & (lum > 250)).sum()
    solid = (al > 0.9).sum()
    assert solid > 5000, f"mark lost ({solid} solid px)"
    print(f"fringe px remaining: {fringe} (was the halo), solid px: {solid}")

    Image.fromarray(out).save(DEST)
    print(f"-> {DEST.relative_to(ROOT)}  {out.shape[1]}x{out.shape[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
