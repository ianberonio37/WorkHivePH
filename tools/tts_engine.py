"""
WorkHive TTS Engine
Edge TTS (Microsoft) with retry-and-fail-loud semantics.

Edge TTS is run in a SUBPROCESS with a hard timeout so a hung websocket can't
block the Flask thread. We retry a few times with backoff because the Edge
websocket is occasionally flaky from PH networks; if every attempt fails we
raise loudly so the UI surfaces a real error.

We intentionally do NOT fall back to a different provider (e.g. gTTS): gTTS
has no voice selection, so a silent fallback would hand the user a generic
speaker instead of the James/Rosa/Jenny/etc. they picked — looking like a bug
where the voice "changed to someone else."
"""

import subprocess
import sys
import time
from pathlib import Path

EDGE_TIMEOUT_S    = 60                  # Hard ceiling per attempt
EDGE_MAX_ATTEMPTS = 3                   # Total tries before giving up
EDGE_BACKOFFS_S   = [0, 2, 5]           # Wait before attempt N (len == MAX_ATTEMPTS)


def _edge_tts_exe() -> str | None:
    """Locate the edge-tts CLI binary. None if not installed."""
    import shutil
    cli = shutil.which("edge-tts")
    if cli:
        return cli
    scripts_dir = Path(sys.executable).parent / "Scripts"
    candidate = scripts_dir / "edge-tts.exe"
    if candidate.exists():
        return str(candidate)
    return None


def _edge_attempt(edge_exe: str, text: str, voice_id: str, out_path: Path) -> tuple[bool, str]:
    """One Edge TTS attempt. Returns (ok, reason_if_failed)."""
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
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EDGE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {EDGE_TIMEOUT_S}s (websocket hang)"
    except Exception as exc:
        return False, f"subprocess error: {exc}"

    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-200:]
        return False, f"rc={result.returncode}: {tail}"
    if not out_path.exists() or out_path.stat().st_size <= 1000:
        return False, "no audio produced (empty or truncated MP3)"
    return True, ""


def generate_tts(text: str, voice_id: str, out_path: Path) -> Path:
    """
    Generate speech audio at out_path using Edge TTS, with retries.
    Raises RuntimeError with details if every attempt fails.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    edge_exe = _edge_tts_exe()
    if not edge_exe:
        raise RuntimeError(
            "edge-tts CLI not found. Install with: pip install edge-tts"
        )

    failures: list[str] = []
    for attempt in range(1, EDGE_MAX_ATTEMPTS + 1):
        backoff = EDGE_BACKOFFS_S[attempt - 1]
        if backoff:
            print(f"  [tts] waiting {backoff}s before retry...")
            time.sleep(backoff)

        print(f"  [tts] Edge TTS attempt {attempt}/{EDGE_MAX_ATTEMPTS} (voice={voice_id})...")
        ok, reason = _edge_attempt(edge_exe, text, voice_id, out_path)
        if ok:
            print(f"  [tts] Edge TTS OK ({out_path.stat().st_size // 1024} KB)")
            return out_path

        print(f"  [tts] attempt {attempt} failed: {reason}")
        failures.append(f"attempt {attempt}: {reason}")

    raise RuntimeError(
        "Edge TTS failed after {n} attempts (voice={v}). "
        "This is usually a network issue reaching Microsoft's TTS endpoint — "
        "check your connection / VPN / firewall and try again.\n  "
        "{details}".format(
            n=EDGE_MAX_ATTEMPTS,
            v=voice_id,
            details="\n  ".join(failures),
        )
    )
