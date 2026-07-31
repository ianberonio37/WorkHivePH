#!/usr/bin/env python3
"""
video_camera_motion.py - measure a video's CAMERA (zoom/pan) with optical flow.
===============================================================================
The bbox/centroid tracing in video_reverse_engineer.py sees WHERE content sits
but only coarsely infers how the camera MOVES. This measures it directly, the
way antiboredom/camera-motion-detector does (found via Ian's "get ideas
externally" push, 2026-07-30): dense Farneback optical flow per frame pair,
then decompose the field -

  * ZOOM  = divergence of the flow field: flow pointing radially OUT of the
            centre means the camera is pushing IN (content expands), radially
            IN means pulling OUT. Reported as expansion rate per second.
  * PAN   = the mean flow vector (px/s at the analysis scale).

Output per frame: t, zoom_rate, pan_x, pan_y - and a per-beat summary with
push/pull events (start, duration, peak rate), which is exactly the spec
needed to make a Ken-Burns camera FEEL like the reference instead of merely
existing.

CLI:
    python tools/video_camera_motion.py <video> --start 24 --end 42
    python tools/video_camera_motion.py <video> --start 24 --end 42 --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def measure(path: Path, start: float = 0.0, end: float | None = None,
            fps: float = 10.0, w: int = 320) -> list:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / fps)))
    if start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    idx = int(start * src_fps)
    h = int(w * 9 / 16)

    # radial basis around the centre, for projecting flow onto expansion
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    rx, ry = xs - w / 2, ys - h / 2
    rn = np.sqrt(rx * rx + ry * ry) + 1e-6
    ux, uy = rx / rn, ry / rn
    # ignore the very centre (unstable direction) and the frame edge
    mask = (rn > w * 0.08) & (rn < w * 0.46)

    prev = None
    out = []
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
        idx += 1
        g = cv2.cvtColor(cv2.resize(fr, (w, h)), cv2.COLOR_BGR2GRAY)
        if prev is None:
            prev = g
            continue
        flow = cv2.calcOpticalFlowFarneback(prev, g, None,
                                            0.5, 3, 21, 3, 5, 1.1, 0)
        prev = g
        fx, fy = flow[..., 0], flow[..., 1]
        radial = (fx * ux + fy * uy)[mask]
        # expansion in fraction-of-halfwidth per SECOND: positive = push-in
        zoom_rate = float(np.median(radial)) / (w / 2) * fps
        pan_x = float(np.median(fx[mask])) * fps
        pan_y = float(np.median(fy[mask])) * fps
        out.append({"t": round(t, 2), "zoom": round(zoom_rate, 4),
                    "pan_x": round(pan_x, 1), "pan_y": round(pan_y, 1)})
    cap.release()
    return out


def events(frames: list, thresh: float = 0.02) -> list:
    """Contiguous zoom events: (t0, t1, direction, peak, total-scale-change)."""
    evs, cur = [], None
    for f in frames:
        z = f["zoom"]
        d = "in" if z > thresh else ("out" if z < -thresh else None)
        if cur and d == cur["dir"]:
            cur["t1"] = f["t"]
            cur["peak"] = max(cur["peak"], abs(z))
            cur["integral"] += z
        else:
            if cur and cur["t1"] > cur["t0"]:
                evs.append(cur)
            cur = ({"dir": d, "t0": f["t"], "t1": f["t"],
                    "peak": abs(z), "integral": z} if d else None)
    if cur and cur["t1"] > cur["t0"]:
        evs.append(cur)
    for e in evs:
        e["dur"] = round(e["t1"] - e["t0"], 2)
        # integral of rate*dt approximates ln(scale change)
        e["scale_x"] = round(2.718 ** (e["integral"] / 10), 3)
        del e["integral"]
    return evs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    frames = measure(Path(a.video), a.start, a.end, a.fps)
    evs = events(frames)
    print(f"{len(frames)} flow samples, {len(evs)} zoom events")
    for e in evs:
        print(f"  {e['dir']:>4}  {e['t0']:6.2f}s -> {e['t1']:6.2f}s "
              f"({e['dur']:4.2f}s)  peak {e['peak']:.3f}/s  ~scale x{e['scale_x']}")
    if a.json:
        Path(a.json).write_text(json.dumps({"frames": frames, "events": evs},
                                           indent=2), encoding="utf-8")
        print(f"-> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
