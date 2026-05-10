"""
WorkHive TTS Engine
Resilient text-to-speech with provider fallback.

Provider chain:
  1. Edge TTS (Microsoft) — natural-sounding, free, but flaky from PH networks.
     Run in a SUBPROCESS with hard timeout so a hung websocket can't block Flask.
  2. gTTS (Google Translate TTS) — synchronous HTTP, very reliable. Robotic
     compared to Edge but always works.

The orchestrator and per-stage voice route both call generate_tts() —
returns the path to the saved MP3 or raises if everything fails.
"""

import os
import subprocess
import sys
from pathlib import Path

EDGE_TIMEOUT_S = 60      # Hard ceiling for Edge TTS subprocess
GTTS_TIMEOUT_S = 30      # gTTS is HTTP, normally completes in 2-4s


# ── Edge TTS: subprocess (isolates flaky asyncio/websockets from Flask) ───────

def _edge_via_subprocess(text: str, voice_id: str, out_path: Path) -> bool:
    """
    Shell out to the bundled `edge-tts` CLI. Returns True on success.
    Subprocess isolation means a hung Edge TTS can't block our Flask thread —
    the timeout will kill the child process cleanly.
    """
    edge_exe = _edge_tts_exe()
    if not edge_exe:
        print("  [tts] edge-tts CLI not found, skipping")
        return False

    if out_path.exists():
        try:
            out_path.unlink()
        except OSError:
            pass

    cmd = [
        edge_exe,
        "--voice",       voice_id,
        "--text",        text,
        "--write-media", str(out_path),
    ]
    print(f"  [tts] Edge TTS subprocess (voice={voice_id})...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EDGE_TIMEOUT_S,
        )
        if result.returncode != 0:
            print(f"  [tts] Edge TTS failed (rc={result.returncode}): {result.stderr[-200:]}")
            return False
        if out_path.exists() and out_path.stat().st_size > 1000:
            print(f"  [tts] Edge TTS OK ({out_path.stat().st_size // 1024} KB)")
            return True
        print("  [tts] Edge TTS produced no audio")
        return False
    except subprocess.TimeoutExpired:
        print(f"  [tts] Edge TTS timed out after {EDGE_TIMEOUT_S}s")
        return False
    except Exception as exc:
        print(f"  [tts] Edge TTS subprocess error: {exc}")
        return False


def _edge_tts_exe() -> str | None:
    """Locate the edge-tts CLI binary. None if not installed."""
    # Try PATH first
    import shutil
    cli = shutil.which("edge-tts")
    if cli:
        return cli
    # Fall back to the same Python's Scripts/ dir
    scripts_dir = Path(sys.executable).parent / "Scripts"
    candidate = scripts_dir / "edge-tts.exe"
    if candidate.exists():
        return str(candidate)
    return None


# ── gTTS fallback: synchronous HTTP, very reliable ────────────────────────────

def _gtts_fallback(text: str, voice_id: str, out_path: Path) -> bool:
    """
    Generate audio using Google Translate TTS. Voice ID is mapped to a
    language code (gTTS doesn't have voice variants, only languages and
    a slow/normal toggle).
    """
    try:
        from gtts import gTTS
    except ImportError:
        print("  [tts] gTTS not installed (pip install gtts)")
        return False

    # Map our voice IDs to gTTS language + tld for closest accent match
    # PH-accented English -> tld='com.au' (closest natural English accent for SE Asia)
    # Filipino -> lang='tl'
    # US/UK English -> tld='us'/'co.uk'
    lang, tld = "en", "com"
    if voice_id.startswith("fil-PH"):
        lang, tld = "tl", "com"
    elif voice_id.startswith("en-PH") or voice_id.startswith("en-AU"):
        lang, tld = "en", "com.au"
    elif voice_id.startswith("en-GB"):
        lang, tld = "en", "co.uk"
    elif voice_id.startswith("en-US"):
        lang, tld = "en", "us"

    print(f"  [tts] gTTS fallback (lang={lang}, tld={tld})...")
    try:
        if out_path.exists():
            out_path.unlink()
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.save(str(out_path))
        if out_path.exists() and out_path.stat().st_size > 1000:
            print(f"  [tts] gTTS OK ({out_path.stat().st_size // 1024} KB)")
            return True
        print("  [tts] gTTS produced no audio")
        return False
    except Exception as exc:
        print(f"  [tts] gTTS error: {exc}")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def generate_tts(text: str, voice_id: str, out_path: Path) -> Path:
    """
    Generate speech audio at out_path. Tries Edge TTS first (better quality),
    falls back to gTTS if Edge fails or hangs. Raises RuntimeError if both fail.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if _edge_via_subprocess(text, voice_id, out_path):
        return out_path

    print("  [tts] Edge TTS failed — falling back to gTTS")
    if _gtts_fallback(text, voice_id, out_path):
        return out_path

    raise RuntimeError(
        "Both Edge TTS and gTTS failed to generate audio. "
        "Check internet connectivity and try again."
    )
