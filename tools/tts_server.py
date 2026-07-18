#!/usr/bin/env python3
"""tts_server.py — self-hosted Piper neural TTS server (NATIVE_AI_ROADMAP.md #6, V-axis V2).

The "download the voice" SOVEREIGNTY path: the companion speaks in ONE branded Hezekiah/Zaniah voice,
OFFLINE, on the plant's own CPU, so the synthesized audio (and the text it speaks) never leaves the
plant, versus the device OS voice (`speechSynthesis`, inconsistent + device-variant). `wh-tts.js`
`speakPiper()` POSTs {text, persona} to WH_TTS_URL (this server) and plays the returned WAV; on any
miss it falls back to browser TTS (fail-open). Mirrors tools/asr_server.py + tools/embed_server.py
(self-hosted, env-gated, indigenous-first, CPU-only).

Voices (Piper, ~63MB each, downloaded to models/piper/ via `python -m piper.download_voices`):
  Hezekiah (technical / male)   = en_US-ryan-medium
  Zaniah   (strategist / female)= en_US-lessac-medium
(Swap either by changing VOICE_FILES + downloading the new .onnx — the branded voice is a config line.)

Run:  python tools/tts_server.py [port]     (default 8903)
  POST /tts   {text, persona}  -> audio/wav bytes
  GET  /health                 -> {ok:true, voices:[...]}
"""
import io
import json
import os
import sys
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from piper import PiperVoice

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8903
VOICES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "piper"))
VOICE_FILES = {
    "hezekiah": "en_US-ryan-medium.onnx",
    "zaniah":   "en_US-lessac-medium.onnx",
}
# Legacy persona aliases (pre-2026-05-20 rename) map to the current keys.
ALIASES = {"james": "hezekiah", "rosa": "zaniah"}
MAX_CHARS = 2000
_loaded: dict[str, PiperVoice] = {}

# Persona-name pronunciation fix (Ian-confirmed 2026-07-12): Piper (like most TTS) mis-says the
# uncommon proper nouns. Respell them phonetically BEFORE synthesis so the companion says its own
# name right. Applied to the spoken text, never persisted. (wh-tts.js mirrors this for the browser
# + edge-tts paths.)  Hezekiah -> "he-ze-kee-yah", Zaniah -> "zah-nah-yah".
import re as _re
_NAME_SAY = [
    (_re.compile(r"\bHezekiah\b", _re.IGNORECASE), "Hezehkeeyah"),
    (_re.compile(r"\bZaniah\b", _re.IGNORECASE), "Zah nah yah"),
]


def _respell_names(text: str) -> str:
    for pat, say in _NAME_SAY:
        text = pat.sub(say, text)
    return text


def _voice(persona: str) -> PiperVoice:
    key = ALIASES.get(persona, persona)
    if key not in VOICE_FILES:
        key = "zaniah"                      # default persona
    if key not in _loaded:
        _loaded[key] = PiperVoice.load(os.path.join(VOICES_DIR, VOICE_FILES[key]))
    return _loaded[key]


def synth_wav(text: str, persona: str) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        _voice(persona).synthesize_wav(_respell_names(text), wf)
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        # CORS: the browser (127.0.0.1:5000) calls this cross-origin (different port).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, apikey")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, json.dumps({"ok": True, "voices": list(VOICE_FILES)}).encode())
        else:
            self._send(404, json.dumps({"error": "POST /tts {text, persona}"}).encode())

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            text = str(data.get("text", "")).strip()[:MAX_CHARS]
            persona = str(data.get("persona", "zaniah")).lower()
            if not text:
                self._send(400, json.dumps({"error": "missing text"}).encode())
                return
            self._send(200, synth_wav(text, persona), "audio/wav")
        except Exception as e:  # noqa: BLE001 — never crash the server on one bad request
            self._send(500, json.dumps({"error": str(e)[:160]}).encode())


if __name__ == "__main__":
    # Warm both voices BEFORE binding (like asr_server warms the model), so the first
    # real request doesn't pay the load cost.
    print(f"tts_server: loading Piper voices from {VOICES_DIR} ...", flush=True)
    missing = [f for f in VOICE_FILES.values() if not os.path.exists(os.path.join(VOICES_DIR, f))]
    if missing:
        print(f"tts_server: MISSING voices {missing} — run: python -m piper.download_voices "
              f"{' '.join(v[:-5] for v in VOICE_FILES.values())} --data-dir models/piper", flush=True)
        sys.exit(1)
    for _p in VOICE_FILES:
        _voice(_p)
    print("tts_server: voices ready.", flush=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"tts_server: listening on :{PORT}  (POST /tts, GET /health)", flush=True)
    srv.serve_forever()
