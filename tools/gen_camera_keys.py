#!/usr/bin/env python3
"""
gen_camera_keys.py - turn the journey's ACTION LOG into a camera + caption script.
==================================================================================
The recorder logs every click / type / scroll / read with a timestamp, the
viewport-fraction position of the element acted on, and a human CAPTION. Both
the camera moves and the on-screen captions are DERIVED from that one log, so
they can never drift apart.

Camera design, arrived at by correction:
  * v10 synthesized snaps on a timer to hit the reference's zoom COUNT. Ian:
    "chaotic ... not aligned what you are highlighting to ... random and
    erratic." A zoom is a pointing gesture; it needs a real referent.
  * v15 zoomed only at real targets but still gave EVERY action its own
    push+pull, so a form with five fields whipped five times. Ian: "the way
    you zoom in and zoom out like a brainless, you have to be rational."

So the rule now: CLUSTER nearby actions into one intent, aim at the cluster's
centroid, push in ONCE, hold long enough to actually read the screen, and pull
out once. Fewer, slower, shallower, and always pointed at something.

Writes remotion_scenes/src/demoCamera.ts (generated - do not edit).

Usage:
    python tools/gen_camera_keys.py .tmp/demo_journey/journey_<ts>.json \
        --segs "3.9:20,20:18,81:20,110:17,133:13"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

PUSH = 1.55               # a readable crop, not a face-plant
WIDE = 1.0
PUSH_IN_S = 0.30          # deliberate, not a twitch
HOLD_S = 3.2              # stay long enough to read the thing
PULL_OUT_S = 0.45
CLUSTER_S = 5.0           # actions closer than this share ONE zoom
CENTRE_PULL = 0.35        # bias the focal point toward frame centre


def keys_for_segment(steps: list, seg_start: float, seg_dur: float) -> list:
    """Camera keyframes (t, scale, focal-x, focal-y) for one segment window."""
    acts = [s for s in steps
            if s.get("ok") and "x" in s
            and seg_start - 0.2 <= s["at_s"] <= seg_start + seg_dur]

    # cluster consecutive actions that belong to one intent
    clusters: list[list] = []
    for a in acts:
        if clusters and (a["at_s"] - clusters[-1][-1]["at_s"]) < CLUSTER_S:
            clusters[-1].append(a)
        else:
            clusters.append([a])

    keys = [(0.0, WIDE, 0.5, 0.5)]
    for c in clusters:
        t = max(0.15, c[0]["at_s"] - seg_start)
        t_last = c[-1]["at_s"] - seg_start
        # aim at the cluster CENTROID: one stable frame containing every
        # action in the intent, rather than chasing each element in turn
        fx = sum(a["x"] for a in c) / len(c)
        fy = sum(a["y"] for a in c) / len(c)
        fx += (0.5 - fx) * CENTRE_PULL
        fy += (0.5 - fy) * CENTRE_PULL

        t_in = max(0.0, t - PUSH_IN_S)
        if t_in <= keys[-1][0] + 0.25:
            keys.append((t, PUSH, fx, fy))          # retarget, don't bounce
        else:
            keys.append((t_in, WIDE, keys[-1][2], keys[-1][3]))
            keys.append((t, PUSH, fx, fy))
        t_end = max(t + HOLD_S, t_last + 1.4)       # hold across the cluster
        keys.append((min(seg_dur - 0.3, t_end), PUSH, fx, fy))
        keys.append((min(seg_dur - 0.1, t_end + PULL_OUT_S), WIDE, fx, fy))

    if keys[-1][1] != WIDE:
        keys.append((seg_dur, WIDE, keys[-1][2], keys[-1][3]))

    out, last_t = [], -1.0
    for t, s, fx, fy in keys:
        t = max(t, last_t + 0.05)
        out.append({"t": round(t, 2), "s": s, "fx": round(fx, 3), "fy": round(fy, 3)})
        last_t = t
    return out


def captions_for_segment(steps: list, seg_start: float, seg_dur: float) -> list:
    """Non-overlapping captions for one segment, from the same action log."""
    caps, last_end = [], -99.0
    for a in steps:
        if not a.get("caption") or not a.get("ok"):
            continue
        t = a["at_s"] - seg_start
        if t < -0.4 or t > seg_dur:
            continue
        t = max(0.0, t)
        if t < last_end - 0.2:                      # never stack captions
            continue
        dur = min(3.4, max(2.0, len(a["caption"]) * 0.055))
        dur = min(dur, seg_dur - t)
        if dur < 0.8:
            continue
        caps.append({"t": round(t, 2), "d": round(dur, 2), "text": a["caption"]})
        last_end = t + dur
    return caps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sidecar")
    ap.add_argument("--segs", required=True,
                    help="comma list of start:dur for each Remotion segment")
    a = ap.parse_args()

    steps = json.loads(Path(a.sidecar).read_text(encoding="utf-8"))["steps"]
    segs = []
    for part in a.segs.split(","):
        st, du = part.split(":")
        segs.append((float(st), float(du)))

    all_keys = [keys_for_segment(steps, st, du) for st, du in segs]
    all_caps = [captions_for_segment(steps, st, du) for st, du in segs]

    ts = ("// GENERATED by tools/gen_camera_keys.py - do not edit.\n"
          "// Camera moves AND captions, both derived from the recorder's own\n"
          "// action log, so a caption can never describe a moment the edit\n"
          "// no longer contains.\n"
          "export type CamKey = {t: number; s: number; fx: number; fy: number};\n"
          f"export const CAMERA_KEYS: CamKey[][] = {json.dumps(all_keys)};\n"
          "export type Caption = {t: number; d: number; text: string};\n"
          f"export const CAPTIONS: Caption[][] = {json.dumps(all_caps)};\n")
    dest = ROOT / "remotion_scenes" / "src" / "demoCamera.ts"
    dest.write_text(ts, encoding="utf-8")

    n = sum(len(k) for k in all_keys)
    c = sum(len(k) for k in all_caps)
    print(f"-> {dest.name}: {len(all_keys)} segments, {n} keyframes, {c} captions")
    for i, k in enumerate(all_keys):
        pushes = sum(1 for x in k if x["s"] > 1.0)
        print(f"  seg{i}: {len(k)} keys, {pushes} pushed, {len(all_caps[i])} captions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
