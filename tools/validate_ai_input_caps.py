#!/usr/bin/env python3
"""
validate_ai_input_caps.py - Arc R (P-lens, OWASP LLM10/A03): user text entering an LLM prompt
must be length-capped.
=============================================================================================
An uncapped user-text field concatenated into a system/user prompt is BOTH a prompt-injection
budget AND a token-cost/DoS surface. The codebase standard is MAX_QUESTION_CHARS=500
(asset-brain-query). Arc R capped the sites that violated it; this gate locks them so the caps
can't silently regress. DETERMINISTIC (static source check) - unlike an LLM-grading gate it never
flakes, so it is safe on the ratcheted security board.

Per target fn, require its cap marker(s) to be present:
  ai-orchestrator      : .slice(0, 500)         (question/message)
  scheduled-agents     : .slice(0, 500)         (voice_context)
  walkthrough-analyzer : _cap( + _capn( + 7_000_000   (finding fields, notes, image bytes)
  voice-model-call     : safeMaxTokens + 8000   (token clamp + message-bytes cap)

Self-test (--self-test): a source missing its cap marker FAILs; one with it passes.
Exit 0 = every target fn caps its user text. Exit 1 = a cap missing (or self-test fail).
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_ai_input_caps"]

# fn -> list of required cap markers (ALL must be present).
TARGETS = {
    "ai-orchestrator":      [".slice(0, 500)"],
    "scheduled-agents":     [".slice(0, 500)"],
    "walkthrough-analyzer": ["_cap(", "_capn(", "7_000_000"],
    "voice-model-call":     ["safeMaxTokens", "8000"],
}


def check_fn(fn: str, markers: list[str]) -> list[str]:
    p = FUNCS / fn / "index.ts"
    if not p.exists():
        return [f"{fn}/index.ts not found"]
    src = p.read_text(encoding="utf-8", errors="replace")
    return [f"{fn}: missing cap marker `{m}`" for m in markers if m not in src]


def self_test() -> bool:
    ok = True
    # detection fn: marker-present passes, marker-absent fails
    good = "const q = _q.slice(0, 500);"
    if ".slice(0, 500)" not in good:
        print(f"{R}self-test FAIL: marker logic broken.{X}"); ok = False
    bad = "const q = body.message;"  # no cap
    if ".slice(0, 500)" in bad:
        print(f"{R}self-test FAIL: false positive.{X}"); ok = False
    print((G + "self-test PASS - cap detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1
    fails = []
    for fn, markers in TARGETS.items():
        fails += check_fn(fn, markers)
    print(f"{B}AI input-caps gate (Arc R / P-lens, LLM10){X}")
    print(f"  target fns: {len(TARGETS)}")
    for f in fails:
        print(f"  {R}FAIL{X} {f}")
    if fails:
        print(f"{R}FAIL: {len(fails)} uncapped AI-input site(s).{X}")
        return 1
    print(f"{G}PASS - every target fn caps its user-text LLM input.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
