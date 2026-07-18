#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D27
r"""
validate_asr_confidence_gate.py — regression guard for the ASR-confidence clarify-gate
(X-FIND, live-caught 2026-07-12): a mis-heard (garbled) voice question must NOT be sent
to the companion, which then CONFABULATES a grounded answer on the garble (caught live:
a 40%-fidelity Cebuano transcript "ASCL sa POM" got grounded to real asset TT-001).

The fix is a 4-layer additive chain — this gate asserts every link is intact so the
confidence signal can never silently stop flowing (which would reopen the confabulation):
  1. tools/asr_server.py            — /transcribe returns `avg_logprob` (mean per-segment confidence)
  2. _shared/audio-chain.ts         — TranscribeResult carries `avg_logprob`; transcribeLocal passes it
  3. voice-transcribe/index.ts      — computes `low_confidence` from avg_logprob + returns it
  4. voice-journal.html             — reads the flag (`low_confidence`/`lowConfidence`) and gates
                                       (does NOT auto-send to the companion when low-confidence)

Deterministic ($0, no deno/DB/model). Exit 0 = PASS, 1 = FAIL. No file is edited.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRN, RED, RST = "\033[92m", "\033[91m", "\033[0m"

LINKS = [
    ("asr_server.py returns avg_logprob",
     ROOT / "tools" / "asr_server.py",
     [r'"avg_logprob"\s*:', r'avg_logprob']),
    ("audio-chain.ts TranscribeResult carries avg_logprob + local passes it",
     ROOT / "supabase" / "functions" / "_shared" / "audio-chain.ts",
     [r'avg_logprob\??\s*:', r'avg_logprob:\s*typeof data\.avg_logprob']),
    ("voice-transcribe computes + returns low_confidence",
     ROOT / "supabase" / "functions" / "voice-transcribe" / "index.ts",
     [r'low_confidence', r'LOW_CONF_FLOOR', r'low_confidence\s*[,}]']),
    ("voice-journal.html reads the flag AND gates (no auto-send on low-confidence)",
     ROOT / "voice-journal.html",
     [r'low_confidence|lowConfidence', r'lowConfidence']),
]


def main() -> int:
    fails: list[str] = []
    passes: list[str] = []
    for name, path, needles in LINKS:
        if not path.exists():
            fails.append(f"{name}: MISSING FILE {path.name}")
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        missing = [n for n in needles if not re.search(n, src)]
        if missing:
            fails.append(f"{name}: {path.name} no longer matches {missing} — the confidence signal "
                         f"may have stopped flowing (the companion would confabulate on garbled ASR again)")
        else:
            passes.append(name)

    # Extra teeth: voice-journal must GATE (return/skip), not merely read the flag.
    vj = (ROOT / "voice-journal.html")
    if vj.exists():
        s = vj.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"lowConfidence\b", s)
        if m:
            window = s[m.start(): m.start() + 400]
            if "return" not in window:
                fails.append("voice-journal.html reads lowConfidence but does not early-return/gate on it "
                             "within the handler — the clarify-gate is defanged (it would still auto-send)")
            else:
                passes.append("voice-journal.html early-returns (gates) on lowConfidence")

    for p in passes:
        print(f"{GRN}PASS{RST} {p}")
    for f in fails:
        print(f"{RED}FAIL{RST} {f}")
    if fails:
        print(f"\n{RED}validate_asr_confidence_gate: {len(fails)} broken link(s) in the clarify-gate chain{RST}")
        return 1
    print(f"\n{GRN}validate_asr_confidence_gate: ASR-confidence clarify-gate chain intact ({len(passes)} links){RST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
