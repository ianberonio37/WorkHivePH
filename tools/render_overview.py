#!/usr/bin/env python3
"""
render_overview.py — the reproducible delivery driver for the "WorkHive Explains"
pure-Python platform-overview video (explainer_studio.render_overview).
=================================================================================
The overview delivery had been ad-hoc (a hand-run session snippet). This makes it
a committed, repeatable pipeline so a script change re-renders + re-delivers with
one command, and so the short/ad platform cuts render the same way:

    spec (overview_spec / _short / _ad)
      -> synth James narration + word timings   (explainer_voice.synth_spec)
      -> render N aspects, sidechain-duck music, loudnorm -14 LUFS  (explainer_studio)
      -> MEASURE final loudness (verify the P1 audio target held)
      -> score the Creative/Overview gate         (video_quality_gate.score_explainer)
      -> optional: copy finals to Desktop/WorkHive_Videos + emit titlecard/preview stills

Zero new dependencies (Pillow + ffmpeg via imageio_ffmpeg + edge-tts, all already used).

CLI:
    python tools/render_overview.py                         # main cut, 9:16, gate, no deliver
    python tools/render_overview.py --variant main --aspects 9x16,1x1,16x9 --desktop --stills
    python tools/render_overview.py --variant short --reuse-audio
    python tools/render_overview.py --gate-only               # score the spec, no render
    python tools/render_overview.py --self-test               # fast, no network/ffmpeg
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path


def _today() -> str:
    """ISO date prefix (YYYY-MM-DD_) so delivered files sort + are easy to find."""
    return date.today().isoformat() + "_"

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DESKTOP = Path.home() / "Desktop"
DELIVER_DIR = DESKTOP / "WorkHive_Videos"
AUDIO_ROOT = ROOT / ".tmp" / "explainer_audio"
OUT_ROOT = ROOT / ".tmp" / "explainer_out"

# delivered-file aspect labels (9x16) <-> engine ASPECTS keys (9:16)
ASPECT_MAP = {"9x16": "9:16", "1x1": "1:1", "16x9": "16:9"}


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


# ── spec builders (the three platform cuts) ──────────────────────────────────

def _spec_for(variant: str, topic: str = "overview") -> dict:
    """Return the <topic> spec for a variant. `main` -> <topic>_spec(); the
    `short` (<=30s) and `ad` (~15s) cuts come from <topic>_spec_<variant>() if
    defined, else fall back to `main` with a clear note. topic='overview' is the
    platform overview; topic='asset_brain' the Asset Brain 360 feature spot, etc."""
    import explainer_render as er
    base = getattr(er, f"{topic}_spec", None)
    if not callable(base):
        raise SystemExit(f"  [render] no spec '{topic}_spec()' in explainer_render.py")
    if variant == "main":
        return base()
    fn = getattr(er, f"{topic}_spec_{variant}", None)
    if callable(fn):
        return fn()
    print(f"  [render] no {topic}_spec_{variant}() yet — using the main cut.")
    return base()


# ── loudness verification (proves the P1 -14 LUFS / -1 dBTP target held) ──────

_LN_KEYS = ("input_i", "input_tp", "input_lra", "input_thresh")


def measure_loudness(path: str | Path) -> dict | None:
    """Run one loudnorm analysis pass and return the measured integrated LUFS +
    true peak of the FINAL file. Dependency-free (ffmpeg already bundled). Returns
    None if it cannot be measured (so callers degrade gracefully)."""
    ff = _ffmpeg_exe()
    try:
        r = subprocess.run(
            [ff, "-i", str(path), "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    # loudnorm prints the JSON block to stderr; grab the last {...} object
    err = r.stderr or ""
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        return None
    try:
        data = json.loads(m[-1])
    except Exception:
        return None
    return {k: data.get(k) for k in _LN_KEYS if k in data}


def _print_loudness(ln: dict | None) -> None:
    if not ln:
        print("  [loudness] (unavailable)")
        return
    i = ln.get("input_i"); tp = ln.get("input_tp")
    tgt_ok = i is not None and abs(float(i) + 14.0) <= 1.5
    tp_ok = tp is not None and float(tp) <= -1.0     # the -1 dBTP ceiling (EBU/social)
    notes = []
    if not tgt_ok:
        notes.append("LUFS off -14")
    if not tp_ok:
        notes.append("TP over -1 dBTP ceiling")
    flag = "OK" if not notes else ("off-target: " + ", ".join(notes))
    print(f"  [loudness] integrated {i} LUFS · true-peak {tp} dBTP · "
          f"LRA {ln.get('input_lra')} -> {flag} (target -14 LUFS / <=-1 dBTP)")


# ── stills : a brand titlecard + a product-hero cover (the mute-first thumbnail)

def emit_stills(spec: dict, out_dir: Path, aspect: str = "9:16", name_prefix: str = "",
                name: str = "WorkHive_Overview") -> list[Path]:
    """Render two representative stills: a brand titlecard (logo intro, settled)
    and a product-hero cover (the stop-scroll thumbnail). Reuses the studio's own
    scene functions so the stills match the video exactly."""
    import explainer_studio as st
    from explainer_render import ASPECTS
    W, H = ASPECTS.get(aspect, ASPECTS["9:16"])
    out_dir.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []

    # titlecard: the logo intro at a settled t
    tc = st.animated_bg(W, H, 0.15)
    st.scene_intro(tc, spec, W, H, 1.0)
    tp = out_dir / f"{name_prefix}{name}_titlecard.png"
    tc.convert("RGB").save(tp); made.append(tp)

    # cover: the product hero (first product beat if present, else the home screen)
    prod = next((b for b in spec.get("beats", []) if b.get("scene") == "product"), None)
    screen = (prod or {}).get("screen", "wh_home_clean")
    label = (prod or {}).get("label", "Home Dashboard")
    headline = (prod or {}).get("caption", "See it coming")
    cover = st.animated_bg(W, H, 0.2)
    st.hero_scene(cover, W, H, screen, headline, label, caption="", appear=1.0, kb=0.4)
    cp = out_dir / f"{name_prefix}{name}_preview.png"
    cover.convert("RGB").save(cp); made.append(cp)
    return made


# ── the pipeline ──────────────────────────────────────────────────────────────

def build(variant: str, aspects: list[str], *, reuse_audio: bool, deliver: bool,
          stills: bool, music: str | None, run_gate: bool, label: str = "",
          topic: str = "overview", name: str = "WorkHive_Overview") -> dict:
    import explainer_voice as ev
    import explainer_studio as st

    spec = _spec_for(variant, topic)
    stem = f"workhive_{topic}" if variant == "main" else f"workhive_{topic}_{variant}"
    audio_dir = AUDIO_ROOT / stem       # audio is per-variant; a label only renames outputs (A/B)
    lbl = f"_{label}" if label else ""
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    # 1) narration (reuse if asked + present)
    if reuse_audio and (audio_dir / "manifest.json").exists():
        print(f"  [overview] reusing audio in {audio_dir}")
    else:
        print(f"  [overview] synthesising James narration for '{variant}' ...")
        ev.synth_spec(spec, audio_dir)

    # 2) render each aspect (music: default track unless disabled). The short/ad
    # cuts use a shorter silent brand-hold so they land nearer their length target.
    mus_arg = "default" if music == "default" else (None if music in (None, "none") else music)
    end_hold = {"main": None, "short": 1.4, "ad": 1.2}.get(variant)
    finals: dict[str, Path] = {}
    for asp in aspects:
        eng = ASPECT_MAP.get(asp)
        if not eng:
            print(f"  [overview] unknown aspect '{asp}' (use 9x16,1x1,16x9) — skipped")
            continue
        out = OUT_ROOT / f"{stem}{lbl}_{asp}.mp4"
        st.render_overview(spec, audio_dir, out, aspect=eng, fps=24, music=mus_arg, end_hold=end_hold)
        finals[asp] = out

    # 3) verify loudness on the primary (9x16 if present, else the first)
    primary = finals.get("9x16") or (next(iter(finals.values())) if finals else None)
    ln = measure_loudness(primary) if primary else {}
    if primary:
        _print_loudness(ln)

    # 3b) DEGENERATE-RENDER guard: a truncated / silent render (e.g. an ffmpeg audio-mux
    # hiccup under CPU contention) yields a tiny, LRA=0.00 file that STILL passes the
    # spec gate (the gate scores the spec, not the output MP4). Refuse to deliver such a
    # file so a broken video never silently ships. (2026-07-05: caught a 265KB / LRA 0.00
    # resume cut that passed gate=100 and shipped.)
    degenerate: set[str] = set()
    for asp, f in finals.items():
        try:
            kb = f.stat().st_size / 1024
        except Exception:
            kb = 0
        if kb < 800:  # any real 15-60s h264 clip is > 800KB; ~265KB = truncated/silent
            degenerate.add(asp)
            print(f"  [render] DEGENERATE {asp}: {kb:.0f}KB (too small) — will NOT deliver")
    lra = ln.get("input_lra")
    if lra is not None and float(lra) == 0.0 and primary:
        pa = next((a for a, f in finals.items() if f == primary), None)
        if pa:
            degenerate.add(pa)
            print(f"  [render] DEGENERATE {pa}: primary LRA 0.00 (silent audio) — will NOT deliver")

    # 4) gate the spec
    gate = None
    if run_gate:
        import video_quality_gate as vg
        gate = vg.score_explainer(spec)
        print(f"  [gate] {gate['verdict']} · score {gate['score']} · axes {gate['axes']}")
        if gate.get("blocking_fails"):
            print(f"  [gate] BLOCKING: {gate['blocking_fails']}")

    # 5) deliver + stills
    delivered: list[Path] = []
    dpre = _today() if deliver else ""       # date-prefix delivered files so they sort + are findable
    if deliver and finals:
        DELIVER_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "" if variant == "main" else f"_{variant}"
        for asp, f in finals.items():
            if asp in degenerate:
                print(f"  -> SKIPPED delivery of degenerate {asp} (re-render needed)")
                continue
            dest = DELIVER_DIR / f"{dpre}{name}{suffix}{lbl}_{asp}.mp4"
            shutil.copyfile(f, dest)
            delivered.append(dest)
            print(f"  -> Desktop/WorkHive_Videos/{dest.name}")
    made_stills: list[Path] = []
    if stills:
        target = DELIVER_DIR if deliver else OUT_ROOT
        made_stills = emit_stills(spec, target, aspect=ASPECT_MAP.get(aspects[0], "9:16"),
                                  name_prefix=dpre, name=name)
        for s in made_stills:
            print(f"  -> still: {s.name}")

    return {"variant": variant, "finals": {k: str(v) for k, v in finals.items()},
            "delivered": [str(p) for p in delivered], "stills": [str(p) for p in made_stills],
            "gate": gate}


# ── self-test (no network, no ffmpeg render) ─────────────────────────────────

def self_test() -> int:
    print("render_overview.py --self-test")
    print("=" * 52)
    fails = 0

    def ck(cond, label):
        nonlocal fails
        print(("  PASS  " if cond else "  FAIL  ") + label)
        if not cond:
            fails += 1

    spec = _spec_for("main")
    ck(spec.get("kind") == "overview" and len(spec.get("beats", [])) >= 5,
       "main overview spec loads (>=5 beats)")
    ck(ASPECT_MAP["9x16"] == "9:16" and ASPECT_MAP["16x9"] == "16:9",
       "aspect labels map to engine keys")

    # the loudnorm JSON parser handles a realistic ffmpeg stderr blob
    blob = ('some banner\n[Parsed_loudnorm_0 @ 0x0]\n{\n  "input_i" : "-14.10",\n'
            '  "input_tp" : "-1.20",\n  "input_lra" : "4.00",\n  "input_thresh" : "-24.3",\n'
            '  "output_i" : "-14.0"\n}\n')
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", blob, re.S)
    parsed = json.loads(m[-1]) if m else {}
    ck(parsed.get("input_i") == "-14.10" and parsed.get("input_tp") == "-1.20",
       "loudnorm stderr JSON parses integrated + true-peak")

    # gate runs on the spec (deterministic, no render)
    import video_quality_gate as vg
    g = vg.score_explainer(spec)
    ck(g["verdict"] in ("PASS", "WARN") and not g.get("blocking_fails"),
       f"main overview spec passes the gate (score {g['score']}, {g['verdict']})")

    print("=" * 52)
    print("  self-test PASS" if fails == 0 else f"  self-test FAIL — {fails} check(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Render + deliver the WorkHive platform-overview video.")
    ap.add_argument("--variant", default="main", choices=["main", "short", "ad"],
                    help="which cut to render (default: main ~60s)")
    ap.add_argument("--topic", default="overview",
                    help="spec family in explainer_render.py: 'overview' (default) "
                         "| 'asset_brain' (Asset Brain 360 feature spot) | any <topic>_spec()")
    ap.add_argument("--aspects", default="9x16", help="comma list of 9x16,1x1,16x9")
    ap.add_argument("--reuse-audio", action="store_true", help="reuse existing synthesised narration if present")
    ap.add_argument("--desktop", action="store_true", help="copy finals to Desktop/WorkHive_Videos")
    ap.add_argument("--stills", action="store_true", help="emit a titlecard + product-hero cover still")
    ap.add_argument("--music", default="default", help="'default' | 'none' | path to an mp3")
    ap.add_argument("--label", default="", help="suffix for output/delivered names (e.g. an A/B music label)")
    ap.add_argument("--no-gate", action="store_true", help="skip the overview quality gate")
    ap.add_argument("--gate-only", action="store_true", help="score the spec against the gate and exit (no render)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    # A delivered/still display name derived from the topic ('overview' keeps the
    # historical 'WorkHive_Overview'; others become 'WorkHive_<CamelTopic>').
    name = "WorkHive_Overview" if args.topic == "overview" else \
        "WorkHive_" + "".join(w.capitalize() for w in args.topic.split("_"))
    if args.gate_only:
        import video_quality_gate as vg
        spec = _spec_for(args.variant, args.topic)
        res = vg.score_explainer(spec)
        vg.print_explainer(res)
        return 0 if res["verdict"] != "BLOCK" else 1

    aspects = [a.strip() for a in args.aspects.split(",") if a.strip()]
    out = build(args.variant, aspects, reuse_audio=args.reuse_audio, deliver=args.desktop,
                stills=args.stills, music=args.music, run_gate=not args.no_gate, label=args.label,
                topic=args.topic, name=name)
    print("\nDONE. Finals:")
    for asp, f in out["finals"].items():
        print(f"  {asp}: {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
