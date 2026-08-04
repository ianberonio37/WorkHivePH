#!/usr/bin/env python3
"""
render_mascot_svg.py - render the WorkHive bee mascot to a transparent PNG.
===========================================================================
Ian asked for the mascot in the video. He shared a 3D render in chat, which is
not on disk - but the project already OWNS a mascot: the vector bee in
`promo_posters/bee.js` (`<symbol id="bee-mascot" viewBox="0 0 300 340">`),
the same character the promo posters use.

Vector beats bitmap here: rendering the symbol in a headless browser with
`omit_background` gives a genuinely transparent, arbitrarily large PNG with
clean edges - no keying, no matte artefacts, no halo. That is strictly better
than cutting a character out of a finished poster.

When the 3D render is saved to `brand_assets/mascot-bee.png`, swap it in with
`tools/prep_mascot.py`; both write the same destination, so the video does not
change shape - only the artwork does.

CLI:
    python tools/render_mascot_svg.py                 # 900px tall
    python tools/render_mascot_svg.py --height 1400 --symbol bee-mini
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEE_JS = ROOT / "promo_posters" / "bee.js"
DEST = ROOT / "remotion_scenes" / "public" / "mascot-cut.png"

VIEWBOX = {"bee-mascot": (300, 340), "bee-mini": (120, 100)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="bee-mascot", choices=sorted(VIEWBOX))
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--dest", default=str(DEST))
    a = ap.parse_args()

    if not BEE_JS.exists():
        print(f"missing {BEE_JS}")
        return 1

    vw, vh = VIEWBOX[a.symbol]
    w = int(a.height * vw / vh)
    js = BEE_JS.read_text(encoding="utf-8")

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body {{ margin:0; padding:0; background:transparent; }}
  #stage {{ width:{w}px; height:{a.height}px; }}
  #stage svg.bee {{ width:100%; height:100%; display:block; }}
</style></head><body>
<div id="stage"><svg class="bee" viewBox="0 0 {vw} {vh}">
  <use href="#{a.symbol}"/></svg></div>
<script>{js}</script>
</body></html>"""

    tmp = ROOT / ".tmp" / "_mascot_render.html"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(html, encoding="utf-8")

    from playwright.sync_api import sync_playwright
    dest = Path(a.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        page = br.new_page(viewport={"width": w, "height": a.height},
                           device_scale_factor=2)
        page.goto(tmp.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(600)
        # omit_background is what makes the alpha real rather than keyed
        page.locator("#stage").screenshot(path=str(dest), omit_background=True)
        br.close()

    # verify the alpha actually survived - a fully opaque PNG means the
    # transparent-background path silently failed, and it would composite as
    # a white box over the video.
    from PIL import Image
    import numpy as np
    im = Image.open(dest).convert("RGBA")
    alpha = np.asarray(im.getchannel("A"))
    clear = float((alpha < 8).mean())
    print(f"-> {dest.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  "
          f"transparent: {clear:.1%}")
    if clear < 0.05:
        print("  ERROR: almost no transparency - the mascot would composite "
              "as a solid rectangle. Not usable.")
        return 1
    # trim to the drawn character so placement maths is about the BEE, not
    # about whatever padding the symbol's viewBox happened to carry
    bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        im.crop(bbox).save(dest)
        print(f"  trimmed to content: {bbox[2]-bbox[0]}x{bbox[3]-bbox[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
