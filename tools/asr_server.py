#!/usr/bin/env python3
"""asr_server.py — self-host Whisper transcription (NO external API, NO rate limit).

The durable voice-capacity fix (Ian, 2026-07-07: "external deps like Whisper are not reliable in
production with many users — can we do it indigenously so it's practical"). Today `voice-transcribe`
transcribes ONLY via Groq Whisper (`_shared/audio-chain.ts`) — a single external provider on a
free tier (~30 rpm org-shared) that fails HARD at scale ("All Whisper models unavailable"). A
self-hosted Whisper has NO per-request cap and no third-party outage surface.

This is the EXACT pattern already proven for embeddings (`tools/embed_server.py` → `bge-local` via
`BGE_EMBED_URL`) and TTS (browser SpeechSynthesis / optional `WH_TTS_EDGE_URL`). The Deno edge calls
this over the docker network; `audio-chain.ts` prefers it (envKey `WH_ASR_URL`) and falls back to
Groq only if it's unset/unavailable — so voice degrades gracefully, never goes fully dark.

Contract (raw-bytes body keeps the stdlib server simple — no multipart parsing):
  POST /transcribe            body = raw audio bytes (webm/mp4/wav/m4a); optional ?lang=en (force) →
                              {"text": "...", "lang": "tl"}   (lang = ISO-639-1 auto-detected)
  GET  /health                → {"ok": true, "model": "...", "device": "cpu"}

Run:  python tools/asr_server.py            # port 8902
      python tools/asr_server.py 8902 --model small --device cpu
Needs: pip install faster-whisper   (CTranslate2, no torch) + ffmpeg on PATH (audio decode).
       First run downloads the model (small ≈ 480MB, base ≈ 145MB). Multilingual — handles
       English + Filipino/Tagalog/Cebuano/Ilocano (the same languages Groq Whisper served).

Model choice for a factory floor (accuracy vs latency/RAM):
  base   (~145MB, ~1GB RAM)  — fastest, OK for clear English, weaker on code-switched Taglish
  small  (~480MB, ~2GB RAM)  — RECOMMENDED default: solid multilingual, ~real-time on CPU int8
  medium (~1.5GB, ~5GB RAM)  — best accuracy, needs a GPU or a beefy host for good latency
"""
from __future__ import annotations
import io
import json
import re
import sys
import tempfile
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DEFAULT_PORT = 8902
_MODEL = None
_MODEL_NAME = os.environ.get("WH_ASR_MODEL", "medium")  # base | small | medium | large-v3
# Ian chose `medium` (2026-07-07) for our Filipino field techs: English 100%, Taglish 78% (vs small's
# 67%). Cebuano stays ~40% even on medium (Whisper under-covers Cebuano — detects it as `tl`); the
# companion's intent-understanding compensates. Bump to large-v3 only if a Cebuano-heavy site needs it.
_DEVICE = os.environ.get("WH_ASR_DEVICE", "cpu")        # cpu | cuda
_COMPUTE = os.environ.get("WH_ASR_COMPUTE", "int8")     # int8 (cpu) | float16 (gpu)


def _model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel  # type: ignore
        _MODEL = WhisperModel(_MODEL_NAME, device=_DEVICE, compute_type=_COMPUTE)
    return _MODEL


# Domain-vocabulary priming (the CL12 Taglish/PH-language weak-spot fix, 2026-07-07).
# Whisper mangles asset IDs + acronyms on code-switched Taglish/Cebuano speech (measured: "PB-001"→
# "i-001", "MTBF"→"dili"). faster-whisper's `initial_prompt` seeds the decoder's first window so it
# biases toward these tokens — a ~zero-cost accuracy lift that keeps decoding indigenous (no cloud).
# Generic FORMAT + the standard maintenance acronyms (hive-specific codes vary; the LL-NNN shape +
# the terms are what transfer). Overridable via WH_ASR_PROMPT for a site with its own vocabulary.
_DEFAULT_ASR_PROMPT = (
    "WorkHive maintenance logbook. Equipment codes like PB-001, P-101, AC-001, CH-002, MTR-05. "
    "Terms: MTBF, MTTR, OEE, PM, RCM, FMEA, LOTO, PEC, NFPA, kW, RPM, vibration, bearing, seal, "
    "gasket, pump, motor, compressor, chiller, conveyor, valve, overhaul, preventive maintenance, "
    "corrective, breakdown, overdue."
)
_ASR_PROMPT = os.environ.get("WH_ASR_PROMPT", _DEFAULT_ASR_PROMPT)
# beam search (>1) sharpens PH-language + technical-term decoding vs greedy. beam=5 on medium+int8
# OOM'd (mkl_malloc) on a loaded host, so default to 2 (most of the gain, ~half the memory of 5);
# a roomier host can set WH_ASR_BEAM=5. The initial_prompt above is the bigger accuracy lever.
_ASR_BEAM = int(os.environ.get("WH_ASR_BEAM", "2"))

# Equipment-word -> asset-tag PREFIX map for the CL12 lost-prefix ASR recovery (§9.3 #1). When Whisper
# drops the prefix letters of a code (Taglish "PB-001" -> "0-0-1") AND the bare suffix collides across
# tags, the equipment WORD in the sentence disambiguates which prefix the worker meant. Common PH
# industrial prefixes + English AND Filipino/Taglish synonyms (bomba=pump, kompresor=compressor,
# boyler=boiler). Only prefixes actually present in the hive's vocab are ever used (see suffix_map).
_EQUIP_WORDS: dict[str, tuple[str, ...]] = {
    "PB":  ("pump", "bomba", "bomba ng", "pamp"),
    "AC":  ("compressor", "air compressor", "kompresor", "kompressor"),
    "CH":  ("chiller",),
    "CT":  ("cooling tower", "tower", "cooling"),
    "AHU": ("air handler", "air handling", "ahu"),
    "BLR": ("boiler", "boyler"),
    "BF":  ("boiler feed", "feed pump", "belt feeder"),
    "BE":  ("bucket elevator", "elevator", "elebeytor"),
    "FL":  ("filter", "salaan"),
    "TX":  ("transformer", "transpormer"),
    "FN":  ("fan", "blower", "bentilador"),
    "MTR": ("motor",),
    "GB":  ("gearbox", "gear box"),
    "CV":  ("conveyor", "conveyor belt", "kombeyor"),
    "VP":  ("vacuum pump", "vacuum"),
    "HX":  ("heat exchanger", "exchanger"),
}


def _repair_codes(text: str, vocab: list[str]) -> str:
    """Post-ASR deterministic repair of garbled asset codes against the hive's KNOWN tags
    (the CL12 Taglish fix — priming alone can't recover "AC-002"→"A C 002" or "PB-001"→"0-0-1").
    Real hives use PREFIX-NNN tags where MANY share a suffix (AC-001, PB-001, CH-001 …), so a
    suffix-only match is almost always ambiguous — the discriminating info is the PREFIX. Strategy:
      1. PRIMARY (prefix survives): full-tag match — the tag's prefix letters + digits, tolerant of
         dash/space/dot separator noise (case-insensitive). Unambiguous by construction (prefix+suffix
         identify the tag), so this fires for the common English/Cebuano case.
      2. FALLBACK (prefix fully lost, e.g. Taglish "0-0-1"): a BARE all-digit token (no surviving
         letters) is corrected ONLY when that digit-suffix maps to EXACTLY ONE tag — never guesses
         between collided suffixes. Bare-only so it can't clobber a correctly-prefixed different tag.
    No-op when vocab is empty."""
    if not vocab:
        return text
    tags = [t.strip() for t in vocab if t.strip()]
    # Full-tag (prefix + digits) match, longest tags first so "AHU-001" wins over a hypothetical "AH-001".
    # Prefix+digits identify the tag uniquely, so this never wrong-guesses between collided suffixes
    # (AC-001 vs PB-001). It fires when the PREFIX survives (the common English/Cebuano case) even through
    # separator/case noise ("A C 002"/"a.c.-002" → "AC-002"). A fully prefix-LOST token (Taglish "0-0-1",
    # prefix gone) is deliberately NOT repaired here — recovering it needs equipment-type context ("pump"→
    # PB), the documented next refinement; a bare-digit fallback was tried and REMOVED because it corrupted
    # already-correct codes ("AC-003"→"AC-AC-003": the "-" let the digit-run lookbehind match mid-tag).
    for tag in sorted(set(tags), key=len, reverse=True):
        m = re.match(r"^([A-Za-z]+)[-\s.]*(\d+)$", tag)
        if not m:
            continue
        pre, dig = m.group(1), m.group(2)
        prepat = r"[-\s.]*".join(re.escape(c) for c in pre)
        digpat = r"[-\s.]*".join(dig)
        pat = re.compile(r"\b" + prepat + r"[-\s.]*" + digpat + r"\b", re.IGNORECASE)
        text = pat.sub(tag, text)

    # 2. FALLBACK (prefix FULLY lost — Taglish "0-0-1", prefix gone): recover it from the EQUIPMENT WORD
    # near the digit token (§9.3 #1 "Later"). A bare digit-suffix that maps to EXACTLY ONE tag is filled
    # directly; an AMBIGUOUS suffix (AC-001 vs PB-001 vs CH-001 …) is disambiguated ONLY when a nearby
    # equipment word (incl. Tagalog: bomba=pump, kompresor=compressor) selects a prefix that is among the
    # collided candidates — never a blind guess. Corruption guard: skip any digit-run already preceded by a
    # letter+separator (i.e. inside an already-canonical tag like "PB-001"), so this can't do "AC-003"→"AC-AC-003".
    from collections import defaultdict
    suffix_map: dict[str, dict[str, str]] = defaultdict(dict)   # digits -> {PREFIX -> full_tag}
    for tag in set(tags):
        mm = re.match(r"^([A-Za-z]+)[-\s.]*(\d+)$", tag)
        if mm:
            suffix_map[mm.group(2)][mm.group(1).upper()] = tag
    src = text  # match offsets/windows resolve against the post-primary text

    def _repair_bare(match: "re.Match[str]") -> str:
        raw = match.start()
        before = src[max(0, raw - 4):raw]
        # Skip a digit-run glued to letters by a TAG separator (dash/dot: "PB-001", "AC.001") — that's an
        # already-canonical tag. A SPACE before the digits ("pump 001") is a word boundary, NOT a tag, so it
        # is eligible for equipment-word recovery — hence [-.] here, never \s.
        if re.search(r"[A-Za-z][-.]{0,2}$", before):
            return match.group(0)                              # part of a prefixed tag — never touch
        digits = re.sub(r"[^\d]", "", match.group(0))
        cands = suffix_map.get(digits)
        if not cands:
            return match.group(0)                              # suffix not in this hive's vocab
        if len(cands) == 1:
            return next(iter(cands.values()))                  # unambiguous — safe to fill
        window = src[max(0, raw - 40):raw].lower()             # ~40 chars before the token
        # Pick the equipment word CLOSEST to the digit token (highest position), so "pump 001 and
        # compressor 001" maps the 2nd 001 to the nearer 'compressor' (AC), not the earlier 'pump' (PB).
        best_pre, best_pos = None, -1
        for pre in cands:
            for w in _EQUIP_WORDS.get(pre, ()):
                pos = window.rfind(w)
                if pos > best_pos:
                    best_pos, best_pre = pos, pre
        if best_pre is not None:
            return cands[best_pre]                             # nearest equipment word selects the prefix
        return match.group(0)                                  # can't disambiguate — leave alone (no guess)

    text = re.sub(r"(?<![A-Za-z])\d(?:[-\s.]*\d){2,}", _repair_bare, text)
    return text


def transcribe(audio_bytes: bytes, language: str | None, vocab: list[str] | None = None) -> dict:
    """Decode + transcribe raw audio bytes. language=None → auto-detect. vocab = hive asset codes
    (primes the prompt + repairs garbled codes in the output — the CL12 indigenous Taglish fix)."""
    # faster-whisper decodes via PyAV/ffmpeg; a temp file is the most format-robust input
    # (webm/mp4/m4a from the browser MediaRecorder). Cleaned up in finally.
    suffix = ".audio"
    tmp = tempfile.NamedTemporaryFile(prefix="wh_asr_", suffix=suffix, delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.flush()
        tmp.close()
        # Prime with the default domain vocabulary + this hive's actual asset codes (if supplied).
        prompt = _ASR_PROMPT
        if vocab:
            prompt = _ASR_PROMPT + " Codes: " + ", ".join(v.strip() for v in vocab if v.strip()) + "."
        segments, info = _model().transcribe(
            tmp.name,
            language=language or None,   # None → auto-detect
            vad_filter=True,             # drop silence/noise gaps (factory floor is noisy)
            beam_size=_ASR_BEAM,         # beam search sharpens asset-ID/acronym decoding (CL12 fix)
            initial_prompt=prompt,       # domain + hive-code priming (CL12 fix)
        )
        seg_list = list(segments)                  # materialize so we can read per-segment confidence
        text = "".join(seg.text for seg in seg_list).strip()
        text = _repair_codes(text, vocab or [])   # deterministic garbled-code repair (CL12 fix)
        lang = (getattr(info, "language", "") or language or "").lower()
        # Transcription confidence (X-FIND 2026-07-12): faster-whisper exposes per-segment avg_logprob
        # (~ -0.1 confident … < -1.0 garbled) + no_speech_prob, and info.language_probability. The
        # voice family walk caught the companion CONFABULATING on a garbled Cebuano transcript (ASR
        # 40%) instead of asking to repeat — it had no confidence signal to gate on. Surface a mean
        # avg_logprob so the client can clarify below a floor rather than grounding a mis-heard question.
        # Additive: existing {text, lang} consumers are unaffected.
        logps = [s.avg_logprob for s in seg_list if getattr(s, "avg_logprob", None) is not None]
        avg_logprob = round(sum(logps) / len(logps), 3) if logps else None
        nsp = [s.no_speech_prob for s in seg_list if getattr(s, "no_speech_prob", None) is not None]
        no_speech_prob = round(max(nsp), 3) if nsp else None
        lang_prob = round(float(getattr(info, "language_probability", 0.0) or 0.0), 3)
        return {"text": text, "lang": lang, "avg_logprob": avg_logprob,
                "no_speech_prob": no_speech_prob, "lang_prob": lang_prob}
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence per-request stderr spam
        pass

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._send(200, {"ok": True, "model": _MODEL_NAME, "device": _DEVICE, "compute": _COMPUTE})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/transcribe":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send(400, {"error": "empty body (POST raw audio bytes)"})
            return
        if length > 25 * 1024 * 1024:   # 25MB cap (mirror the edge fn's own guard)
            self._send(413, {"error": "audio too large (>25MB)"})
            return
        audio = self.rfile.read(length)
        qs = parse_qs(parsed.query)
        lang = (qs.get("lang") or [None])[0]
        # optional ?vocab=PB-001,AC-001,... — the hive's known asset codes (prime + repair)
        vocab = [c for c in (qs.get("vocab") or [""])[0].split(",") if c.strip()]
        try:
            result = transcribe(audio, lang, vocab)
            self._send(200, result)
        except Exception as e:  # never 500 silently — return a shaped error so the edge falls back
            self._send(500, {"error": f"asr failed: {str(e)[:200]}"})


def main():
    port = DEFAULT_PORT
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a.isdigit():
            port = int(a)
        elif a == "--model" and i + 1 < len(argv):
            globals()["_MODEL_NAME"] = argv[i + 1]
        elif a == "--device" and i + 1 < len(argv):
            globals()["_DEVICE"] = argv[i + 1]
    print(f"asr_server: loading faster-whisper '{_MODEL_NAME}' on {_DEVICE} ({_COMPUTE}) ...", flush=True)
    try:
        _model()  # warm the model at boot so the first request isn't a cold 30s load
        print("asr_server: model ready.", flush=True)
    except Exception as e:
        print(f"asr_server: model load FAILED ({e}). Install: pip install faster-whisper + ffmpeg.", flush=True)
        # still serve /health so the edge sees it as down and falls back to Groq
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"asr_server: listening on :{port}  (POST /transcribe, GET /health)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
