"""
WorkHive TTS Engine
Edge TTS (Microsoft) with retry-and-fail-loud semantics.

Edge TTS is run in a SUBPROCESS with a hard timeout so a hung websocket can't
block the Flask thread. We retry a few times with backoff because the Edge
websocket is occasionally flaky from PH networks; if every attempt fails we
raise loudly so the UI surfaces a real error.

By DEFAULT we do NOT fall back to a different provider: gTTS has no voice
selection, so a SILENT fallback would hand the user a generic speaker instead of
the James/Rosa/Jenny/etc. they picked — looking like a bug where the voice
"changed to someone else."

OPT-IN fallback (`allow_fallback_voice=True`): when Edge TTS is down (it had a
multi-hour outage on 2026-06-10) and the caller would rather finish a produce
with a placeholder voice than fail, gTTS is used — but the swap is made LOUD, not
silent: a `<out>.VOICE_FALLBACK.txt` marker is written next to the audio and a
warning is printed, so the user knows to re-produce for the chosen voice once
Edge is back. The default (no flag) keeps the original fail-loud behaviour.
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


def _gtts_attempt(text: str, out_path: Path) -> tuple[bool, str]:
    """Opt-in placeholder voice. gTTS (Google Translate TTS) has no voice
    selection — it is a stand-in, not the chosen speaker."""
    try:
        from gtts import gTTS
    except ImportError:
        return False, "gTTS not installed (pip install gTTS)"
    try:
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        gTTS(text=text, lang="en").save(str(out_path))
    except Exception as exc:  # noqa: BLE001  (network/Google error)
        return False, f"gTTS error: {exc}"
    if not out_path.exists() or out_path.stat().st_size <= 1000:
        return False, "no audio produced (empty or truncated MP3)"
    return True, ""


def _write_fallback_marker(out_path: Path, voice_id: str, failures: list[str]) -> None:
    """Make the voice swap LOUD: a sibling marker the UI/assembler can surface."""
    marker = out_path.with_suffix(out_path.suffix + ".VOICE_FALLBACK.txt")
    marker.write_text(
        "PLACEHOLDER VOICE — this audio was made with gTTS, NOT the selected voice "
        f"'{voice_id}'.\n"
        "Edge TTS was unavailable, so the produce completed with a generic speaker.\n"
        "RE-PRODUCE this clip once Edge TTS is reachable to get the real voice.\n\n"
        "Edge failures:\n  " + "\n  ".join(failures) + "\n",
        encoding="utf-8",
    )


def generate_tts(text: str, voice_id: str, out_path: Path,
                 allow_fallback_voice: bool = False) -> Path:
    """
    Generate speech audio at out_path using Edge TTS, with retries.

    If every Edge attempt fails:
      • allow_fallback_voice=False (default) -> raise RuntimeError (fail loud).
      • allow_fallback_voice=True            -> use gTTS as a clearly-labelled
        placeholder (writes a <out>.VOICE_FALLBACK.txt marker) so a produce can
        complete during an Edge outage. Raises only if gTTS also fails.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    edge_exe = _edge_tts_exe()
    if not edge_exe:
        failures.append("edge-tts CLI not found (pip install edge-tts)")
    else:
        for attempt in range(1, EDGE_MAX_ATTEMPTS + 1):
            backoff = EDGE_BACKOFFS_S[attempt - 1]
            if backoff:
                print(f"  [tts] waiting {backoff}s before retry...")
                time.sleep(backoff)

            print(f"  [tts] Edge TTS attempt {attempt}/{EDGE_MAX_ATTEMPTS} (voice={voice_id})...")
            ok, reason = _edge_attempt(edge_exe, text, voice_id, out_path)
            if ok:
                print(f"  [tts] Edge TTS OK ({out_path.stat().st_size // 1024} KB)")
                # A previous fallback marker is now stale — remove it.
                stale = out_path.with_suffix(out_path.suffix + ".VOICE_FALLBACK.txt")
                if stale.exists():
                    try:
                        stale.unlink()
                    except OSError:
                        pass
                return out_path

            print(f"  [tts] attempt {attempt} failed: {reason}")
            failures.append(f"attempt {attempt}: {reason}")

    # Every Edge path exhausted.
    if allow_fallback_voice:
        print("  [tts] \033[93mEdge TTS unavailable -- using gTTS PLACEHOLDER voice "
              "(allow_fallback_voice=True)\033[0m")
        ok, reason = _gtts_attempt(text, out_path)
        if ok:
            _write_fallback_marker(out_path, voice_id, failures)
            print(f"  [tts] \033[93m[!] placeholder voice written ({out_path.stat().st_size // 1024} KB). "
                  f"Re-produce for '{voice_id}' once Edge is back -- see {out_path.name}.VOICE_FALLBACK.txt\033[0m")
            return out_path
        failures.append(f"gTTS fallback: {reason}")

    raise RuntimeError(
        "Edge TTS failed{fb} (voice={v}). "
        "This is usually a network issue reaching Microsoft's TTS endpoint — "
        "check your connection / VPN / firewall and try again.{hint}\n  "
        "{details}".format(
            v=voice_id,
            fb="" if not edge_exe else f" after {EDGE_MAX_ATTEMPTS} attempts",
            hint="" if allow_fallback_voice else
                 " (pass allow_fallback_voice=True to finish with a placeholder gTTS voice)",
            details="\n  ".join(failures),
        )
    )
