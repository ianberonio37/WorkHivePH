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
    # imageio_ffmpeg.get_ffmpeg_exe() can HANG on some machines (a network /
    # binary-resolution wait that never returns), which silently stalls the whole
    # video pipeline. Prefer an explicit env override, then a local shim, then a
    # PATH ffmpeg, and only fall back to imageio_ffmpeg as a last resort.
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

def make_vertical(final_mp4: Path, out_path: Path = None) -> Path:
    """9:16 social variant (Reels/Stories/TikTok — the placement-spanning format).
    Blurred-fill background + the sharp 16:9 master centered; audio copied.
    Fast single ffmpeg pass; the burned captions stay in the sharp center band."""
    final_mp4 = Path(final_mp4)
    if out_path is None:
        out_path = final_mp4.with_name(final_mp4.stem + "_vertical.mp4")
    _run_ffmpeg([
        "-i", str(final_mp4),
        "-filter_complex",
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=18,eq=brightness=-0.12[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy",
        str(out_path),
    ], "export 9:16 vertical variant")
    return out_path


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
    # Prefer an explicit env override or an already-built local shim over
    # imageio_ffmpeg.get_ffmpeg_exe() (which can hang on some machines).
    env_exe = os.environ.get("IMAGEIO_FFMPEG_EXE")
    if env_exe and Path(env_exe).exists():
        os.environ["PATH"] = str(Path(env_exe).parent) + os.pathsep + os.environ.get("PATH", "")
        return
    _existing_shim = ROOT / ".tmp/_ffmpeg_shim/ffmpeg.exe"
    if _existing_shim.exists():
        os.environ["PATH"] = str(_existing_shim.parent) + os.pathsep + os.environ.get("PATH", "")
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


_BRAND_CASE = [
    (re.compile(r"work\s?hives?\s?ph\.?\s?com", re.I), "workhiveph.com"),
    (re.compile(r"work\s?hives\b", re.I), "WorkHive"),
    (re.compile(r"workhive\b", re.I), "WorkHive"),
]


def _brand_case(text: str) -> str:
    """Deterministic brand casing on caption text (Whisper writes 'Workhive' /
    'work hives.com' no matter what the prompt says)."""
    for rx, rep in _BRAND_CASE:
        text = rx.sub(rep, text)
    return text


CAPTION_MAX_WORDS = 6   # one short kinetic chunk at a time (social-native pacing)

_CLAUSE_SPLIT = re.compile(r"(?<=[,.!?;:])\s+")


def _chunk_segment(seg: dict) -> list[tuple[float, float, str]]:
    """Split one Whisper segment into short caption chunks: first on CLAUSE
    boundaries (so a chunk never cuts mid-phrase like 'So next I…'), then cap
    each clause at ≤CAPTION_MAX_WORDS. Time is distributed by word count."""
    words_all = seg["text"].split()
    if not words_all:
        return []
    pieces: list[list[str]] = []
    for clause in _CLAUSE_SPLIT.split(seg["text"].strip()):
        cw = clause.split()
        for i in range(0, len(cw), CAPTION_MAX_WORDS):
            piece = cw[i:i + CAPTION_MAX_WORDS]
            if piece:
                pieces.append(piece)
    # merge tiny clause-tails (a lone 'trips,' flashing for 0.3s looks glitchy)
    merged: list[list[str]] = []
    for p in pieces:
        if merged and (len(p) <= 2 or len(merged[-1]) <= 2) and len(merged[-1]) + len(p) <= CAPTION_MAX_WORDS + 2:
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    pieces = merged
    span = max(0.2, float(seg["end"]) - float(seg["start"]))
    total = sum(len(p) for p in pieces) or 1
    out, t = [], float(seg["start"])
    for p in pieces:
        d = span * (len(p) / total)
        out.append((t, t + d, " ".join(p)))
        t += d
    return out


def _align_to_source(seg_text: str, source_words: list[str]) -> str:
    """Replace a Whisper guess with the matching span of the REAL narration.

    We WROTE the narration — Whisper's job is timing, not words. For each
    transcribed segment, find the best-matching window of source words
    (difflib ratio); replace when confident. Kills mishears like
    'tracked'→'trapped' and 'So next time'→'So next I' at the root."""
    import difflib
    sw = seg_text.split()
    if not sw or not source_words:
        return seg_text
    target = " ".join(w.lower().strip(".,!?;:") for w in sw)
    best, best_r = None, 0.55     # confidence floor — below it keep Whisper's text
    for n in (len(sw) - 1, len(sw), len(sw) + 1, len(sw) + 2):
        if n < 1:
            continue
        for i in range(0, max(1, len(source_words) - n + 1)):
            cand = source_words[i:i + n]
            r = difflib.SequenceMatcher(
                None, target, " ".join(w.lower().strip(".,!?;:") for w in cand)).ratio()
            if r > best_r:
                best, best_r = " ".join(cand), r
    return best or seg_text


def generate_srt(narration_path: Path, out_srt: Path, model_size: str = "base",
                 align_text: str = None) -> bool:
    """Transcribe narration and write an SRT file. Returns True on success.
    align_text = the REAL narration script; when given, caption words come from
    the source and Whisper provides only the timing."""
    try:
        _ensure_ffmpeg_on_path()
        import whisper
        print(f"  Whisper: transcribing narration ({model_size} model)...")
        model  = whisper.load_model(model_size)
        result = model.transcribe(str(narration_path), fp16=False, language="en",
                                  initial_prompt=WHISPER_PROMPT)

        source_words = (align_text or "").split()
        aligned = 0
        srt_lines, n = [], 0
        for seg in result["segments"]:
            if source_words:
                fixed = _align_to_source(seg["text"].strip(), source_words)
                if fixed != seg["text"].strip():
                    aligned += 1
                seg = {**seg, "text": fixed}
            for (cs, ce, ctext) in _chunk_segment(seg):
                n += 1
                srt_lines.append(f"{n}\n{_srt_time(cs)} --> {_srt_time(ce)}\n{_brand_case(ctext.strip())}\n")

        out_srt.write_text("\n".join(srt_lines), encoding="utf-8")
        print(f"  Captions: {len(result['segments'])} segments → {n} clause chunks"
              + (f" ({aligned} aligned to the script source)" if source_words else "")
              + f" → {out_srt.name}")
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
    # libass scales FontSize by video-height/PlayResY(288): 22 ≈ 69px at 900p —
    # comfortably above the ≥48px@1080 sound-off readability bar (Meta guidance;
    # 85% of social video plays muted).
    # NOTE: ASS colours are &H00BBGGRR (byte-swapped). '&H00D88A0E' rendered BLUE
    # (D8 blue / 8A green / 0E red) — caught by frame inspection 2026-06-10.
    # Brand orange #D88A0E in ASS byte order = &H000E8AD8.
    "FontName=Arial,FontSize=22,Bold=1,"
    "PrimaryColour=&H00FFFFFF,"      # white text
    "OutlineColour=&H000E8AD8,"      # orange outline (#D88A0E in BGR)
    "BorderStyle=1,Outline=2,Shadow=1,"
    "Alignment=2,MarginV=40"         # bottom-center, inside the caption-safe band
)

# Whisper mis-hears brand words on PH-accented narration ("workhiveph.com" →
# "work hives.com", "tracked" → "trapped"). The initial prompt biases decoding
# toward the real platform vocabulary.
WHISPER_PROMPT = (
    "WorkHive, workhiveph.com, logbook, PM, preventive maintenance, downtime, "
    "MTBF, OEE, hive, dashboard, tracked, spare parts, plant, supervisor, technician."
)


# ── Core assembly ─────────────────────────────────────────────────────────────

def assemble(
    idea_id:        str,
    voice_key:      str  = "james",
    music_path:     Path = None,
    scene_clip:     Path = None,       # Kling/Pexels/Remotion scene → full background, UI = overlay
    hook_clip:      Path = None,       # hook clip prepended before UI recording
    recording_file: Path = None,       # explicit recording override (skip auto-pick)
    avatar_clip:    Path = None,       # lip-synced brand-persona narrator → circular corner bubble
    captions:       bool = True,
    output_path:    Path = None,
    pip_windows:    dict = None,       # {'demo': (s,e), 'cta_start': s} → dynamic PiP emphasis
    brand_logo:     bool = True,       # False when the scene is a branded Remotion render (one-logo policy)
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
    # -ss 1.4 trims the brief blank/white first frames a screen-record starts with
    # (about:blank before the feature page paints).
    norm_video = tmp / "recording_norm.mp4"
    _run_ffmpeg([
        "-ss", "1.4",
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
        # Fill the narration with INPUT-side -stream_loop (re-reads the file from
        # disk) NOT the `loop` video filter: that filter buffers every looped frame
        # in RAM, and at size=32767 it's a ~45GB allocation that OOMs on a busy box
        # (ffmpeg ENOMEM -12, "Cannot allocate memory"). With -t, a full-length
        # storyboard scene never actually loops; a short Pexels clip repeats cheaply.
        _run_ffmpeg([
            "-stream_loop", "-1",
            "-i", str(scene_clip),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",
            "-t", str(narr_dur),
            str(norm_scene),
        ], "normalise scene clip (loop to fill if short)")

        pip_video = tmp / "pip.mp4"
        # Dynamic PiP emphasis (the 90/10 product-dominant rule):
        #   • normal beats  → 38% bottom-right corner (thin orange frame so the
        #     dark UI pops off the navy scene — was navy-on-navy, invisible)
        #   • the DEMO beat → the UI becomes the HERO: 62%, centered
        #   • CTA beats     → PiP hidden entirely (fixes the EndCard collision)
        # Falls back to the static 38% overlay when no windows are provided.
        win = pip_windows or {}
        demo = win.get("demo")
        cta_s = win.get("cta_start")

        def _and(*exprs):
            live = [e for e in exprs if e]
            return "*".join(live) if live else "1"

        small_en = _and(
            f"(lt(t\\,{demo[0]:.2f})+gte(t\\,{demo[1]:.2f}))" if demo else "",
            f"lt(t\\,{cta_s:.2f})" if cta_s is not None else "",
        )
        big_en = f"between(t\\,{demo[0]:.2f}\\,{demo[1]:.2f})" if demo else "0"

        if demo or cta_s is not None:
            print(f"  PiP windows: demo={demo}  cta_start={cta_s}  (hero 62% during demo, hidden on CTA)")
            filter_c = (
                "[1:v]split[u1][u2];"
                "[u1]scale=trunc(iw*0.38/2)*2:-2,pad=iw+6:ih+6:3:3:color=0xF7A21B[small];"
                "[u2]scale=trunc(iw*0.62/2)*2:-2,pad=iw+8:ih+8:4:4:color=0xF7A21B[big];"
                f"[0:v][small]overlay=W-w-24:H-h-24:enable='{small_en}'[v1];"
                f"[v1][big]overlay=(W-w)/2:(H-h)/2:enable='{big_en}'[vid]"
            )
        else:
            filter_c = (
                "[1:v]scale=trunc(iw*0.38/2)*2:-2[ui_s];"
                "[ui_s]pad=iw+6:ih+6:3:3:color=0xF7A21B[ui_b];"
                "[0:v][ui_b]overlay=W-w-24:H-h-24[vid]"
            )
        _run_ffmpeg([
            "-i", str(norm_scene),   # [0] background scene
            "-i", str(norm_video),   # [1] UI overlay
            "-filter_complex", filter_c,
            "-map", "[vid]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-t", str(narr_dur),
            str(pip_video),
        ], "compose PiP: scene + UI overlay (dynamic emphasis)")
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

    # ── Step 2.5: Brand-persona narrator bubble (avatar) ─────────────────────
    # A lip-synced persona (Wav2Lip) becomes a circular presenter bubble in the
    # bottom-left, persistent for the whole video. Its own audio is dropped — the
    # narration mp3 stays the master clock, and since the avatar was generated
    # FROM that narration, the lips stay in sync.
    if avatar_clip and avatar_clip.exists():
        av_video = tmp / "with_avatar.mp4"
        D  = 200            # avatar bubble diameter
        R  = D + 12         # orange ring diameter
        dc = D // 2
        rc = R // 2
        _run_ffmpeg([
            "-i", str(main_video),    # [0] composited scene + UI
            "-i", str(avatar_clip),   # [1] lip-synced persona
            "-filter_complex",
            f"[1:v]scale={D}:{D},format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
            f"a='if(gt((X-{dc})*(X-{dc})+(Y-{dc})*(Y-{dc}),{dc*dc}),0,255)'[avc];"
            f"color=c=0xF7A21B:s={R}x{R}:d={narr_dur:.2f},format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
            f"a='if(gt((X-{rc})*(X-{rc})+(Y-{rc})*(Y-{rc}),{rc*rc}),0,255)'[ring];"
            "[ring][avc]overlay=(W-w)/2:(H-h)/2[bub];"
            "[0:v][bub]overlay=40:H-h-40[vid]",
            "-map", "[vid]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-t", str(narr_dur),
            str(av_video),
        ], "overlay brand-persona narrator bubble")
        main_video = av_video

    # ── Step 3: Mix audio (narration + music) ────────────────────────────────
    silent_mp4 = tmp / "with_audio.mp4"

    if music_path and music_path.exists():
        _run_ffmpeg([
            "-i", str(main_video),
            "-i", str(narration),
            "-stream_loop", "-1", "-i", str(music_path),   # loop music from disk, not via aloop's in-RAM sample buffer (same OOM class as the scene loop)
            "-filter_complex",
            "[1:a]volume=1.0[narr];[2:a]volume=0.15[music];"
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
    # Captions: words from the SCRIPT (source of truth), Whisper for timing only.
    align_text = None
    try:
        sf = idea.get("script_file")
        if sf and Path(sf).exists():
            import sys as _sys
            _t = str(Path(__file__).resolve().parent)
            if _t not in _sys.path:
                _sys.path.insert(0, _t)
            from storyboard import parse_script_beats
            beats, _rng = parse_script_beats(Path(sf).read_text(encoding="utf-8"))
            align_text = " ".join(b["narration"] for b in beats if b.get("narration"))
    except Exception as _exc:
        print(f"  [captions] script alignment unavailable ({_exc}) — Whisper text as-is")
    has_captions = captions and generate_srt(narration, srt_path, align_text=align_text)
    # One-logo policy: a branded Remotion scene already carries the wordmark —
    # the watermark overlay is only for unbranded (Pexels) footage.
    has_logo     = LOGO_PATH.exists() and brand_logo

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
