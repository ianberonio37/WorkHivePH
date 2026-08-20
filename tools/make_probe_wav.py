#!/usr/bin/env python3
"""Generate .tmp/probe.wav — a 2s 440Hz tone used as Chromium's FAKE MICROPHONE.

WHY THIS EXISTS. voice-journal's write is audio-driven (mic -> voice-transcribe -> extraction ->
voice_journal_entries), so no amount of form-filling reaches it and the page looked un-probeable: its
CO/CK action rows sat owed with "needs a synthetic audio stream" as the reason. Chromium can play a WAV
as the microphone (--use-file-for-fake-audio-capture), which turns that into an ordinary page. This is
the build-the-structure move rather than recording the page as covered-by-nature.

The CONTENT does not matter: the transcribe call is intercepted by the prover and never issued, so what
is being exercised is the capture and in-flight control behaviour, not speech recognition. A plain tone
is therefore the honest fixture — it makes no claim about transcription accuracy.
"""
import math
import os
import struct

SR, SECS, AMP, FREQ = 16000, 2, 8000, 440
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp", "probe.wav")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    frames = b"".join(
        struct.pack("<h", int(AMP * math.sin(2 * math.pi * FREQ * t / SR))) for t in range(SR * SECS)
    )
    with open(OUT, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, SR, SR * 2, 2, 16))
        f.write(b"data" + struct.pack("<I", len(frames)) + frames)
    print(f"  wrote {OUT} ({os.path.getsize(OUT)} bytes, {SECS}s @ {SR}Hz)")


if __name__ == "__main__":
    main()
