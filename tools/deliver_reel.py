#!/usr/bin/env python3
"""
deliver_reel.py - mux, loudness-normalize, and deliver a VERSIONED reel.
========================================================================
Ian (2026-07-31): "can you just change the title depending on the version you
made" - every delivery had been overwriting ONE filename, so he could never
tell which version he was watching or A/B two versions. Versions are cheap;
ambiguity about what you are reviewing is not.

This replaces the inline mux snippet that had been retyped ~8 times:
  render mp4 + music -> loudnorm -14 LUFS -> Desktop/WorkHive_Videos/
  <date>_WorkHive_DemoReel_v<N>_16x9.mp4

The version number is REQUIRED and the destination must not already exist -
overwriting a delivered version is exactly the bug this exists to kill.

CLI:
    python tools/deliver_reel.py --version 14
    python tools/deliver_reel.py --version 14 --music .tmp/music/other.mp3
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from video_reference_study import ffmpeg_exe, loudness, probe   # noqa: E402

RENDER = ROOT / "remotion_scenes" / "out" / "demo_reel_16x9.mp4"
DEFAULT_MUSIC = ROOT / ".tmp" / "music" / "pixabay_upbeat_corporate_346481.mp3"
DESK = Path.home() / "Desktop" / "WorkHive_Videos"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--music", default=str(DEFAULT_MUSIC))
    ap.add_argument("--src", default=str(RENDER))
    a = ap.parse_args()

    src, music = Path(a.src), Path(a.music)
    if not src.exists():
        sys.exit(f"no render at {src}")
    dest = DESK / f"{date.today():%Y-%m-%d}_WorkHive_DemoReel_v{a.version}_16x9.mp4"
    if dest.exists():
        sys.exit(f"{dest.name} already exists - bump --version, never overwrite "
                 f"a delivered cut")

    final = ROOT / ".tmp" / "demo_build" / "workhive_demoreel_16x9.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    d = probe(src).get("duration_s") or 0
    r = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(src), "-stream_loop", "-1", "-i", str(music),
         "-filter_complex",
         f"[1:a]afade=t=in:d=0.8,afade=t=out:st={max(0.5, d-2.4):.2f}:d=2.2,"
         f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)],
        capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"mux failed:\n{(r.stderr or '')[-400:]}")

    lufs = loudness(final).get("integrated_lufs")
    if lufs is None or abs(lufs + 14) > 3:
        sys.exit(f"loudness off target ({lufs} LUFS) - not delivering")

    DESK.mkdir(parents=True, exist_ok=True)
    shutil.copy(final, dest)
    print(f"v{a.version} -> {dest.name}  "
          f"({probe(dest).get('duration_s')}s, {lufs} LUFS, music={music.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
