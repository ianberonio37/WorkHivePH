#!/usr/bin/env python3
"""
find_mascot.py - locate a mascot image Ian saved anywhere obvious, and stage it.
===============================================================================
Ian saves the mascot from a chat image, which lands wherever the browser's
"save image as" dialog last pointed - Downloads, Desktop, Pictures, or the
project folder - under whatever name it suggested. Asking him to hit an exact
path is friction he has already had to repeat once.

So: sweep the likely locations for a RECENT image that looks like a character
render, rank the candidates, and stage the best one to
brand_assets/mascot-bee.png (never overwriting an existing file without
--force). Then tools/prep_mascot.py cuts it out for the video.

"Looks like a mascot" is scored, not guessed:
  * recency          - saved in the last few hours beats an old asset
  * name hints       - mascot / bee / workhive in the filename
  * aspect + size    - a character render is tall-ish and reasonably large
  * NOT a screenshot - "Screenshot ...", .playwright, test-results are excluded

CLI:
    python tools/find_mascot.py                 # report candidates
    python tools/find_mascot.py --stage         # copy the best one into place
    python tools/find_mascot.py --stage --force
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "brand_assets" / "mascot-bee.png"
HOME = Path.home()

SEARCH_DIRS = [
    HOME / "Downloads", HOME / "Desktop", HOME / "Pictures",
    HOME / "Pictures" / "Screenshots", HOME / "OneDrive" / "Pictures",
    ROOT / "brand_assets", ROOT,
]
EXTS = {".png", ".jpg", ".jpeg", ".webp"}
EXCLUDE_PARTS = {"node_modules", ".git", "test-results", ".playwright-mcp",
                 "_out", "temporary screenshots", "test-images", ".tmp"}


def score(p: Path) -> tuple[float, str]:
    """Higher is more likely to be the mascot. Returns (score, why)."""
    try:
        st = p.stat()
    except OSError:
        return (-1, "unreadable")
    age_h = (time.time() - st.st_mtime) / 3600.0
    name = p.name.lower()

    if name.startswith("screenshot") or "screen shot" in name:
        return (-1, "screenshot")
    if st.st_size < 40_000:
        return (-1, "too small")

    s, why = 0.0, []
    if age_h < 6:
        s += 60; why.append("saved in the last 6h")
    elif age_h < 48:
        s += 25; why.append("saved in the last 2 days")

    for hint, pts in (("mascot", 45), ("bee", 30), ("workhive", 15)):
        if hint in name:
            s += pts; why.append(f"name has '{hint}'")

    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
        if w >= 500 and h >= 500:
            s += 15; why.append(f"{w}x{h}")
        ar = w / h if h else 99
        if 0.45 <= ar <= 1.35:          # a standing character, or a poster
            s += 20; why.append("character-ish aspect")
        if im_has_alpha := (Image.open(p).mode in ("RGBA", "LA")):
            s += 20; why.append("has alpha")
    except Exception:
        return (-1, "not a readable image")
    return (s, ", ".join(why) or "no signals")


def candidates() -> list:
    seen, out = set(), []
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        depth = 1 if d == ROOT else 3
        for p in d.rglob("*"):
            if p in seen or not p.is_file() or p.suffix.lower() not in EXTS:
                continue
            if any(part in EXCLUDE_PARTS for part in p.parts):
                continue
            if len(p.relative_to(d).parts) > depth:
                continue
            seen.add(p)
            sc, why = score(p)
            if sc > 0:
                out.append((sc, p, why))
    return sorted(out, key=lambda t: -t[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    cands = candidates()
    if not cands:
        print("No mascot-like image found.\n"
              f"Save it anywhere in Downloads/Desktop/Pictures, or directly to:\n"
              f"  {DEST}")
        return 1

    print(f"{len(cands)} candidate(s), best first:")
    for sc, p, why in cands[:6]:
        try:
            rel = p.relative_to(HOME)
            shown = f"~/{rel}"
        except ValueError:
            shown = str(p)
        print(f"  [{sc:5.0f}] {shown}\n           {why}")

    if not a.stage:
        print("\nRe-run with --stage to copy the best one to brand_assets/mascot-bee.png")
        return 0

    best = cands[0][1]
    if DEST.exists() and not a.force:
        print(f"\n{DEST.name} already exists - pass --force to replace it.")
        return 1
    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best, DEST)
    print(f"\nstaged {best.name} -> {DEST.relative_to(ROOT)}")
    print("next: python tools/prep_mascot.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
