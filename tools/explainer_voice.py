#!/usr/bin/env python3
"""
explainer_voice.py — Edge-TTS "James" narration + per-word timing for the
"WorkHive Explains" educational video engine.
==========================================================================
WHY THIS EXISTS: the kinetic captions must light up word-by-word EXACTLY as
James speaks them. Edge-TTS emits WordBoundary events (offset + duration, in
100-nanosecond ticks) as it synthesises, so we capture them alongside the audio.
That is the whole reason NO Whisper is needed: the TTS engine already tells us
when each word is spoken. (Roadmap CONTENT_CREATION_ROADMAP.md sec 9.)

Voice: "james" -> en-PH-JamesNeural, the Philippine-accented English male voice
the platform already uses (see tools/notebooklm_client.py VOICE_MAP).

Per narrated beat we emit, into <audio_dir>/:
  beat_<i>.mp3         the narration audio (Edge-TTS)
  beat_<i>.words.json  [{ "text", "start_ms", "end_ms" }, ...]  (beat-relative)
and a manifest.json tying them together with probed durations.

Public API:
  synth_beat(text, out_mp3, voice="en-PH-JamesNeural") -> list[word dict]
  synth_spec(spec, audio_dir, voice="en-PH-JamesNeural") -> manifest dict
  media_duration_s(path) -> float

Zero new dependencies: edge-tts (installed) + ffmpeg via imageio_ffmpeg (installed).
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

JAMES = "en-PH-JamesNeural"
_MAX_ATTEMPTS = 3
_BACKOFFS_S = [0, 2, 5]

# UTF-8 stdout so the middot / brand glyphs never crash a cp1252 console
# (same guard the other video tools use).
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")


def media_duration_s(path: str | Path) -> float:
    """Probe a media file's duration (seconds) by parsing ffmpeg's stderr banner.
    Dependency-free (ffmpeg is already bundled via imageio_ffmpeg). Returns 0.0
    if it cannot be determined."""
    try:
        res = subprocess.run([_ffmpeg_exe(), "-i", str(path)],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return 0.0
    m = _DUR_RE.search(res.stderr or "")
    if not m:
        return 0.0
    h, mm, ss = m.groups()
    return int(h) * 3600 + int(mm) * 60 + float(ss)


async def _synth_async(text: str, voice: str, out_mp3: Path) -> dict:
    """One Edge-TTS pass: stream audio to out_mp3 and collect timing metadata.
    edge-tts offset/duration are in 100ns ticks -> divide by 10000 for ms.

    Some voices (incl. en-PH-JamesNeural) emit SentenceBoundary rather than
    WordBoundary events. We collect BOTH; the caller derives per-word timing from
    whichever is available (see synth_beat)."""
    import edge_tts
    words: list[dict] = []
    sentences: list[dict] = []
    got_audio = False
    communicate = edge_tts.Communicate(text, voice)
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            ctype = chunk.get("type")
            if ctype == "audio" and chunk.get("data"):
                f.write(chunk["data"])
                got_audio = True
            elif ctype == "WordBoundary":
                s = chunk["offset"] / 10000.0
                d = chunk["duration"] / 10000.0
                words.append({"text": chunk["text"], "start_ms": round(s, 1), "end_ms": round(s + d, 1)})
            elif ctype == "SentenceBoundary":
                s = chunk["offset"] / 10000.0
                d = chunk["duration"] / 10000.0
                sentences.append({"text": chunk["text"], "start_ms": s, "end_ms": s + d})
    return {"got_audio": got_audio, "words": words, "sentences": sentences}


def _interp_span(text: str, start_ms: float, end_ms: float) -> list[dict]:
    """Distribute per-word timings across [start_ms, end_ms], weighting each word
    by its length (a good proxy for spoken duration). Gives word-level kinetic
    reveal even when the voice only reports sentence-level boundaries."""
    toks = re.findall(r"\S+", text or "")
    if not toks:
        return []
    span = max(1.0, end_ms - start_ms)
    weights = [len(t) + 1 for t in toks]
    tot = sum(weights)
    out, t = [], start_ms
    for tok, w in zip(toks, weights):
        dur = span * (w / tot)
        out.append({"text": tok, "start_ms": round(t, 1), "end_ms": round(t + dur, 1)})
        t += dur
    return out


# ── spoken-form normalization (fix TTS mispronunciation) ─────────────────────
# Edge-TTS mangles run-together brand/URL tokens: "workhiveph.com" came out as
# "work h-i-v-eph dot com" (Ian, 2026-07-01). We synthesise a PRONOUNCEABLE form
# for the AUDIO while the on-screen caption keeps the REAL text (decoupled below).
_SPOKEN_SUBS = [
    (re.compile(r"\bworkhiveph\.com\b", re.I), "WorkHive P H dot com"),
    (re.compile(r"\bworkhive\.ph\b", re.I), "WorkHive dot P H"),
    (re.compile(r"\bworkhiveph\b", re.I), "WorkHive P H"),
    (re.compile(r"https?://", re.I), ""),
    (re.compile(r"\.com\b", re.I), " dot com"),
    # Companion names (Ian's phonetics 2026-07-03): Hezekiah = "He Ze Ki Yah",
    # Zaniah = "Zah Nah Yah". Audio-only; the caption keeps the real spelling.
    (re.compile(r"\bHezekiah\b"), "Hezekeeyah"),
    # "Zahnahyah" got parsed as "Zahn-ah-yah"; force the 3 syllables with spaces
    # (Ian 2026-07-03: "Zah Nah Yah", NOT "Zan Hahyah").
    (re.compile(r"\bZaniah\b"), "Zah Nah Yah"),
]


def spoken_form(text: str) -> str:
    """Rewrite a display string into a TTS-pronounceable one (URLs, run-together
    brand tokens). Applied ONLY to the audio, never to the caption/pack."""
    for pat, rep in _SPOKEN_SUBS:
        text = pat.sub(rep, text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+", (text or "").strip()) if s]


def _derive_words(res: dict, display_text: str, audio_dur_ms: float) -> list[dict]:
    """Per-word caption timings for the DISPLAY text, mapped onto the audio. When
    display and spoken sentence counts match, interpolate each display sentence
    across the matching spoken sentence's [start,end] (keeps rough sync while the
    caption shows the real URL, not the pronounceable spelling)."""
    disp = _sentences(display_text)
    spk = res.get("sentences") or []
    if spk and len(spk) == len(disp):
        out = []
        for ds, ss in zip(disp, spk):
            out += _interp_span(ds, ss["start_ms"], ss["end_ms"])
        if out:
            return out
    if res.get("words"):   # some voices DO give word boundaries (spoken tokens)
        return res["words"]
    total = audio_dur_ms if audio_dur_ms > 0 else max(1000.0, len(display_text) * 62.0)
    return _interp_span(display_text, 100.0, total)


def synth_beat(text: str, out_mp3: str | Path, voice: str = JAMES) -> list[dict]:
    """Synthesise one narration line to out_mp3 and return its per-word timings.
    Retries (Edge's websocket is occasionally flaky from PH networks); raises
    loudly if every attempt fails so the caller surfaces a real error, mirroring
    tools/tts_engine.py semantics."""
    out_mp3 = Path(out_mp3)
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        backoff = _BACKOFFS_S[attempt - 1]
        if backoff:
            print(f"  [voice] waiting {backoff}s before retry...")
            time.sleep(backoff)
        try:
            # audio synthesised from the PRONOUNCEABLE form; caption uses `text`
            res = asyncio.run(_synth_async(spoken_form(text), voice, out_mp3))
        except Exception as exc:  # noqa: BLE001  (network / websocket flake)
            failures.append(f"attempt {attempt}: {type(exc).__name__}: {str(exc)[:120]}")
            print(f"  [voice] attempt {attempt}/{_MAX_ATTEMPTS} failed: {failures[-1]}")
            continue
        # Success is defined by AUDIO, not word events: James reports sentence
        # boundaries, and we interpolate per-word timing from them.
        if out_mp3.exists() and out_mp3.stat().st_size > 1000 and res["got_audio"]:
            audio_dur_ms = media_duration_s(out_mp3) * 1000.0
            words = _derive_words(res, text, audio_dur_ms)
            src = "word" if res["words"] else ("sentence-interp" if res["sentences"] else "text-interp")
            print(f"  [voice] OK ({out_mp3.stat().st_size // 1024} KB, {len(words)} words, {src})")
            return words
        failures.append(f"attempt {attempt}: no audio produced (empty/truncated MP3)")
        print(f"  [voice] attempt {attempt}/{_MAX_ATTEMPTS}: empty output")
    raise RuntimeError(
        f"Edge-TTS failed after {_MAX_ATTEMPTS} attempts (voice={voice}). "
        "Usually a network issue reaching Microsoft's TTS endpoint.\n  "
        + "\n  ".join(failures)
    )


def _beat_narrations(spec: dict) -> list[tuple[int, dict, str]]:
    """Return (index, beat, narration) for every beat that actually has spoken
    narration. Beats without narration (e.g. a silent end card) are skipped."""
    out = []
    for i, beat in enumerate(spec.get("beats", [])):
        narr = (beat.get("narration") or "").strip()
        if narr:
            out.append((i, beat, narr))
    return out


def synth_spec(spec: dict, audio_dir: str | Path, voice: str = JAMES) -> dict:
    """Synthesise every narrated beat of an ExplainerSpec into audio_dir and
    write a manifest.json. Returns the manifest:
        { "voice", "beats": [ {beat_index, kind, mp3, words_file,
                               duration_s, words:[...]} ] }
    """
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"voice": voice, "beats": []}
    for order, (bidx, beat, narr) in enumerate(_beat_narrations(spec)):
        mp3 = audio_dir / f"beat_{order:02d}.mp3"
        words_file = audio_dir / f"beat_{order:02d}.words.json"
        print(f"  [voice] beat {order} ({beat.get('kind','?')}): "
              f"\"{narr[:56]}{'...' if len(narr) > 56 else ''}\"")
        words = synth_beat(narr, mp3, voice=voice)
        words_file.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
        dur = media_duration_s(mp3)
        if dur <= 0 and words:
            dur = (words[-1]["end_ms"] / 1000.0) + 0.4  # graceful fallback
        manifest["beats"].append({
            "beat_index": bidx,
            "order": order,
            "kind": beat.get("kind", ""),
            "narration": narr,
            "mp3": str(mp3),
            "words_file": str(words_file),
            "duration_s": round(dur, 3),
            "words": words,
        })
    (audio_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(b["duration_s"] for b in manifest["beats"])
    print(f"  [voice] synthesised {len(manifest['beats'])} beats, {total:.1f}s narration total")
    return manifest


# ── CLI (handy for probing a single line) ─────────────────────────────────────

def _demo() -> int:
    out = Path(".tmp/explainer_voice_demo")
    out.mkdir(parents=True, exist_ok=True)
    words = synth_beat(
        "Three of your best numbers can still hide a problem on the plant floor.",
        out / "demo.mp3")
    print(json.dumps(words[:6], indent=2))
    print(f"duration: {media_duration_s(out / 'demo.mp3'):.2f}s")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        raise SystemExit(_demo())
    print(__doc__)
