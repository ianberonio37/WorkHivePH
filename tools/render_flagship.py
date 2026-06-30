#!/usr/bin/env python3
"""
WorkHive Flagship Video Renderer  (the industrialized "new-era" pipeline)

Renders the data-driven Remotion `FlagshipReel` composition (remotion_scenes/) to
the modern poster-DNA style — product-as-hero, spring motion, mute-first kinetic
captions — across 9:16 / 1:1 / 16:9, then mixes a music bed + light SFX.

One video idea -> one FlagshipSpec JSON -> 3 finished, branded, multi-format videos.

Usage:
    python tools/render_flagship.py --default                       # render the reference spec
    python tools/render_flagship.py --spec <spec.json> --name <id>  # render a specific idea's spec
    python tools/render_flagship.py --spec s.json --name x --aspects 9x16            # subset
    python tools/render_flagship.py --spec s.json --name x --music <track.mp3> --desktop

A FlagshipSpec (all keys optional; omitted keys fall back to the in-composition default):
  { "hook":[{"text":"3AM.","size":150,"weight":900}, ...],
    "stakes":[...],
    "reveal":{"caption":"...","accent":["WorkHive"],"screen":"wh_home_clean.png",
              "flagTitle":"...","flagSub":"...","flagColor":"orange","flagSide":"left"},
    "plan":{...},
    "payoff":[{"text":"Less downtime.","size":86}, {"text":"...","color":"orange"}],
    "endTagline":"...","endSub":"...","endCta":"workhiveph.com — start free" }
colors: cloud|orange|blue|steel.  screen = a PNG in remotion_scenes/public/.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so `from tools.video_quality_gate import score` works when run as a file
REMOTION = ROOT / "remotion_scenes"
OUT = REMOTION / "out"
PUBLIC = REMOTION / "public"
CLI = "node_modules/@remotion/cli/remotion-cli.js"
DESKTOP = Path.home() / "Desktop"
DEFAULT_MUSIC = ROOT / ".tmp" / "music" / "Soundstortion_Dramat_Hidden_Feelings.mp3"

# composition id + (width,height) per aspect
ASPECTS = {
    "9x16": ("WorkHiveFlagship", 1080, 1920),
    "1x1":  ("WorkHiveFlagshipSquare", 1080, 1080),
    "16x9": ("WorkHiveFlagshipWide", 1920, 1080),
}

# video length is fixed by the composition (FLAGSHIP_DURATION = 516f @30fps = 17.2s)
VID_SECONDS = 17.26


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if not exe:
            sys.exit("ffmpeg not found (install imageio-ffmpeg or put ffmpeg on PATH)")
        return exe


def node_exe() -> str:
    return shutil.which("node") or "node"


def render_aspect(comp_id: str, out_path: Path, spec_file: Path | None) -> None:
    cmd = [node_exe(), CLI, "render", comp_id, str(out_path),
           "--codec=h264", "--log=error"]
    if spec_file is not None:
        cmd.append(f"--props={spec_file}")
    print(f"  remotion render {comp_id} -> {out_path.name}")
    subprocess.run(cmd, cwd=str(REMOTION), check=True)


def mux_audio(ff: str, silent: Path, music: Path, out_path: Path) -> None:
    """Music bed (faded, leveled) + synthesized SFX (impact @hook, whoosh @reveal/@payoff)."""
    fout = VID_SECONDS - 1.66
    fc = (
        f"[1:a]aformat=channel_layouts=stereo,volume=0.5,afade=t=in:d=0.8,"
        f"afade=t=out:st={fout:.2f}:d=1.6,atrim=0:{VID_SECONDS}[mus];"
        "[2:a]aformat=channel_layouts=stereo,afade=t=out:st=0.06:d=0.62,volume=0.6,adelay=250:all=1[s1];"
        "[3:a]aformat=channel_layouts=stereo,highpass=f=250,lowpass=f=5000,"
        "afade=t=in:d=0.25,afade=t=out:st=0.32:d=0.3,volume=0.38,adelay=4000:all=1[s2];"
        "[4:a]aformat=channel_layouts=stereo,highpass=f=250,lowpass=f=5000,"
        "afade=t=in:d=0.25,afade=t=out:st=0.32:d=0.3,volume=0.34,adelay=11600:all=1[s3];"
        "[mus][s1][s2][s3]amix=inputs=4:normalize=0:dropout_transition=0,alimiter=limit=0.95,aresample=44100[aout]"
    )
    cmd = [ff, "-y", "-loglevel", "error",
           "-i", str(silent), "-i", str(music),
           "-f", "lavfi", "-i", "sine=frequency=72:duration=0.7",
           "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.5",
           "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.5",
           "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_path)]
    print(f"  mux audio -> {out_path.name}")
    subprocess.run(cmd, check=True)


# frame budget per beat (mirrors BEAT in FlagshipReel.tsx) — for the quality-gate mapping
BEAT_FRAMES = {"hook": 84, "stakes": 72, "reveal": 142, "plan": 112, "payoff": 80, "end": 96}


def _spec_to_ctx(spec: dict, mp4: Path | None = None) -> dict:
    """Map a FlagshipSpec to the video_quality_gate ctx (ABCD / 3s-hook / mute-readability)."""
    def secs(f):
        return round(f / 30.0, 2)

    def join(lines):
        return " ".join(l.get("text", "") for l in (lines or []))

    def first(lines):
        return (lines or [{}])[0].get("text", "")

    rv, pl = spec.get("reveal", {}), spec.get("plan", {})
    segs = [
        {"section": "hook",    "seconds": secs(BEAT_FRAMES["hook"]),   "style": "kinetic",
         "headline": first(spec.get("hook")), "overlay": join(spec.get("hook")), "subhead": "", "ui": {"feature": ""}},
        {"section": "problem", "seconds": secs(BEAT_FRAMES["stakes"]), "style": "kinetic",
         "headline": first(spec.get("stakes")), "overlay": join(spec.get("stakes")), "subhead": "", "ui": {"feature": ""}},
        {"section": "solution", "seconds": secs(BEAT_FRAMES["reveal"]), "style": "demo",
         "headline": rv.get("caption", ""), "overlay": rv.get("caption", ""), "subhead": "WorkHive", "ui": {"feature": rv.get("screen", "")}},
        {"section": "solution", "seconds": secs(BEAT_FRAMES["plan"]), "style": "demo",
         "headline": pl.get("caption", ""), "overlay": pl.get("caption", ""), "subhead": "WorkHive", "ui": {"feature": pl.get("screen", "")}},
        {"section": "payoff",  "seconds": secs(BEAT_FRAMES["payoff"]), "style": "kinetic",
         "headline": first(spec.get("payoff")), "overlay": join(spec.get("payoff")), "subhead": "", "ui": {"feature": ""}},
        {"section": "cta",     "seconds": secs(BEAT_FRAMES["end"]), "style": "endcard",
         "headline": spec.get("endTagline", ""), "overlay": spec.get("endCta", ""), "subhead": spec.get("endSub", ""), "ui": {"feature": "WorkHive"}},
    ]
    return {"segments": segs, "total_seconds": VID_SECONDS, "mp4_path": str(mp4) if mp4 else None}


def run_gate(spec: dict, mp4: Path | None = None) -> dict | None:
    """Score a spec against the creative quality gate and print the scorecard."""
    try:
        from tools.video_quality_gate import score
    except Exception as e:  # noqa: BLE001
        print(f"  [gate] unavailable: {type(e).__name__}: {e}")
        return None
    res = score(_spec_to_ctx(spec, mp4))
    print(f"  [gate] {res['verdict']}  score={res['score']}  axes={res['axes']}")
    if res["blocking_fails"]:
        print(f"  [gate] BLOCKING FAILS: {res['blocking_fails']}")
    for r in res["checks"]:
        if r["status"] != "PASS":
            print(f"         {r['status']:4} {r['check']}: {r['detail']}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="Render the WorkHive flagship video in 9:16/1:1/16:9 + audio.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec", help="path to a FlagshipSpec JSON (overrides the default content)")
    g.add_argument("--default", action="store_true", help="render the in-composition reference spec")
    ap.add_argument("--name", default="flagship", help="output basename (e.g. idea_001)")
    ap.add_argument("--aspects", default="9x16,1x1,16x9", help="comma list: 9x16,1x1,16x9")
    ap.add_argument("--music", default=str(DEFAULT_MUSIC), help="music bed mp3")
    ap.add_argument("--no-audio", action="store_true", help="skip the audio mix (silent master only)")
    ap.add_argument("--desktop", action="store_true", help="also copy finals to the Desktop")
    ap.add_argument("--gate-only", action="store_true", help="score the spec against the creative quality gate and exit (no render)")
    ap.add_argument("--no-gate", action="store_true", help="skip the quality-gate scorecard after rendering")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_exe()
    music = Path(args.music)
    if not args.no_audio and not music.exists():
        sys.exit(f"music track not found: {music}")

    spec_file = None
    if args.spec:
        spec_path = Path(args.spec)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        # validate referenced screens exist in public/
        for beat in ("reveal", "plan"):
            scr = (spec.get(beat) or {}).get("screen")
            if scr and not (PUBLIC / scr).exists():
                sys.exit(f"screen '{scr}' for '{beat}' not found in {PUBLIC} — capture it first.")
        spec_file = OUT / f"{args.name}_spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8")

    if args.gate_only:
        if not args.spec:
            sys.exit("--gate-only requires --spec")
        run_gate(spec)
        return

    finals = []
    for asp in [a.strip() for a in args.aspects.split(",") if a.strip()]:
        if asp not in ASPECTS:
            sys.exit(f"unknown aspect '{asp}' (use 9x16,1x1,16x9)")
        comp_id = ASPECTS[asp][0]
        silent = OUT / f"{args.name}_{asp}.mp4"
        render_aspect(comp_id, silent, spec_file)
        if args.no_audio:
            finals.append(silent)
            continue
        final = OUT / f"{args.name}_{asp}_audio.mp4"
        mux_audio(ff, silent, music, final)
        finals.append(final)

    if args.desktop:
        for f in finals:
            asp = f.stem.replace(f"{args.name}_", "").replace("_audio", "")
            dest = DESKTOP / f"WorkHive_{args.name}_{asp}.mp4"
            shutil.copyfile(f, dest)
            print(f"  -> Desktop: {dest.name}")

    if not args.no_gate and args.spec:
        print("\nCreative quality gate:")
        run_gate(spec, finals[0] if finals else None)

    print("\nDONE. Finals:")
    for f in finals:
        print(f"  {f}")


if __name__ == "__main__":
    main()
