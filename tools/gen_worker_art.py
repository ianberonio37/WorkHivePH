#!/usr/bin/env python3
"""
gen_worker_art.py - generate the WorkHive worker + AI-companion CHARACTER art with a
FREE image model (Ian 2026-07-02: "use AI to render an animation about the worker";
the geometric Pillow character was too crude; "together ai needs payment, remove it").

Provider: Pollinations.ai FLUX - genuinely FREE, NO key, NO account, NO payment (a
plain HTTP GET; it only needs a browser User-Agent, which was the earlier 403). This
honours feedback_free_tier_only_models AND feedback_build_own_minimal_dependencies
(no SDK, no key to manage). The image comes back on a flat dark background, so we
flood-remove that background to a TRANSPARENT PNG for clean compositing over the
video's own navy gradient.

Saves each pose to remotion_scenes/public/worker_<name>.png (a reusable brand asset,
same folder as the wh_*_clean screenshots). The video engine (explainer_studio.
_companion_art) then composites + animates these: the AI renders the WORKER, our
pure-Python engine renders the MOTION.

Usage:
    python tools/gen_worker_art.py                 # generate the default poses
    python tools/gen_worker_art.py --poses cheer   # just one pose
"""
from __future__ import annotations
import io, os, sys, argparse, urllib.request, urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "remotion_scenes" / "public"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# One consistent mascot across poses (brand identity). Flat dark bg so it flood-keys
# cleanly; the ac-cent palette matches the brand (navy / orange / sky-blue).
STYLE = ("cute friendly cartoon mascot, flat vector style, thick clean outlines, "
         "Filipino industrial maintenance worker, bright orange hard hat, orange shirt, navy overalls, "
         "a small cute robot AI companion with a glowing sky-blue core floating beside him, "
         "isolated character on a solid flat dark navy background, centered, full body, "
         "no text, no words, no letters, no logo")

POSES = {
    "cheer":  "confident happy worker giving a thumbs up, robot companion glowing happily, " + STYLE,
    "think":  "worker looking thoughtful and puzzled with a hand on his chin trying to remember, " + STYLE,
    "assist": "the robot companion shows a glowing holographic memory card to the worker who looks relieved, " + STYLE,
}


def _fetch(prompt: str, seed: int) -> bytes:
    u = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
         + f"?width=768&height=896&nologo=true&model=flux&seed={seed}")
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()


def _cutout(data: bytes) -> Image.Image:
    """Flood-remove the flat background (from the borders) -> transparent RGBA."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    W, H = im.size
    MARK = (255, 0, 255)
    seeds = [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1),
             (W // 2, 0), (W // 2, H - 1), (0, H // 2), (W - 1, H // 2)]
    for xy in seeds:
        ImageDraw.floodfill(im, xy, MARK, thresh=46)
    im = im.convert("RGBA")
    px = im.load()
    for y in range(H):
        for x in range(W):
            if px[x, y][:3] == MARK:
                px[x, y] = (0, 0, 0, 0)
    return im.crop(im.getbbox() or (0, 0, W, H))


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate WorkHive worker+AI character art (free Pollinations FLUX).")
    ap.add_argument("--poses", default="", help="comma list subset of: " + ",".join(POSES))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    want = [p.strip() for p in args.poses.split(",") if p.strip()] or list(POSES)
    OUT.mkdir(parents=True, exist_ok=True)
    fails = 0
    for i, name in enumerate(want):
        if name not in POSES:
            print(f"  skip unknown pose '{name}'"); continue
        try:
            img = _cutout(_fetch(POSES[name], args.seed + i))
            p = OUT / f"worker_{name}.png"
            img.save(p)
            print(f"  SAVED {p.relative_to(ROOT)}  {img.size}  (transparent)")
        except Exception as e:
            print(f"  FAIL {name}: {type(e).__name__} {str(e)[:150]}"); fails += 1
    print("done." if not fails else f"done with {fails} failure(s).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
