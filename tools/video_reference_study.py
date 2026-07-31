#!/usr/bin/env python3
"""
video_reference_study.py - reverse-engineer a REFERENCE video into a spec.
==========================================================================
Ian drops a sample video he likes into `.tmp/video_ref/`. This tool studies it
DETERMINISTICALLY so the "what makes it work" conversation is grounded in
measurements, not vibes - then the findings get mapped onto the existing
WorkHive pipeline (remotion_scenes/FlagshipReel.tsx + video_quality_gate.py).

It is the INSTRUMENT half of the loop; the creative judgement stays with the
agent reading the output. What it measures, and why each one matters (every
threshold traces to CONTENT_VIDEO_BEST_PRACTICES.md / the Creative Quality Gate):

  * container      - duration, fps, resolution, ASPECT (9:16 vertical is the
                     placement-spanning social format)
  * shot rhythm    - ffmpeg scene-cut detection -> cut timestamps, shot count,
                     average shot length, and CUTS IN THE FIRST 3s / 5s
                     (Google ABCD: 2+ shots in the first 5s)
  * the hook       - dense frame sampling across 0-3s, because the first 3s
                     decides whether the scroll stops
  * the script     - Whisper transcript WITH timestamps -> the actual VO beats,
                     words-per-minute pacing, and the literal opening line
  * loudness       - ffmpeg ebur128 integrated LUFS (social platforms normalise
                     to about -14; a quiet master gets buried)
  * frames         - JPGs at every cut + the hook grid, so the agent can READ
                     them as images and judge the visual language (typography,
                     caption placement, colour, face-vs-product framing)

Nothing here is WorkHive-specific - it studies ANY mp4/mov/webm/m4v.

CLI:
    python tools/video_reference_study.py .tmp/video_ref/sample.mp4
    python tools/video_reference_study.py "https://www.tiktok.com/@x/video/123"
    python tools/video_reference_study.py --latest        # newest file in video_ref
    python tools/video_reference_study.py --latest --scene-threshold 0.12
    python tools/video_reference_study.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

REF_DIR = ROOT / ".tmp" / "video_ref"
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}

# Sampling caps - keep the frame count affordable to READ as images.
MAX_CUT_FRAMES = 12
HOOK_SAMPLE_TIMES = [0.15, 0.8, 1.6, 2.4]   # the first-3s decision window


# --------------------------------------------------------------------------
# ffmpeg plumbing (same resolver as video_assembler - get_ffmpeg_exe() can hang)
# --------------------------------------------------------------------------

def ffmpeg_exe() -> str:
    import shutil
    env = os.environ.get("IMAGEIO_FFMPEG_EXE")
    if env and Path(env).exists():
        return env
    shim = ROOT / ".tmp/_ffmpeg_shim/ffmpeg.exe"
    if shim.exists():
        return str(shim)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _rel(p: Path) -> str:
    """Repo-relative when possible (readable in the JSON), absolute otherwise -
    the self-test writes to a temp dir OUTSIDE ROOT, where relative_to() raises."""
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(p).resolve())


def _ff(args: list, timeout: int = 900) -> subprocess.CompletedProcess:
    """Run ffmpeg and return the completed process. stderr is where ffmpeg
    writes its analysis output, so callers read .stderr, not .stdout."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-y"] + args
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


# --------------------------------------------------------------------------
# 0. input - a local file, or a pasted link
# --------------------------------------------------------------------------

def looks_like_url(s: str) -> bool:
    return str(s).lower().startswith(("http://", "https://"))


def fetch_url(url: str, dest_dir: Path = REF_DIR) -> Path:
    """Download a TikTok / Reels / Shorts / YouTube link into the drop folder.
    Reference videos are usually SENT as links, so accepting one removes a
    round-trip. Fails loudly - a silently-missing download would otherwise be
    studied as 'no file' and read like a tool bug."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed: pip install yt-dlp") from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "format": "mp4/bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "ffmpeg_location": str(Path(ffmpeg_exe()).parent),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    if not path.exists():                     # yt-dlp may have remuxed the ext
        alts = sorted(dest_dir.glob(path.stem + ".*"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        alts = [p for p in alts if p.suffix.lower() in VIDEO_EXTS]
        if not alts:
            raise RuntimeError(f"download reported success but no file at {path}")
        path = alts[0]
    print(f"  downloaded -> {_rel(path)}  ({info.get('title', '')[:60]})")
    return path


# --------------------------------------------------------------------------
# 1. container
# --------------------------------------------------------------------------

def probe(path: Path) -> dict:
    """Duration / resolution / fps / audio presence, parsed from `ffmpeg -i`.
    ffprobe is NOT bundled with imageio_ffmpeg, so we parse the -i banner and
    cross-check the geometry with OpenCV (which reads the container directly)."""
    out = {"path": str(path), "name": path.name,
           "size_mb": round(path.stat().st_size / 1_048_576, 2)}
    res = _ff(["-i", str(path)], timeout=120)
    err = res.stderr or ""

    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
    if m:
        h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        out["duration_s"] = round(h * 3600 + mnt * 60 + s, 2)

    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
    if m:
        out["width"], out["height"] = int(m.group(1)), int(m.group(2))

    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", err)
    if m:
        out["fps"] = float(m.group(1))

    m = re.search(r"Video:\s*(\w+)", err)
    if m:
        out["vcodec"] = m.group(1)

    out["has_audio"] = "Audio:" in err
    m = re.search(r"Audio:\s*(\w+).*?(\d+)\s*Hz", err)
    if m:
        out["acodec"], out["sample_rate"] = m.group(1), int(m.group(2))

    # OpenCV cross-check - authoritative for frame count / fps on odd containers.
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if w and h:
                out.setdefault("width", w)
                out.setdefault("height", h)
            if fps and fps > 0:
                out["fps"] = round(fps, 3)
            if n > 0 and fps and fps > 0:
                out.setdefault("duration_s", round(n / fps, 2))
                out["frame_count"] = n
        cap.release()
    except Exception as exc:                                  # pragma: no cover
        out["opencv_error"] = str(exc)

    w, h = out.get("width"), out.get("height")
    if w and h:
        ratio = w / h
        out["aspect_ratio"] = round(ratio, 4)
        # Name the ratio the way the social placements do.
        named = [("9:16", 0.5625), ("4:5", 0.8), ("1:1", 1.0),
                 ("16:9", 1.7778), ("4:3", 1.3333)]
        label, _ = min(named, key=lambda t: abs(t[1] - ratio))
        out["aspect_label"] = label
        out["orientation"] = ("vertical" if ratio < 0.95
                              else "square" if ratio < 1.1 else "horizontal")
    return out


# --------------------------------------------------------------------------
# 2. shot rhythm
# --------------------------------------------------------------------------

def scene_cuts(path: Path, threshold: float = 0.25) -> list:
    """Cut timestamps via ffmpeg scene detection. `scene` is the fraction of the
    frame that changed; 0.25 is the usual working threshold for edited social
    video (lower fires on camera motion, higher misses soft cuts).

    KNOWN LIMIT, worth stating rather than hiding: ffmpeg scores the change on
    LUMA, so a cut between two shots of similar brightness scores low even when
    the colour flips completely (the self-test fixture originally used red->green
    = only ~0.29 luma delta, and the cut was legitimately missed). Dissolve- and
    match-cut-heavy references therefore need a lower --scene-threshold; the
    printed shot count is the tell (far fewer shots than the frames show)."""
    return cuts_at(scene_events(path), threshold)


def scene_events(path: Path) -> list:
    """Every candidate cut with its raw score, from ONE decode.

    Thresholding is then pure arithmetic, so calibrate() can try a dozen
    thresholds for the cost of a single pass instead of a dozen passes."""
    res = _ff(["-i", str(path),
               "-filter:v", "select='gt(scene,0.008)',metadata=print:file=-",
               "-f", "null", "-"], timeout=900)
    blob = (res.stdout or "") + (res.stderr or "")
    events, pending = [], None
    for line in blob.splitlines():
        m = re.search(r"pts_time:(\d+\.?\d*)", line)
        if m:
            pending = round(float(m.group(1)), 3)
            continue
        m = re.search(r"scene_score=(\d+\.?\d*)", line)
        if m and pending is not None:
            events.append((pending, float(m.group(1))))
            pending = None
    return events


def cuts_at(events: list, threshold: float) -> list:
    """Apply a threshold to pre-computed events, de-duping adjacent detections
    (a transition can fire on two consecutive frames)."""
    times = []
    for t, score in events:
        if score <= threshold:
            continue
        if not times or t - times[-1] > 0.12:
            times.append(t)
    return times


# Coarse -> fine. A real edit is STABLE across a band of thresholds; noise keeps
# growing as you descend. That difference is what calibrate() exploits.
_SWEEP = [0.40, 0.30, 0.25, 0.20, 0.15, 0.12, 0.10, 0.08, 0.06, 0.04, 0.03, 0.02]


def calibrate(events: list) -> dict:
    """Pick a scene threshold from the video instead of assuming one.

    WHY THIS EXISTS: our own Remotion flagship reported ONE shot in 17.2s at the
    0.25 default - and therefore a failed ABCD 2-shot rule - because its
    transitions are animated, not hard cuts. The real structure is 6 shots. A
    confidently wrong number is worse than no number, so the tool now finds the
    PLATEAU: the widest band of thresholds that agree on a cut count. Hard-cut
    social video plateaus high (~0.25); animated/dissolve work plateaus low
    (~0.06). Returns the chosen threshold plus the whole sweep, so the choice
    is auditable rather than magic."""
    counts = [(t, len(cuts_at(events, t))) for t in _SWEEP]
    best, run_start, run_len = None, None, 0
    prev = None
    for i, (t, n) in enumerate(counts):
        if prev is not None and n == prev[1] and n > 0:
            run_len += 1
        else:
            run_start, run_len = i, 1
        prev = (t, n)
        # Prefer the widest plateau; tie -> the HIGHEST (most conservative)
        # threshold in it, which is counts[run_start][0] since the sweep descends.
        if n > 0 and (best is None or run_len > best["width"]):
            best = {"threshold": counts[run_start][0], "cuts": n, "width": run_len}
    sweep = [{"threshold": t, "cuts": n} for t, n in counts]
    if best is None:                     # genuinely a single continuous shot
        return {"threshold": 0.25, "cuts": 0, "width": 0, "single_shot": True,
                "confident": True, "sweep": sweep}
    best["sweep"] = sweep
    # NO PLATEAU = the count climbs at every step and never settles, which means
    # continuous motion (animation, camera moves, kinetic type) rather than a
    # cut-driven edit. Ian's eTax reference did exactly this: 10 -> 16 -> 23 ->
    # ... -> 156, and the tool reported a confident-looking "11 shots" that was
    # meaningless. Say so instead of picking a number that reads as fact.
    best["confident"] = best["width"] >= 2
    if not best["confident"]:
        best["note"] = ("no stable plateau - cut count climbs monotonically, so "
                        "this is a continuous-motion piece, not a cut-driven "
                        "edit. Shot count is NOT meaningful; frames are sampled "
                        "uniformly instead.")
    return best


def rhythm(cuts: list, duration: float) -> dict:
    """Turn raw cut times into the metrics the Creative Quality Gate reasons
    about. A 'shot' is the span between cuts; t=0 opens the first shot."""
    shots = len(cuts) + 1
    out = {
        "cut_count": len(cuts),
        "shot_count": shots,
        "avg_shot_len_s": round(duration / shots, 2) if duration else None,
        "cuts_in_first_3s": sum(1 for t in cuts if t <= 3.0),
        "cuts_in_first_5s": sum(1 for t in cuts if t <= 5.0),
        "shots_in_first_5s": sum(1 for t in cuts if t <= 5.0) + 1,
    }
    if len(cuts) >= 2:
        gaps = [round(cuts[i] - cuts[i - 1], 3) for i in range(1, len(cuts))]
        out["shot_len_min_s"] = min(gaps)
        out["shot_len_max_s"] = max(gaps)
    # ABCD: 2+ shots in the first 5s is the measured attention rule.
    out["abcd_two_shots_in_5s"] = out["shots_in_first_5s"] >= 2
    return out


# --------------------------------------------------------------------------
# 3. frames
# --------------------------------------------------------------------------

def _sample_times(cuts: list, duration: float, confident: bool = True) -> list:
    """The hook window densely, then one frame just AFTER each cut (a frame ON
    the cut can land mid-transition and read as mush), then the end card.

    When cut detection is NOT confident (continuous-motion piece), cuts are not
    a trustworthy skeleton - following them left a 75-second stretch of the eTax
    reference almost unsampled. Fall back to an even sweep of the whole runtime
    so nothing goes unseen."""
    times = [t for t in HOOK_SAMPLE_TIMES if t < duration]
    if not confident:
        step = max(duration / (MAX_CUT_FRAMES + 4), 0.5)
        t = 3.0
        while t < duration:
            times.append(round(t, 3))
            t += step
        if duration > 1.0:
            times.append(round(duration - 0.4, 3))
        return sorted({round(x, 1) for x in times if 0 <= x < duration})
    for t in cuts[:MAX_CUT_FRAMES]:
        times.append(round(t + 0.25, 3))
    if duration > 1.0:
        times.append(round(duration - 0.4, 3))
    seen, keep = set(), []
    for t in sorted(times):
        if t < 0 or t >= duration:
            continue
        k = round(t, 1)
        if k in seen:
            continue
        seen.add(k)
        keep.append(t)
    return keep


def extract_frames(path: Path, times: list, out_dir: Path, width: int = 520) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for i, t in enumerate(times):
        dest = out_dir / f"f{i:02d}_t{t:07.3f}s.jpg"
        # -ss BEFORE -i = fast keyframe seek; accurate enough at this sampling.
        res = _ff(["-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                   "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)], timeout=120)
        if dest.exists() and dest.stat().st_size > 0:
            made.append({"t": t, "file": _rel(dest), "abs": str(dest)})
        elif res.returncode != 0:
            made.append({"t": t, "error": (res.stderr or "")[-200:]})
    return made


def contact_sheet(frames: list, dest: Path, cols: int = 4) -> str | None:
    """One tiled image of the whole arc - lets the agent see the visual story in
    a single Read instead of N. Falls back silently if Pillow is absent."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:                                        # pragma: no cover
        return None
    have = [f for f in frames if "file" in f]
    paths = [Path(f.get("abs") or (ROOT / f["file"])) for f in have]
    if not paths:
        return None
    ims = [Image.open(p).convert("RGB") for p in paths]
    tw, th = 320, int(320 * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    pad, bar = 6, 18
    sheet = Image.new("RGB", (cols * (tw + pad) + pad,
                              rows * (th + bar + pad) + pad), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for i, (im, f) in enumerate(zip(ims, have)):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + bar + pad)
        sheet.paste(im.resize((tw, th)), (x, y))
        d.text((x + 3, y + th + 3), f"{i:02d}  t={f['t']:.2f}s", fill=(235, 235, 235))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=88)
    return _rel(dest)


# --------------------------------------------------------------------------
# 4. script + loudness
# --------------------------------------------------------------------------

def _decode_audio_16k(path: Path):
    """Decode to the mono 16 kHz float32 array Whisper wants, using OUR ffmpeg.

    Whisper's own load_audio() shells out to a bare `ffmpeg` on PATH. There is
    no PATH ffmpeg on this machine (we use the imageio_ffmpeg binary), so it
    died with a bare '[WinError 2] cannot find the file specified' that read
    like a missing model rather than a missing decoder. Decoding here removes
    the dependency entirely."""
    import numpy as np
    # Binary mode on purpose: _ff() decodes stdout as text, which would mangle
    # raw PCM. Whisper's contract is mono f32 @16k in [-1,1] - exactly f32le.
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, timeout=900)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError((proc.stderr or b"").decode("utf-8", "replace")[-300:]
                           or "ffmpeg produced no audio")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def transcribe(path: Path, model_size: str = "base") -> dict:
    """Whisper transcript with segment timestamps. This is the reference's
    actual SCRIPT - the beat structure, the opening line, the CTA wording."""
    try:
        import whisper
    except ImportError:
        return {"available": False, "reason": "openai-whisper not installed"}
    try:
        audio = _decode_audio_16k(path)
        if audio.size < 16000 * 0.2:
            return {"available": False, "reason": "audio track shorter than 0.2s"}
        model = whisper.load_model(model_size)
        r = model.transcribe(audio, verbose=False)
    except Exception as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {str(exc)[:280]}"}

    segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
             "text": (s.get("text") or "").strip()} for s in r.get("segments", [])]
    text = (r.get("text") or "").strip()
    words = len(text.split())
    span = segs[-1]["end"] if segs else 0
    return {
        "available": True,
        "language": r.get("language"),
        "text": text,
        "segments": segs,
        "word_count": words,
        "words_per_min": round(words / (span / 60), 1) if span > 5 else None,
        "first_3s_line": " ".join(s["text"] for s in segs if s["start"] < 3.0),
    }


def loudness(path: Path) -> dict:
    """Integrated LUFS via ebur128. Social platforms normalise toward -14 LUFS;
    a master far quieter than that gets turned down relative to the feed."""
    res = _ff(["-i", str(path), "-af", "ebur128", "-f", "null", "-"], timeout=600)
    err = res.stderr or ""
    out = {}
    m = re.search(r"I:\s*(-?\d+\.?\d*)\s*LUFS", err[::-1][:4000][::-1])
    if not m:
        m = re.findall(r"I:\s*(-?\d+\.?\d*)\s*LUFS", err)
        if m:
            out["integrated_lufs"] = float(m[-1])
    else:
        out["integrated_lufs"] = float(m.group(1))
    m = re.findall(r"LRA:\s*(-?\d+\.?\d*)\s*LU", err)
    if m:
        out["loudness_range_lu"] = float(m[-1])
    if "integrated_lufs" in out:
        out["vs_social_target_db"] = round(out["integrated_lufs"] + 14.0, 1)
    return out


# --------------------------------------------------------------------------
# study
# --------------------------------------------------------------------------

def study(path: Path, do_transcript: bool = True, model_size: str = "base",
          scene_threshold: float | None = None) -> dict:
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    out_dir = REF_DIR / f"{path.stem}_study"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] probing {path.name} ...")
    meta = probe(path)
    dur = meta.get("duration_s") or 0.0

    print("[2/5] detecting scene cuts ...")
    events = scene_events(path)
    cal = calibrate(events)
    if scene_threshold is None:
        chosen = cal["threshold"]
        print(f"      auto-calibrated threshold {chosen} "
              f"({cal['cuts']} cuts, stable across {cal['width']} steps)")
    else:
        chosen = scene_threshold
        print(f"      threshold {chosen} (forced; auto would pick "
              f"{cal['threshold']})")
    cuts = cuts_at(events, chosen)
    rhy = rhythm(cuts, dur)
    rhy["scene_threshold"] = chosen
    rhy["threshold_auto"] = scene_threshold is None
    rhy["calibration"] = cal

    if not cal.get("confident", True):
        print(f"      !! {cal['note']}")
    print(f"[3/5] extracting frames ({rhy['shot_count']} shots) ...")
    times = _sample_times(cuts, dur, confident=cal.get("confident", True))
    frames = extract_frames(path, times, out_dir / "frames")
    sheet = contact_sheet(frames, out_dir / "contact_sheet.jpg")

    print("[4/5] measuring loudness ...")
    loud = loudness(path) if meta.get("has_audio") else {"note": "no audio track"}

    script = {"available": False, "reason": "skipped (--no-transcript)"}
    if do_transcript and meta.get("has_audio"):
        print(f"[5/5] transcribing (whisper {model_size}, this takes a minute) ...")
        script = transcribe(path, model_size)
    elif not meta.get("has_audio"):
        script = {"available": False, "reason": "no audio track"}

    result = {
        "source": meta,
        "rhythm": rhy,
        "cut_times_s": cuts,
        "frames": frames,
        "contact_sheet": sheet,
        "loudness": loud,
        "script": script,
        "read_this": {
            "contact_sheet": sheet,
            "frames_dir": _rel(out_dir / "frames"),
        },
    }
    dest = out_dir / "study.json"
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    result["study_json"] = _rel(dest)
    return result


def print_summary(r: dict) -> None:
    s, rhy = r["source"], r["rhythm"]
    print("\n" + "=" * 66)
    print(f"REFERENCE STUDY - {s.get('name')}")
    print("=" * 66)
    print(f"  duration     {s.get('duration_s')}s   fps {s.get('fps')}   {s.get('size_mb')} MB")
    print(f"  frame        {s.get('width')}x{s.get('height')}  "
          f"{s.get('aspect_label')} ({s.get('orientation')})")
    cal = rhy.get("calibration", {})
    if cal.get("confident", True):
        print(f"  shots        {rhy['shot_count']}  (avg {rhy['avg_shot_len_s']}s/shot)")
    else:
        print(f"  shots        UNRELIABLE - continuous-motion piece, not a cut-driven edit")
        print(f"               (sweep never settles: "
              f"{cal['sweep'][0]['cuts']} cuts @{cal['sweep'][0]['threshold']} -> "
              f"{cal['sweep'][-1]['cuts']} @{cal['sweep'][-1]['threshold']})")
    if cal.get("confident", True):
        print(f"  first 5s     {rhy['shots_in_first_5s']} shots  -> ABCD 2-shot rule: "
              f"{'PASS' if rhy['abcd_two_shots_in_5s'] else 'FAIL'}")
        print(f"  first 3s     {rhy['cuts_in_first_3s']} cuts")
    if r["loudness"].get("integrated_lufs") is not None:
        print(f"  loudness     {r['loudness']['integrated_lufs']} LUFS  "
              f"({r['loudness'].get('vs_social_target_db'):+} dB vs -14 target)")
    sc = r["script"]
    if sc.get("available"):
        print(f"  script       {sc['word_count']} words, {sc.get('words_per_min')} wpm "
              f"[{sc.get('language')}]")
        print(f"  opening line \"{(sc.get('first_3s_line') or '').strip()[:90]}\"")
    else:
        print(f"  script       (none: {sc.get('reason')})")
    print(f"\n  frames       {len([f for f in r['frames'] if 'file' in f])} extracted")
    print(f"  contact      {r.get('contact_sheet')}")
    print(f"  json         {r.get('study_json')}")
    print("=" * 66 + "\n")


# --------------------------------------------------------------------------

def _build_fixture(colours: list, dst: Path, tmp: Path, tag: str) -> Path:
    """Concatenate 2s solid-colour segments -> a clip whose cut times are KNOWN
    exactly (at 2s and 4s), so the detector can be graded against ground truth."""
    parts = []
    for i, colour in enumerate(colours):
        p = tmp / f"{tag}_p{i}.mp4"
        _ff(["-f", "lavfi", "-i", f"color=c={colour}:s=320x568:d=2:r=25",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", str(p)], timeout=120)
        parts.append(p)
    lst = tmp / f"{tag}_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    _ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dst)],
        timeout=120)
    return dst


def self_test() -> int:
    """Assert the tool RECOVERS a known structure from a synthetic clip. A study
    tool that reports a plausible number on a video it never really decoded is
    the failure mode worth guarding (see the 'impossibly good result' lesson).

    Two fixtures, because one only proves half of it:
      HARD  black/white/gray - unambiguous luma deltas; the default threshold
            must find both cuts. A miss here means the TOOL is broken.
      SOFT  gray steps of 18 - measured scene_score ~0.15, i.e. deliberately
            BETWEEN the two thresholds. The default must MISS both cuts and
            0.10 must RECOVER both. That is the non-vacuity check: it proves
            the threshold is load-bearing in the exact direction a real
            dissolve- or match-cut-heavy reference will need.
    """
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="vrs_selftest_"))
    src = _build_fixture(["black", "white", "gray"], tmp / "hard.mp4", tmp, "hard")

    if not src.exists():
        print("SELF-TEST FAIL: ffmpeg could not build the fixture "
              f"(exe={ffmpeg_exe()})")
        return 1

    fails = []
    meta = probe(src)
    if not (5.5 <= (meta.get("duration_s") or 0) <= 6.5):
        fails.append(f"duration {meta.get('duration_s')} not ~6s")
    if meta.get("aspect_label") != "9:16":
        fails.append(f"aspect {meta.get('aspect_label')} != 9:16 (320x568)")
    if not meta.get("has_audio"):
        fails.append("audio track not detected")

    cuts = scene_cuts(src)
    if len(cuts) != 2:
        fails.append(f"expected 2 cuts, got {len(cuts)}: {cuts}")
    else:
        if not (1.7 <= cuts[0] <= 2.3):
            fails.append(f"cut[0]={cuts[0]} not ~2.0s")
        if not (3.7 <= cuts[1] <= 4.3):
            fails.append(f"cut[1]={cuts[1]} not ~4.0s")

    rhy = rhythm(cuts, meta.get("duration_s") or 6.0)
    if rhy["shot_count"] != 3:
        fails.append(f"shot_count {rhy['shot_count']} != 3")

    # SENSITIVITY (non-vacuity): a detector that returns the same list whatever
    # you ask it has no teeth. The SOFT fixture is engineered to sit across the
    # default threshold - default must miss a cut, a lower threshold must find
    # it. Both halves have to hold, or the threshold is decoration.
    # Gray steps of 18/255 MEASURE at scene_score 0.15-0.16 (measured, not
    # predicted - my arithmetic guess was 2x off). That straddles the two
    # thresholds by construction. NB red/green/blue is useless here: ffmpeg's
    # "green" is #008000, whose luma is within 1 of red's, so that cut is
    # invisible at ANY threshold - which is how this fixture got chosen.
    soft = _build_fixture(["0x303030", "0x424242", "0x545454"],
                          tmp / "soft.mp4", tmp, "soft")
    soft_default = scene_cuts(soft, threshold=0.25)
    soft_low = scene_cuts(soft, threshold=0.10)
    if soft_default:
        fails.append(f"soft fixture (score ~0.15) should be MISSED at the 0.25 "
                     f"default, got {soft_default}")
    if len(soft_low) != 2:
        fails.append(f"soft fixture at 0.10 should recover both cuts, got {soft_low}")
    if len(soft_low) <= len(soft_default):
        fails.append(f"threshold not load-bearing: 0.25 -> {len(soft_default)} cuts, "
                     f"0.10 -> {len(soft_low)} cuts (lowering must find MORE)")

    # CALIBRATION is the whole point of the soft fixture: a fixed default reports
    # "0 cuts, 1 shot" on it, exactly as it did on our real Remotion flagship.
    # Auto-calibration must recover the true structure WITHOUT being told.
    for tag, fixture, want in (("hard", src, 2), ("soft", soft, 2)):
        cal = calibrate(scene_events(fixture))
        if cal["cuts"] != want:
            fails.append(f"calibrate({tag}) found {cal['cuts']} cuts, expected {want} "
                         f"(picked threshold {cal['threshold']}, sweep {cal['sweep']})")
    # ...and it must not hallucinate structure in a genuinely single-shot clip.
    still = _build_fixture(["0x404040"], tmp / "still.mp4", tmp, "still")
    cal_still = calibrate(scene_events(still))
    if cal_still["cuts"] != 0:
        fails.append(f"calibrate(single-shot) invented {cal_still['cuts']} cuts")

    frames = extract_frames(src, _sample_times(cuts, meta["duration_s"]), tmp / "fr")
    if len([f for f in frames if "file" in f]) < 4:
        fails.append(f"only {len(frames)} frames extracted")

    if fails:
        print("SELF-TEST FAIL:")
        for f in fails:
            print("  - " + f)
        return 1
    print(f"SELF-TEST PASS - hard fixture: 3 shots, cuts at {cuts}, 9:16, audio, "
          f"{len(frames)} frames extracted.")
    print(f"                 soft fixture: {len(soft_default)} cuts @0.25 -> "
          f"{len(soft_low)} @0.10 (threshold is load-bearing).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Study a reference video.")
    ap.add_argument("video", nargs="?", help="path to the reference video")
    ap.add_argument("--latest", action="store_true",
                    help="use the newest video in .tmp/video_ref/")
    ap.add_argument("--no-transcript", action="store_true")
    ap.add_argument("--model", default="base", help="whisper model size")
    ap.add_argument("--scene-threshold", type=float, default=None,
                    help="force the scene-change sensitivity; omit to "
                         "auto-calibrate from the video itself")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    path = None
    if a.latest:
        REF_DIR.mkdir(parents=True, exist_ok=True)
        cands = [p for p in REF_DIR.iterdir()
                 if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
        if not cands:
            print(f"No video found in {REF_DIR}. Drop an .mp4/.mov/.webm there.")
            return 1
        path = max(cands, key=lambda p: p.stat().st_mtime)
        print(f"--latest -> {path.name}")
    elif a.video and looks_like_url(a.video):
        print(f"fetching {a.video} ...")
        path = fetch_url(a.video)
    elif a.video:
        path = Path(a.video)
    else:
        ap.error("give a video path, or --latest, or --self-test")

    r = study(path, do_transcript=not a.no_transcript, model_size=a.model,
              scene_threshold=a.scene_threshold)
    print_summary(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
