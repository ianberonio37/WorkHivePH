#!/usr/bin/env python3
"""
video_compare.py - the COMPREHENSIVE study: sample vs ours, axis by axis.
=========================================================================
Ian, 2026-07-30: "you haven't maximized PySceneDetect... do a comprehensive
study of the sample video, then compare it to ours using the ideas we got
from outside sources and tools."

One battery, run on BOTH videos, producing a measured comparison instead of
another taste-driven iteration. Instruments (each already proven separately):

  * PySceneDetect AdaptiveDetector  - the authoritative cut list
  * per-frame classifier (6fps)     - card/product/mixed, bg palette, ink
                                      (video_reverse_engineer.analyse)
  * optical-flow camera (8fps)      - zoom events: count, depth, duration
                                      (video_camera_motion)
  * audio onset alignment           - % of cuts landing within 120ms of an
                                      audio onset: the cut-on-the-beat craft
                                      metric professional editors optimize
  * loudness / bpm / brightness     - audio character (video_reference_study)

Output: per-video profile JSONs + a printed gap table with verdicts.

CLI:
    python tools/video_compare.py <sample> <ours> [--json out.json]
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

from video_reference_study import probe, loudness, _decode_audio_16k   # noqa: E402
from video_reverse_engineer import analyse                             # noqa: E402
from video_camera_motion import measure as cam_measure, events as cam_events  # noqa: E402


def scenes_of(path: Path) -> list:
    from scenedetect import detect, AdaptiveDetector
    return [{"start": round(a.get_seconds(), 2), "end": round(b.get_seconds(), 2),
             "dur": round(b.get_seconds() - a.get_seconds(), 2)}
            for a, b in detect(str(path), AdaptiveDetector())]


def onsets_of(path: Path) -> list:
    """Audio onset times from the energy envelope - local peaks that jump
    >25% above the local floor. Crude next to librosa, but stable, and all
    the cut-alignment metric needs is peak TIMES."""
    import numpy as np
    a = _decode_audio_16k(path)
    hop = 512                                    # 32ms
    env = np.abs(a[:len(a) // hop * hop]).reshape(-1, hop).mean(1)
    if len(env) < 8:
        return []
    floor = np.convolve(env, np.ones(31) / 31, mode="same")
    on = []
    for i in range(2, len(env) - 2):
        if (env[i] > env[i - 1] and env[i] >= env[i + 1]
                and env[i] > floor[i] * 1.25):
            t = i * hop / 16000
            if not on or t - on[-1] > 0.12:
                on.append(round(t, 3))
    return on


def profile(path: Path) -> dict:
    print(f"  profiling {path.name} ...")
    meta = probe(path)
    dur = meta.get("duration_s") or 0
    sc = scenes_of(path)
    fr = analyse(path, fps=6.0)["frames"]
    cam = cam_measure(path, 0, dur, fps=8.0)
    cev = cam_events(cam)
    loud = loudness(path)
    ons = onsets_of(path) if meta.get("has_audio") else []

    # classify each scene from the frames inside it
    for s in sc:
        inside = [f for f in fr if s["start"] <= f["t"] < s["end"]]
        cls = Counter(f["cls"] for f in inside)
        s["cls"] = cls.most_common(1)[0][0] if cls else "?"
        mot = [f["motion"] for f in inside if f["motion"] is not None]
        s["motion"] = round(sum(mot) / len(mot), 1) if mot else 0.0

    cuts = [s["start"] for s in sc[1:]]
    onbeat = sum(1 for c in cuts if any(abs(c - o) <= 0.12 for o in ons))

    card = [s for s in sc if s["cls"] == "card"]
    prod = [s for s in sc if s["cls"] == "product"]
    micro = [s for s in sc if s["dur"] < 1.0]
    zooms = [e for e in cev if e["dur"] >= 0.1]

    return {
        "name": path.name, "duration": dur,
        "scenes": len(sc), "scene_list": sc,
        "card_scenes": len(card), "product_scenes": len(prod),
        "micro_scenes": len(micro),
        "longest_product_s": max((s["dur"] for s in prod), default=0),
        "card_motion_mean": round(sum(s["motion"] for s in card) / len(card), 1) if card else 0,
        "zoom_events": len(zooms),
        "zoom_depths": [e["scale_x"] for e in zooms],
        "zoom_durs": [e["dur"] for e in zooms],
        "cuts": len(cuts), "cuts_on_beat": onbeat,
        "cut_beat_pct": round(100 * onbeat / len(cuts), 1) if cuts else 0,
        "lufs": loud.get("integrated_lufs"),
        "onsets": len(ons),
    }


def row(label, a, b, verdict=""):
    print(f"  {label:<28} {str(a):>16} {str(b):>16}   {verdict}")


def compare(pa: dict, pb: dict) -> list:
    print("\n" + "=" * 78)
    print(f"  {'AXIS':<28} {'SAMPLE':>16} {'OURS':>16}")
    print("-" * 78)
    gaps = []

    def check(label, a, b, ok, fix=""):
        verdict = "match" if ok else f"GAP - {fix}"
        row(label, a, b, verdict)
        if not ok:
            gaps.append({"axis": label, "sample": a, "ours": b, "fix": fix})

    check("duration s", pa["duration"], pb["duration"],
          abs(pa["duration"] - pb["duration"]) < 8, "retime")
    check("scenes", pa["scenes"], pb["scenes"],
          abs(pa["scenes"] - pb["scenes"]) <= 6, "match cut density")
    check("card scenes", pa["card_scenes"], pb["card_scenes"],
          abs(pa["card_scenes"] - pb["card_scenes"]) <= 3, "card count")
    check("product scenes", pa["product_scenes"], pb["product_scenes"],
          abs(pa["product_scenes"] - pb["product_scenes"]) <= 3, "product count")
    check("micro scenes (<1s)", pa["micro_scenes"], pb["micro_scenes"],
          pb["micro_scenes"] >= pa["micro_scenes"] - 2,
          "add whip/transition micro-cuts")
    check("longest product s", pa["longest_product_s"], pb["longest_product_s"],
          pb["longest_product_s"] >= pa["longest_product_s"] * 0.6,
          "let walkthroughs breathe")
    check("card motion (kinetic)", pa["card_motion_mean"], pb["card_motion_mean"],
          pb["card_motion_mean"] >= pa["card_motion_mean"] * 0.4,
          "cards too static")
    check("zoom events", pa["zoom_events"], pb["zoom_events"],
          pb["zoom_events"] >= max(1, pa["zoom_events"] // 2),
          "camera not moving enough")
    check("cut-on-beat %", pa["cut_beat_pct"], pb["cut_beat_pct"],
          pb["cut_beat_pct"] >= pa["cut_beat_pct"] * 0.6,
          "retime cuts to the music")
    check("LUFS", pa["lufs"], pb["lufs"],
          pa["lufs"] is not None and pb["lufs"] is not None
          and abs(pa["lufs"] - pb["lufs"]) < 3, "loudnorm")
    print("=" * 78)
    return gaps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sample")
    ap.add_argument("ours")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    pa = profile(Path(a.sample))
    pb = profile(Path(a.ours))
    gaps = compare(pa, pb)

    print(f"\n{len(gaps)} measured gaps:")
    for g in gaps:
        print(f"  - {g['axis']}: sample={g['sample']} ours={g['ours']} -> {g['fix']}")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"sample": pa, "ours": pb, "gaps": gaps}, indent=2), encoding="utf-8")
        print(f"-> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
