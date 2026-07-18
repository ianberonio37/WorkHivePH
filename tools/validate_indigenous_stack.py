#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D28
r"""
validate_indigenous_stack.py — SOVEREIGNTY ratchet (NATIVE_AI_ROADMAP.md #6, V-axis V6).

Every AI capability that touches a hot path MUST keep BOTH:
  (a) a LOCAL-FIRST path behind an env-gated URL (so a plant can run inference on its own infra and
      its data never leaves the plant), AND
  (b) a FALLBACK (so no single external provider — or a local-server outage — can take the feature down).

This asserts that invariant across all four stack members, so no future edit can silently re-introduce
a hard external dependency (which would break data-sovereignty for compliance-locked accounts):
  Embeddings : _shared/embedding-chain.ts  — BGE_EMBED_URL (local bge) + provider fallback chain
  ASR (audio): _shared/audio-chain.ts       — WH_ASR_URL (local faster-whisper) + Groq fallback
  TTS (voice): wh-tts.js                     — WH_TTS_URL (local Piper) + browser speechSynthesis fallback
  LLM        : _shared/ai-chain.ts           — WH_LLM_URL (local Ollama/llama.cpp) + the free-tier PROVIDER_CHAIN

Deterministic ($0, no deno/DB/model). Exit 0 = PASS, 1 = FAIL. No file is ever edited.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

# (capability, file, local-first-slot regex, fallback-evidence regex)
STACK = [
    ("Embeddings (bge)", ROOT / "supabase" / "functions" / "_shared" / "embedding-chain.ts",
     r"BGE_EMBED_URL", r"PROVIDER_CHAIN|voyage|jina|gemini|fallback"),
    ("ASR (whisper)", ROOT / "supabase" / "functions" / "_shared" / "audio-chain.ts",
     r"WH_ASR_URL", r"transcribeLocal|Groq|groq|WHISPER_CHAIN|falling back"),
    ("TTS (voice)", ROOT / "wh-tts.js",
     r"WH_TTS_URL", r"speakBrowser|speechSynthesis"),
    ("LLM", ROOT / "supabase" / "functions" / "_shared" / "ai-chain.ts",
     r"WH_LLM_URL", r"PROVIDER_CHAIN|attemptChain"),
]


def main() -> int:
    fails: list[str] = []
    passes: list[str] = []
    for cap, path, local_re, fb_re in STACK:
        if not path.exists():
            fails.append(f"{cap}: MISSING FILE {path.name}")
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        has_local = re.search(local_re, src) is not None
        has_fb = re.search(fb_re, src) is not None
        if not has_local:
            fails.append(f"{cap}: {path.name} lost its LOCAL-FIRST slot (`{local_re}`) — the capability "
                         f"can no longer run in-plant, breaking data sovereignty")
        if not has_fb:
            fails.append(f"{cap}: {path.name} lost its FALLBACK (`{fb_re}`) — a local-server outage would "
                         f"now dead-end the worker (fail-open hedge removed)")
        if has_local and has_fb:
            passes.append(f"{cap}: local-first ({local_re}) + fallback both intact")

    for p in passes:
        print(f"{GRN}PASS{RST} {p}")
    for f in fails:
        print(f"{RED}FAIL{RST} {f}")
    if fails:
        print(f"\n{RED}validate_indigenous_stack: {len(fails)} sovereignty regression(s){RST}")
        return 1
    print(f"\n{GRN}validate_indigenous_stack: all 4 AI capabilities keep local-first + fallback "
          f"(sovereign-ready, no hard external dependency){RST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
