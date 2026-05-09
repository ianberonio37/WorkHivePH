"""
WorkHive Video Assembler
Combines UI recording + narration + background music into a ready-to-post .mp4.
Optionally burns auto-generated captions using Whisper.

Pipeline:
  1. UI recording (.webm)  — Playwright auto-recorder
  2. Narration (.mp3)      — Edge TTS voice generation
  3. Music (.mp3)          — Suno AI (optional, user-provided)
  4. Hook clip (.mp4)      — Kling AI (optional, user-provided)
  ──────────────────────────────────────────────────────────
  → Draft .mp4  (narration drives the length)
  → Captioned .mp4  (Whisper auto-subtitles burned in)

Usage:
    python tools/video_assembler.py --idea idea_006 --voice james [--music path.mp3]
"""

import os
import re
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

ROOT           = Path(__file__).parent.parent
RECORDINGS_DIR = ROOT / ".tmp/ui_recordings"
VOICE_DIR      = ROOT / ".tmp/voice_files"
ASSEMBLED_DIR  = ROOT / ".tmp/assembled_videos"
BACKLOG        = ROOT / ".tmp/video_ideas_backlog.json"
LOGO_PATH      = ROOT / "brand_assets/workhive-logo-transparent.png"

# Watermark sizing: 140px wide on 1280px video = ~11% of frame width
# (broadcast-standard corner watermark size, top-right with 22px padding)
LOGO_WIDTH_PX  = 140
LOGO_PAD_PX    = 22

# ── FFmpeg binary (bundled with imageio_ffmpeg) ───────────────────────────────

def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"   # fall back to system ffmpeg if installed


def _run_ffmpeg(args: list, label: str = ""):
    exe  = _ffmpeg_exe()
    cmd  = [exe, "-y"] + args
    print(f"  ffmpeg: {label}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-800:]}")
    return result


# ── Asset discovery ───────────────────────────────────────────────────────────

def find_narration(idea_id: str, voice_key: str = "james") -> Path | None:
    p = VOICE_DIR / f"{idea_id}_{voice_key}.mp3"
    return p if p.exists() else None


def find_latest_recording(feature: str) -> Path | None:
    """
    Find the most recently modified .webm for this feature.
    Searches both auto-recorder pattern (feature_name_*.webm)
    and manual-recorder pattern (manual_feature_name_*.webm).
    """
    safe = feature.lower().replace(" ", "_").replace("/", "_")[:30]
    matches = (
        list(RECORDINGS_DIR.glob(f"{safe}*.webm")) +
        list(RECORDINGS_DIR.glob(f"manual_{safe}*.webm"))
    )
    if not matches:
        return None
    return sorted(matches, key=lambda f: f.stat().st_mtime)[-1]


def list_recordings(feature: str) -> list:
    """Return all recordings for a feature sorted newest first."""
    safe = feature.lower().replace(" ", "_").replace("/", "_")[:30]
    matches = (
        list(RECORDINGS_DIR.glob(f"{safe}*.webm")) +
        list(RECORDINGS_DIR.glob(f"manual_{safe}*.webm"))
    )
    return sorted(matches, key=lambda f: f.stat().st_mtime, reverse=True)


def get_duration(file_path: Path) -> float:
    """
    Get media duration in seconds using ffmpeg stderr output.
    imageio_ffmpeg bundles only ffmpeg, not ffprobe, so we parse
    the 'Duration: HH:MM:SS.ms' line that ffmpeg always prints.
    """
    exe = _ffmpeg_exe()
    result = subprocess.run(
        [exe, "-i", str(file_path)],
        capture_output=True, text=True
    )
    # Duration is always in stderr (even when ffmpeg 'fails' with no output file)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


# ── Whisper auto-captions ─────────────────────────────────────────────────────

def _ensure_ffmpeg_on_path():
    """
    Whisper shells out to bare 'ffmpeg' for audio decoding. imageio_ffmpeg
    bundles a versioned binary (ffmpeg-win-x86_64-vX.X.exe) which Windows
    won't resolve as 'ffmpeg'. We copy it to a shim dir as ffmpeg.exe and
    prepend that dir to PATH for this process only. No-op if real ffmpeg
    is already on PATH.
    """
    import shutil
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
        bundled  = Path(imageio_ffmpeg.get_ffmpeg_exe())
        shim_dir = ROOT / ".tmp/_ffmpeg_shim"
        shim_dir.mkdir(parents=True, exist_ok=True)
        shim_exe = shim_dir / "ffmpeg.exe"
        if (not shim_exe.exists()
                or shim_exe.stat().st_mtime < bundled.stat().st_mtime):
            shutil.copy2(bundled, shim_exe)
        os.environ["PATH"] = str(shim_dir) + os.pathsep + os.environ.get("PATH", "")
    except Exception as exc:
        print(f"  [WARN] ffmpeg shim setup failed: {exc}")


def generate_srt(narration_path: Path, out_srt: Path, model_size: str = "tiny") -> bool:
    """Transcribe narration and write an SRT file. Returns True on success."""
    try:
        _ensure_ffmpeg_on_path()
        import whisper
        print(f"  Whisper: transcribing narration ({model_size} model)...")
        model  = whisper.load_model(model_size)
        result = model.transcribe(str(narration_path), fp16=False, language="en")

        srt_lines = []
        for i, seg in enumerate(result["segments"], 1):
            start = _srt_time(seg["start"])
            end   = _srt_time(seg["end"])
            text  = seg["text"].strip()
            srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")

        out_srt.write_text("\n".join(srt_lines), encoding="utf-8")
        print(f"  Captions: {len(result['segments'])} segments written to {out_srt.name}")
        return True

    except Exception as exc:
        print(f"  [WARN] Whisper failed: {exc} — video will be assembled without captions")
        return False


def _srt_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── Caption style ─────────────────────────────────────────────────────────────

# WorkHive brand: white text, orange outline, Poppins-like bold
CAPTION_STYLE = (
    "FontName=Arial,FontSize=20,Bold=1,"
    "PrimaryColour=&H00FFFFFF,"      # white text
    "OutlineColour=&H00D88A0E,"      # orange outline (#D88A0E)
    "BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=40"         # bottom-center
)


# ── Core assembly ─────────────────────────────────────────────────────────────

def assemble(
    idea_id:        str,
    voice_key:      str  = "james",
    music_path:     Path = None,
    scene_clip:     Path = None,       # Kling/Pexels scene → full background, UI = overlay
    hook_clip:      Path = None,       # hook clip prepended before UI recording
    recording_file: Path = None,       # explicit recording override (skip auto-pick)
    captions:       bool = True,
    output_path:    Path = None,
) -> Path:
    """
    Assemble all assets into a final .mp4.

    Timeline (narration is the master clock):
      [hook_clip (0→hook_dur)] + [ui_recording (hook_dur→end)]
      narration plays full duration
      music plays full duration at 15% volume
    """
    ASSEMBLED_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load idea ────────────────────────────────────────────────────────────
    data    = json.loads(BACKLOG.read_text(encoding="utf-8"))
    idea    = next((i for i in data["ideas"] if i["id"] == idea_id), None)
    if not idea:
        raise ValueError(f"Idea '{idea_id}' not found in backlog")

    feature = idea.get("solution_feature", "")
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = re.sub(r"[^\w]", "_", idea_id)

    # ── Discover assets ──────────────────────────────────────────────────────
    narration = find_narration(idea_id, voice_key)
    recording = find_latest_recording(feature)

    if not narration:
        raise FileNotFoundError(
            f"No narration found for {idea_id} (voice: {voice_key}). "
            "Generate it in the dashboard first."
        )

    # Use explicit recording override if provided, otherwise auto-pick latest
    if recording_file and recording_file.exists():
        recording = recording_file
        print(f"  Recording:  {recording.name}  (manually selected)")
    elif not recording:
        raise FileNotFoundError(
            f"No UI recording found for '{feature}'. "
            "Click 'Record Demo Video' or 'Record Myself' in the dashboard first."
        )

    print(f"\nAssembling: {idea['title']}")
    print(f"  Narration:  {narration.name}")
    print(f"  Recording:  {recording.name}")
    print(f"  Scene clip: {scene_clip.name if scene_clip else 'none (UI fullscreen)'}")
    print(f"  Music:      {music_path.name if music_path else 'none'}")
    print(f"  Captions:   {'yes (Whisper)' if captions else 'no'}")

    narr_dur = get_duration(narration)
    print(f"  Narration duration: {narr_dur:.1f}s  (master timeline)\n")

    tmp = Path(tempfile.mkdtemp())

    # ── Step 1: Normalise UI recording to mp4 ────────────────────────────────
    norm_video = tmp / "recording_norm.mp4"
    _run_ffmpeg([
        "-i", str(recording),
        "-vf", "scale=1280:900:force_original_aspect_ratio=decrease,pad=1280:900:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-an",
        "-t", str(narr_dur),
        str(norm_video),
    ], "normalise UI recording")

    # ── Step 2: Scene overlay (PiP) if scene_clip provided ───────────────────
    # Layout: scene = full background, UI recording = small corner overlay
    main_video = norm_video
    if scene_clip and scene_clip.exists():
        norm_scene = tmp / "scene_norm.mp4"
        _run_ffmpeg([
            "-i", str(scene_clip),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,loop=-1:size=32767",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",
            "-t", str(narr_dur),
            str(norm_scene),
        ], "normalise scene clip (loop if short)")

        pip_video = tmp / "pip.mp4"
        # UI overlay: 38% width, dark navy border, bottom-right corner
        _run_ffmpeg([
            "-i", str(norm_scene),   # [0] background scene
            "-i", str(norm_video),   # [1] UI overlay
            "-filter_complex",
            "[1:v]scale=trunc(iw*0.38/2)*2:-2[ui_s];"
            "[ui_s]pad=iw+10:ih+10:5:5:color=0x162032[ui_b];"
            "[0:v][ui_b]overlay=W-w-24:H-h-24[vid]",
            "-map", "[vid]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-t", str(narr_dur),
            str(pip_video),
        ], "compose PiP: scene + UI overlay")
        main_video = pip_video

    # ── Step 3: Prepend hook clip if provided ────────────────────────────────
    elif hook_clip and hook_clip.exists():
        norm_hook = tmp / "hook_norm.mp4"
        _run_ffmpeg([
            "-i", str(hook_clip),
            "-vf", "scale=1280:900:force_original_aspect_ratio=decrease,pad=1280:900:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",
            str(norm_hook),
        ], "normalise hook clip")

        concat_list = tmp / "concat.txt"
        concat_list.write_text(
            f"file '{norm_hook}'\nfile '{norm_video}'\n", encoding="utf-8"
        )
        combined = tmp / "combined.mp4"
        _run_ffmpeg([
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            "-t", str(narr_dur),
            str(combined),
        ], "concat hook + recording")
        main_video = combined

    # ── Step 3: Mix audio (narration + music) ────────────────────────────────
    silent_mp4 = tmp / "with_audio.mp4"

    if music_path and music_path.exists():
        _run_ffmpeg([
            "-i", str(main_video),
            "-i", str(narration),
            "-i", str(music_path),
            "-filter_complex",
            "[1:a]volume=1.0[narr];[2:a]volume=0.15,aloop=loop=-1:size=2e+09[music];"
            "[narr][music]amix=inputs=2:duration=first:dropout_transition=1[audio]",
            "-map", "0:v", "-map", "[audio]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(silent_mp4),
        ], "mix narration + music")
    else:
        _run_ffmpeg([
            "-i", str(main_video),
            "-i", str(narration),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(silent_mp4),
        ], "attach narration audio")

    # ── Step 4: Burn captions ─────────────────────────────────────────────────
    if output_path is None:
        output_path = ASSEMBLED_DIR / f"{safe_id}_{ts}.mp4"

    srt_path     = tmp / "captions.srt"
    has_captions = captions and generate_srt(narration, srt_path)
    has_logo     = LOGO_PATH.exists()

    if has_captions and has_logo:
        # Captions + logo watermark in one pass
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        _run_ffmpeg([
            "-i", str(silent_mp4),
            "-i", str(LOGO_PATH),
            "-filter_complex",
            f"[0:v]subtitles='{srt_escaped}':force_style='{CAPTION_STYLE}'[v1];"
            f"[1:v]scale={LOGO_WIDTH_PX}:-1[logo];"
            f"[v1][logo]overlay=W-w-{LOGO_PAD_PX}:{LOGO_PAD_PX}[vout]",
            "-map", "[vout]", "-map", "0:a",
            "-c:a", "copy",
            str(output_path),
        ], "burn captions + WorkHive logo watermark")
    elif has_captions:
        # Captions only (logo file missing)
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        _run_ffmpeg([
            "-i", str(silent_mp4),
            "-vf", f"subtitles='{srt_escaped}':force_style='{CAPTION_STYLE}'",
            "-c:a", "copy",
            str(output_path),
        ], "burn captions")
    elif has_logo:
        # Logo watermark only
        _run_ffmpeg([
            "-i", str(silent_mp4),
            "-i", str(LOGO_PATH),
            "-filter_complex",
            f"[1:v]scale={LOGO_WIDTH_PX}:-1[logo];"
            f"[0:v][logo]overlay=W-w-{LOGO_PAD_PX}:{LOGO_PAD_PX}[vout]",
            "-map", "[vout]", "-map", "0:a",
            "-c:a", "copy",
            str(output_path),
        ], "burn WorkHive logo watermark")
    else:
        # Nothing to burn — just copy
        _run_ffmpeg([
            "-i", str(silent_mp4),
            "-c", "copy",
            str(output_path),
        ], "finalise (no captions)")

    size_mb = output_path.stat().st_size / 1_000_000
    dur     = get_duration(output_path)
    print(f"\n  Done: {output_path.name}")
    print(f"  Duration: {dur:.1f}s  |  Size: {size_mb:.1f} MB")

    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WorkHive Video Assembler")
    parser.add_argument("--idea",     required=True, help="Idea ID (e.g. idea_006)")
    parser.add_argument("--voice",    default="james", help="Voice key used for narration")
    parser.add_argument("--music",    default=None,  help="Path to background music MP3")
    parser.add_argument("--hook",     default=None,  help="Path to Kling AI hook clip")
    parser.add_argument("--no-captions", action="store_true", help="Skip Whisper captions")
    args = parser.parse_args()

    music = Path(args.music) if args.music else None
    hook  = Path(args.hook)  if args.hook  else None

    result = assemble(
        idea_id    = args.idea,
        voice_key  = args.voice,
        music_path = music,
        hook_clip  = hook,
        captions   = not args.no_captions,
    )
    print(f"\nReady to post: {result}")
