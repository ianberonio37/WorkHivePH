#!/usr/bin/env python3
# DEEPWALK-CELL: ai-gateway D26
"""validate_assistant_recall.py — lock the CL5 fix: the orchestrator's 0-agents deflection is MEMORY-AWARE.

Found live 2026-07-08: the Work Assistant (agent=assistant → ai-orchestrator) had NO multi-turn recall —
a "what did I just tell you?" question made the router pick a specialist that returned no HIVE data, so
`orchestrate()` returned its hardcoded "couldn't find enough data" fallback BEFORE the memory-grounded
synthesis (the only place the gateway-forwarded `memoryBlock` is used). The voice-journal companion
recalled fine (decisive fork). Fix: deflect only when `!successfulResults.length` AND no memory; a
`RECALL_RE`-shaped question WITH conversation memory falls through to the memory-grounded synthesis.

This gate asserts the fix stays in place (static; a naive revert to an unconditional early-return deflect
would FAIL it):
  1. `RECALL_RE` is defined in ai-orchestrator.
  2. The "couldn't find enough data" deflection is NOT an unconditional early return under
     `if (!successfulResults.length)` — it must be guarded by a memory + RECALL_RE check.

Usage:  python tools/validate_assistant_recall.py [--json]
Exit 0 = fix intact · 1 = the memory-aware guard is missing (recall regressed).
"""
import re
import sys
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORCH = ROOT / "supabase" / "functions" / "ai-orchestrator" / "index.ts"
DEFLECT = "couldn't find enough data"


def analyze():
    viols = []
    if not ORCH.exists():
        return [{"issue": f"missing {ORCH.relative_to(ROOT)}"}]
    src = ORCH.read_text(encoding="utf-8", errors="ignore")

    if "RECALL_RE" not in src:
        viols.append({"issue": "RECALL_RE (recall-question detector) is gone — the memory-aware recall guard was removed"})

    # Locate the deflection return and confirm a memory guard sits between the 0-agents check and it.
    m = re.search(r"if\s*\(\s*!successfulResults\.length\s*\)\s*\{(.*?)\}", src, re.S)
    if not m:
        viols.append({"issue": "could not find the `if (!successfulResults.length)` block — orchestrator refactored; re-verify recall by hand"})
        return viols
    block = m.group(1)
    if DEFLECT not in block:
        # deflection moved elsewhere; not necessarily broken, but the gate can't verify → warn as a viol
        viols.append({"issue": f"the 0-agents block no longer contains the '{DEFLECT}' deflection — re-point this gate"})
        return viols
    # The deflection must be GUARDED (memoryBlock + RECALL_RE), not an unconditional return.
    guarded = ("memoryBlock" in block and "RECALL_RE" in block)
    if not guarded:
        viols.append({"issue": "the 0-agents deflection is UNCONDITIONAL again (no memoryBlock/RECALL_RE guard) — multi-turn recall will regress: a recall question deflects 'not enough data'"})
    return viols


def main():
    as_json = "--json" in sys.argv
    viols = analyze()
    if as_json:
        print(json.dumps({"violations": viols, "count": len(viols)}, indent=2))
    else:
        print("assistant multi-turn recall (CL5 — orchestrator 0-agents deflection must be memory-aware)")
        if not viols:
            print("  PASS: RECALL_RE present + the 'not enough data' deflection is guarded by memoryBlock/RECALL_RE")
        else:
            print(f"  FAIL: {len(viols)} issue(s):")
            for v in viols:
                print(f"    - {v['issue']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
