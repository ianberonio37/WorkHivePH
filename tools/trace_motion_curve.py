#!/usr/bin/env python3
"""
trace_motion_curve.py - extract the EXACT animation curve of a screen element.
==============================================================================
Twelve iterations of spring-parameter guessing all failed Ian's eye ("its
still worse"). The springs were always approximations: damping/stiffness pairs
chosen to look like the sample. This stops approximating. For a chosen window
(e.g. one hook word), it tracks the element's geometry PER FRAME at full rate:

    scale   - ink-bbox height relative to its settled value
    x, y    - ink centroid offset from its settled position (fractions)
    sharp   - edge-gradient mean (a monotone proxy for motion-blur amount)
    alpha   - ink coverage relative to settled (a proxy for opacity)

The output is a curve TABLE (one row per frame). The renderer then plays OUR
content through THE SAME table - the sample's actual easing, overshoot, blur
decay and timing, not a spring that resembles them.

CLI:
    python tools/trace_motion_curve.py <video> --start 0.0 --end 0.93 --name word1
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


def trace(path: Path, start: float, end: float) -> list:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    idx = int(start * src_fps)

    rows = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        t = idx / src_fps
        if t > end:
            break
        idx += 1
        small = cv2.resize(fr, (640, 360))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # background from the border ring; ink = departure from it
        border = np.concatenate([gray[:6].ravel(), gray[-6:].ravel(),
                                 gray[:, :6].ravel(), gray[:, -6:].ravel()])
        bg = float(np.median(border))
        ink = np.abs(gray.astype(np.float32) - bg) > 45
        n = int(ink.sum())
        if n < 30:
            rows.append({"t": round(t - start, 4), "empty": True})
            continue
        ys, xs = np.where(ink)
        h = float(ys.max() - ys.min()) / 360.0
        cx = float(xs.mean()) / 640.0
        cy = float(ys.mean()) / 360.0
        # sharpness: mean gradient magnitude on ink edges (blurred = low)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx * gx + gy * gy)
        sharp = float(mag[ink].mean())
        rows.append({"t": round(t - start, 4), "h": round(h, 4),
                     "cx": round(cx, 4), "cy": round(cy, 4),
                     "ink": n, "sharp": round(sharp, 1)})
    cap.release()

    # normalise against the SETTLED state (median of the last third)
    solid = [r for r in rows if not r.get("empty")]
    if len(solid) < 4:
        return rows
    tail = solid[-max(3, len(solid) // 3):]
    import statistics as st
    h0 = st.median(r["h"] for r in tail) or 1e-6
    cx0 = st.median(r["cx"] for r in tail)
    cy0 = st.median(r["cy"] for r in tail)
    ink0 = st.median(r["ink"] for r in tail) or 1
    sharp0 = st.median(r["sharp"] for r in tail) or 1
    out = []
    for r in rows:
        if r.get("empty"):
            out.append({"t": r["t"], "scale": 0, "dx": 0, "dy": 0,
                        "alpha": 0, "blur": 1})
            continue
        out.append({
            "t": r["t"],
            "scale": round(r["h"] / h0, 4),
            "dx": round(r["cx"] - cx0, 4),      # fraction of width
            "dy": round(r["cy"] - cy0, 4),      # fraction of height
            "alpha": round(min(1.0, r["ink"] / ink0), 4),
            "blur": round(max(0.0, 1 - r["sharp"] / sharp0), 4),  # 0 sharp .. 1 mush
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    rows = trace(Path(a.video), a.start, a.end)
    dest = ROOT / ".tmp" / "video_ref" / f"curve_{a.name}.json"
    dest.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"{len(rows)} frames -> {dest.name}")
    for r in rows:
        bar = "#" * int(max(0, min(30, (r["scale"] or 0) * 20)))
        print(f"  t={r['t']:5.3f} scale={r['scale']:6.3f} dx={r['dx']:+.3f} "
              f"dy={r['dy']:+.3f} blur={r['blur']:.2f} {bar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
