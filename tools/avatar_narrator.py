"""
Generate a lip-synced brand-persona NARRATOR clip from an idea's narration, using
the local (patched) Wav2Lip install in .tmp/Wav2Lip. Output drops into the
video_assembler as an `avatar_clip` (circular presenter bubble).

Free, offline, CPU. A ~60s narration takes ~10-20 min on CPU.

Windows notes baked in:
  - Wav2Lip's static-image check is args.face.split('.')[1]; the project's ABSOLUTE
    path contains "Industry 4.0" (a dot), so we run with cwd=.tmp/Wav2Lip and clean
    RELATIVE input names.
  - inference.py's final mux is shell=True (patched) and finds ffmpeg.exe via cwd/PATH.
  - --outfile must be a relative, space-free name (the mux command is unquoted).

Usage:
    python tools/avatar_narrator.py --idea idea_013 --voice james
"""
import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT        = Path(__file__).parent.parent
WAV2LIP_DIR = ROOT / ".tmp" / "Wav2Lip"
SHIM_DIR    = ROOT / ".tmp" / "_ffmpeg_shim"
SHIM_FFMPEG = SHIM_DIR / "ffmpeg.exe"
VOICE_DIR   = ROOT / ".tmp" / "voice_files"
OUT_DIR     = ROOT / ".tmp" / "avatar_outputs"
BRAND       = ROOT / "brand_assets"

# voice_key → brand persona portrait
PERSONA = {
    "james":    BRAND / "James.png",
    "guy":      BRAND / "James.png",
    "ryan":     BRAND / "James.png",
    "angelo":   BRAND / "James.png",
    "rosa":     BRAND / "Rosa.png",
    "jenny":    BRAND / "Rosa.png",
    "blessica": BRAND / "Rosa.png",
}


def _ffmpeg() -> str:
    if SHIM_FFMPEG.exists():
        return str(SHIM_FFMPEG)
    return shutil.which("ffmpeg") or "ffmpeg"


def _find_narration(idea_id: str, voice_key: str) -> Path:
    p = VOICE_DIR / f"{idea_id}_{voice_key}.mp3"
    if not p.exists():
        raise FileNotFoundError(f"No narration {p.name} — generate the voice first")
    return p


def generate_avatar(idea_id: str, voice_key: str = "james") -> Path:
    """Render a full-length lip-synced narrator. Returns the avatar mp4 path."""
    if not (WAV2LIP_DIR / "inference.py").exists():
        raise RuntimeError(f"Wav2Lip not set up at {WAV2LIP_DIR}")
    ckpt = WAV2LIP_DIR / "checkpoints" / "wav2lip_gan.pth"
    if not ckpt.exists():
        raise RuntimeError("wav2lip_gan.pth checkpoint missing")

    persona = PERSONA.get(voice_key.lower(), BRAND / "James.png")
    if not persona.exists():
        raise FileNotFoundError(f"Persona image not found: {persona}")

    narration = _find_narration(idea_id, voice_key)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Reuse an already-rendered avatar — Wav2Lip is ~10-20 min on CPU, so never
    # regenerate if a valid clip already exists for this idea+voice.
    dst = OUT_DIR / f"{idea_id}_{voice_key}_avatar.mp4"
    if dst.exists() and dst.stat().st_size > 100_000:
        print(f"  Avatar: reusing existing {dst.name}")
        return dst

    ff = _ffmpeg()
    # Stage clean, space-free relative inputs inside the Wav2Lip dir.
    face_in  = WAV2LIP_DIR / "input_face.png"
    audio_in = WAV2LIP_DIR / "input_audio.wav"
    shutil.copy2(persona, face_in)
    # Decode narration → 16k mono wav (avoids mp3-decode quirks inside Wav2Lip).
    subprocess.run(
        [ff, "-y", "-i", str(narration), "-ar", "16000", "-ac", "1", str(audio_in)],
        capture_output=True, text=True,
    )
    # Make sure ffmpeg.exe is resolvable for inference.py's internal mux.
    if SHIM_FFMPEG.exists():
        shutil.copy2(SHIM_FFMPEG, WAV2LIP_DIR / "ffmpeg.exe")

    env = dict(os.environ)
    env["PATH"] = str(SHIM_DIR) + os.pathsep + env.get("PATH", "")
    if SHIM_FFMPEG.exists():
        env["IMAGEIO_FFMPEG_EXE"] = str(SHIM_FFMPEG)

    rel_out = "output_avatar.mp4"   # relative + space-free (mux command is unquoted)
    print(f"  Wav2Lip: lip-syncing {persona.name} to {narration.name} (CPU, be patient)...")
    proc = subprocess.run(
        [sys.executable, "inference.py",
         "--checkpoint_path", "checkpoints/wav2lip_gan.pth",
         "--face", "input_face.png",
         "--audio", "input_audio.wav",
         "--outfile", rel_out],
        cwd=str(WAV2LIP_DIR), env=env,
        capture_output=True, text=True,
    )
    produced = WAV2LIP_DIR / rel_out
    if not produced.exists():
        raise RuntimeError(
            "Wav2Lip produced no output.\n"
            + (proc.stdout or "")[-600:] + "\n" + (proc.stderr or "")[-1200:]
        )

    dst = OUT_DIR / f"{idea_id}_{voice_key}_avatar.mp4"
    shutil.copy2(produced, dst)
    print(f"  Avatar: {dst.name}")
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate a brand-persona narrator avatar")
    ap.add_argument("--idea", required=True)
    ap.add_argument("--voice", default="james")
    args = ap.parse_args()
    out = generate_avatar(args.idea, args.voice)
    print(f"OK: {out}  ({out.stat().st_size/1_000_000:.1f} MB)")
