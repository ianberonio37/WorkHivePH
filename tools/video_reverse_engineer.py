#!/usr/bin/env python3
"""
video_reverse_engineer.py - extract an IMPLEMENTABLE spec from a reference video.
=================================================================================
`video_reference_study.py` answers "what shape is this video" - duration, aspect,
shot count, loudness, a contact sheet. That is a SUMMARY, and a summary is not
enough to rebuild something: working only from one, I produced static cards with
a fade against full-bleed footage, while the reference uses motion-blurred word
transitions, 3D device reveals, camera push-ins and inset/rounded/shadowed
product shots. Ian, correctly: "you didn't fully reverse engineer" it.

So this measures, per frame, the things you must KNOW to reproduce a look:

  * background colour     - sampled from the border, so page chrome does not
                            skew it. Reveals the palette and every card/footage
                            boundary.
  * frame class           - CARD (flat background + a little ink) vs PRODUCT
                            (busy) vs TRANSITION, from ink coverage + edge
                            density.
  * content bounding box  - for product frames, the non-background region. This
                            is the treatment spec: inset %, whether the shot is
                            full-bleed or floated, and how it is positioned.
  * motion energy         - mean abs frame-to-frame difference. Holds, pushes,
                            scatters and whips each have a distinct signature;
                            a static card and a slow zoom are not the same curve.
  * text ink + centroid   - where type sits in the frame and how much of it there
                            is, which is the typography/layout spec.

Output: beats.json (a real beat map with measured boundaries) + a printed spec.

CLI:
    python tools/video_reverse_engineer.py ".tmp/video_ref/Video Marketing.mp4"
    python tools/video_reverse_engineer.py <video> --fps 4
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from video_reference_study import probe                          # noqa: E402


def analyse(path: Path, fps: float = 4.0, start: float = 0.0,
            end: float | None = None) -> dict:
    """start/end bound the scan (seconds). A whole-video pass at 4fps gives
    the beat map; a WINDOWED pass at 12-15fps gives motion TRAJECTORIES -
    the actual zoom curve of a product beat, the actual path of a word."""
    import cv2
    import numpy as np

    meta = probe(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / fps)))
    frames = []
    prev_small = None
    idx = 0

    if start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        idx = int(start * src_fps)
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        t = idx / src_fps
        if end is not None and t > end:
            break
        if idx % step:
            idx += 1
            continue
        small = cv2.resize(fr, (320, 180))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # BACKGROUND from the border ring - the interior is content, the border
        # is (almost always) the backdrop.
        border = np.concatenate([
            small[0:6, :, :].reshape(-1, 3), small[-6:, :, :].reshape(-1, 3),
            small[:, 0:6, :].reshape(-1, 3), small[:, -6:, :].reshape(-1, 3)])
        bg = border.reshape(-1, 3).mean(axis=0)          # BGR
        bg_rgb = (int(bg[2]), int(bg[1]), int(bg[0]))
        bg_lum = float(0.299 * bg[2] + 0.587 * bg[1] + 0.114 * bg[0])

        # INK = pixels that differ from the background. On a card this is the
        # type; on product footage it is the whole UI.
        diff = np.abs(small.astype(np.int16) - bg.astype(np.int16)).sum(axis=2)
        ink = diff > 60
        ink_frac = float(ink.mean())

        # EDGE DENSITY separates "a few big glyphs" from "a dense UI".
        edges = cv2.Canny(gray, 60, 160)
        edge_frac = float((edges > 0).mean())

        # CONTENT BBOX - the treatment spec. Full-bleed vs floated/inset.
        bbox = None
        ys, xs = np.where(ink)
        if len(xs) > 40:
            x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
            bbox = {"x0": x0 / 320, "x1": x1 / 320, "y0": y0 / 180, "y1": y1 / 180}
            bbox["w"] = bbox["x1"] - bbox["x0"]
            bbox["h"] = bbox["y1"] - bbox["y0"]
            # centroid of ink = where the type/content sits
            bbox["cx"] = float(xs.mean()) / 320
            bbox["cy"] = float(ys.mean()) / 180

        motion = None
        if prev_small is not None:
            motion = float(np.abs(gray.astype(np.int16) -
                                  prev_small.astype(np.int16)).mean())
        prev_small = gray

        frames.append({
            "t": round(t, 2), "bg": bg_rgb, "bg_lum": round(bg_lum, 1),
            "ink": round(ink_frac, 4), "edge": round(edge_frac, 4),
            "motion": None if motion is None else round(motion, 2),
            "bbox": bbox,
        })
        idx += 1
    cap.release()

    for f in frames:
        # A CARD is a flat backdrop carrying a little type: low ink, low edges.
        # PRODUCT footage is dense with UI edges. Thresholds are set from the
        # observed bimodal split, not guessed.
        if f["ink"] < 0.10 and f["edge"] < 0.030:
            f["cls"] = "card"
        elif f["edge"] > 0.055 or f["ink"] > 0.35:
            f["cls"] = "product"
        else:
            f["cls"] = "mixed"

    return {"meta": meta, "fps_sampled": fps, "frames": frames}


def segment(frames: list, min_len: float = 0.6) -> list:
    """Group consecutive same-class frames into beats, then describe each."""
    beats, cur = [], None
    for f in frames:
        if cur and f["cls"] == cur["cls"]:
            cur["frames"].append(f)
            cur["end"] = f["t"]
        else:
            if cur:
                beats.append(cur)
            cur = {"cls": f["cls"], "start": f["t"], "end": f["t"], "frames": [f]}
    if cur:
        beats.append(cur)

    merged = []
    for b in beats:
        b["dur"] = round(b["end"] - b["start"], 2)
        if merged and b["dur"] < min_len and merged[-1]["cls"] != b["cls"]:
            merged[-1]["frames"].extend(b["frames"])
            merged[-1]["end"] = b["end"]
            merged[-1]["dur"] = round(merged[-1]["end"] - merged[-1]["start"], 2)
        else:
            merged.append(b)

    for b in merged:
        fr = b["frames"]
        mot = [f["motion"] for f in fr if f["motion"] is not None]
        bgs = Counter(tuple(f["bg"]) for f in fr)
        b["bg_mode"] = list(bgs.most_common(1)[0][0])
        b["bg_lum"] = round(sum(f["bg_lum"] for f in fr) / len(fr), 1)
        b["motion_mean"] = round(sum(mot) / len(mot), 2) if mot else 0.0
        b["motion_max"] = round(max(mot), 2) if mot else 0.0
        boxes = [f["bbox"] for f in fr if f["bbox"]]
        if boxes:
            b["bbox_mean"] = {k: round(sum(bx[k] for bx in boxes) / len(boxes), 3)
                              for k in ("x0", "x1", "y0", "y1", "w", "h", "cx", "cy")}
        b["ink_mean"] = round(sum(f["ink"] for f in fr) / len(fr), 4)
        del b["frames"]
    return merged


def report(res: dict, beats: list) -> None:
    m = res["meta"]
    print("\n" + "=" * 74)
    print(f"REVERSE-ENGINEERED SPEC - {m.get('name')}")
    print("=" * 74)
    print(f"  {m.get('duration_s')}s  {m.get('width')}x{m.get('height')}  "
          f"{m.get('aspect_label')}  {m.get('fps')}fps")

    cards = [b for b in beats if b["cls"] == "card"]
    prod = [b for b in beats if b["cls"] == "product"]
    print(f"\n  beats: {len(beats)}   cards: {len(cards)}   product: {len(prod)}")
    if cards:
        print(f"  card duration   : min {min(b['dur'] for b in cards):.2f}s  "
              f"max {max(b['dur'] for b in cards):.2f}s  "
              f"mean {sum(b['dur'] for b in cards)/len(cards):.2f}s")
    if prod:
        print(f"  product duration: min {min(b['dur'] for b in prod):.2f}s  "
              f"max {max(b['dur'] for b in prod):.2f}s  "
              f"mean {sum(b['dur'] for b in prod)/len(prod):.2f}s")

    bgs = Counter(tuple(b["bg_mode"]) for b in beats)
    print("\n  BACKGROUND palette (mode per beat):")
    for c, n in bgs.most_common(6):
        print(f"    rgb{c}  #{c[0]:02X}{c[1]:02X}{c[2]:02X}   {n} beats")

    print("\n  PRODUCT-SHOT TREATMENT (content bbox as fraction of frame):")
    pb = [b for b in prod if b.get("bbox_mean")]
    if pb:
        w = sum(b["bbox_mean"]["w"] for b in pb) / len(pb)
        h = sum(b["bbox_mean"]["h"] for b in pb) / len(pb)
        x0 = sum(b["bbox_mean"]["x0"] for b in pb) / len(pb)
        y0 = sum(b["bbox_mean"]["y0"] for b in pb) / len(pb)
        print(f"    mean content w={w:.3f}  h={h:.3f}   inset left={x0:.3f} top={y0:.3f}")
        print(f"    => {'FULL-BLEED' if w > 0.95 and h > 0.95 else 'INSET/FLOATED'}"
              f"  (side margin {x0*100:.1f}%, top margin {y0*100:.1f}%)")

    print("\n  TYPE PLACEMENT on cards (ink centroid, fraction of frame):")
    cb = [b for b in cards if b.get("bbox_mean")]
    if cb:
        cy = sum(b["bbox_mean"]["cy"] for b in cb) / len(cb)
        ch = sum(b["bbox_mean"]["h"] for b in cb) / len(cb)
        ink = sum(b["ink_mean"] for b in cb) / len(cb)
        print(f"    centroid y={cy:.3f} (0=top,1=bottom)   glyph band h={ch:.3f}"
              f"   ink coverage {ink*100:.2f}%")

    print("\n  BEAT MAP")
    print(f"    {'#':>3} {'t':>7} {'dur':>6} {'class':<8} {'motion':>7} {'bg':>16}  inset")
    for i, b in enumerate(beats):
        bb = b.get("bbox_mean")
        inset = (f"w={bb['w']:.2f} h={bb['h']:.2f} y0={bb['y0']:.2f}" if bb else "-")
        c = tuple(b["bg_mode"])
        print(f"    {i:>3} {b['start']:>7.2f} {b['dur']:>6.2f} {b['cls']:<8} "
              f"{b['motion_mean']:>7.2f} #{c[0]:02X}{c[1]:02X}{c[2]:02X}{'':>9}  {inset}")
    print("=" * 74 + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    src = Path(a.video)
    res = analyse(src, fps=a.fps)
    beats = segment(res["frames"])
    report(res, beats)

    dest = Path(a.out) if a.out else (ROOT / ".tmp" / "video_ref" /
                                      f"{src.stem}_spec.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"meta": res["meta"], "beats": beats,
                                "frames": res["frames"]}, indent=2), encoding="utf-8")
    print(f"  spec -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
