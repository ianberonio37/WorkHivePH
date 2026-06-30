#!/usr/bin/env python3
"""validate_ai_alldown_degrade.py - Arc S (Resilience/DR) F-lens cell `ai_alldown_degrade`.
================================================================================
When ALL AI providers are down, _shared/ai-chain.ts degrades to the bare string
"{}". A caller that does `JSON.parse(callAI(...))` then trusts the result will
silently render/store an EMPTY object (no error shown) because JSON.parse("{}")
succeeds. Any narrative caller must DETECT the empty/all-down case and fall back to
a meaningful message instead of a blank section.

This gate asserts:
  1. ai-chain.ts still has the documented all-down degrade return ("{}") — the contract.
  2. the narrative callers that JSON.parse the result GUARD the empty/"{}" case
     (an explicit `=== "{}"` / empty check, OR a required-field check before use).
     intelligence-report was the confirmed unguarded caller (F-005).

Exit 0 = all-down degrades visibly; 1 = a caller would render empty silently. Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FUNCS = ROOT / "supabase" / "functions"
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"

# narrative callers that JSON.parse a callAI result and must guard the empty case
GUARDED_CALLERS = ["intelligence-report"]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    print(f"{B}Arc S - AI all-down degrade (F-lens, no silent empty){X}")
    print("=" * 60)
    issues = []

    chain = _read(FUNCS / "_shared" / "ai-chain.ts")
    chain_ok = '"{}"' in chain or "'{}'" in chain
    print(f"  {(G+'PASS'+X) if chain_ok else (R+'FAIL'+X)}  ai-chain.ts has the documented all-down degrade return")
    if not chain_ok:
        issues.append("ai-chain all-down return not found")

    for caller in GUARDED_CALLERS:
        t = _read(FUNCS / caller / "index.ts")
        if not t:
            continue
        # a guard: explicit empty/"{}" detection OR a required-field presence check
        guarded = bool(re.search(r"===\s*[\"']\{\}[\"']", t)) or \
                  bool(re.search(r"raw\.trim\(\)\s*===\s*[\"']\{\}[\"']", t)) or \
                  bool(re.search(r"if\s*\(\s*!?\s*\w*\.?(executive_summary|parsed)\b", t)) or \
                  ("ai_unavailable" in t or "ai_empty" in t)
        print(f"  {(G+'PASS'+X) if guarded else (R+'FAIL'+X)}  {caller} guards the empty/all-down AI result")
        if not guarded:
            issues.append(f"{caller} does not guard empty AI result")

    if issues:
        print(f"\n{R}{B}  AI-ALLDOWN-DEGRADE: FAIL{X} - {'; '.join(issues)}")
        return 1
    print(f"\n{G}{B}  AI-ALLDOWN-DEGRADE: PASS{X} - all-providers-down degrades to a visible message, not blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
