#!/usr/bin/env python3
"""
normalize_existing_videos.py - retro-fix the loudness of ALREADY-RENDERED videos.
=================================================================================
`render_flagship.py` and `video_assembler.py` are now fixed, so anything rendered
from here on lands at -14 LUFS. But every file already on disk was produced by
the broken chains and still sits 10-15 dB under target - and those are the files
that actually get posted.

Re-rendering is the wrong tool: a Remotion render is ~2.5 min per aspect, and it
would regenerate the VIDEO to fix the AUDIO. The mix itself was never wrong -
only its level. So this copies the video stream untouched (`-c:v copy`) and
passes the existing audio through loudnorm. Fast, and it cannot alter a single
frame or change the balance of the mix.

Forward-only and non-destructive: writes alongside the source, and SKIPS any
file already inside the acceptable band so re-runs are idempotent.

CLI:
    python tools/normalize_existing_videos.py --dry-run
    python tools/normalize_existing_videos.py --apply
    python tools/normalize_existing_videos.py --apply --in-place
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from video_reference_study import ffmpeg_exe, loudness, probe    # noqa: E402

TARGET, TOL = -14.0, 3.0

SEARCH = [
    ROOT / "remotion_scenes" / "out",
    ROOT / ".tmp" / "assembled_videos",
    Path.home() / "Desktop" / "WorkHive_Videos",
]


def candidates() -> list:
    out = []
    for d in SEARCH:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.mp4")):
            if p.stem.endswith("_norm"):
                continue
            out.append(p)
    return out


def fix(src: Path, in_place: bool) -> tuple:
    m = loudness(src)
    i = m.get("integrated_lufs")
    if i is None:
        return ("skip", src, "no audio track")
    if abs(i - TARGET) <= TOL:
        return ("ok", src, f"{i:.1f} LUFS already in band")

    dest = src.with_name(src.stem + "_norm.mp4")
    r = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(dest)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not dest.exists():
        return ("fail", src, (r.stderr or "")[-160:])

    after = loudness(dest).get("integrated_lufs")
    if after is None or abs(after - TARGET) > TOL:
        # Verify before replacing anything - a "fix" that did not land must not
        # overwrite the original.
        dest.unlink(missing_ok=True)
        return ("fail", src, f"still {after} LUFS after loudnorm")

    if in_place:
        src.unlink()
        dest.rename(src)
        dest = src
    return ("fixed", dest, f"{i:.1f} -> {after:.1f} LUFS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in-place", action="store_true",
                    help="replace the original instead of writing *_norm.mp4")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files = candidates()
    print(f"scanning {len(files)} rendered videos\n")
    counts = {"fixed": 0, "ok": 0, "skip": 0, "fail": 0}

    for p in files:
        if not (a.apply or a.dry_run):
            a.dry_run = True
        if a.dry_run:
            m = loudness(p)
            i = m.get("integrated_lufs")
            if i is None:
                state, note = "skip", "no audio"
            elif abs(i - TARGET) <= TOL:
                state, note = "ok", f"{i:.1f} LUFS in band"
            else:
                state, note = "fixed", f"{i:.1f} LUFS -> WOULD FIX"
            counts[state] += 1
            print(f"  {state.upper():<6} {p.name[:46]:<48} {note}")
            continue
        state, out, note = fix(p, a.in_place)
        counts[state] += 1
        print(f"  {state.upper():<6} {p.name[:46]:<48} {note}")

    print("\n" + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
