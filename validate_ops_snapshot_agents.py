#!/usr/bin/env python3
"""
validate_ops_snapshot_agents.py
Grounding guard: every USER-FACING conversational agent that can be asked a factual
"how many / which / what's my" ops question MUST be in ai-gateway's OPS_SNAPSHOT_AGENTS
set, so it receives the LIVE OPERATIONS SNAPSHOT (v_alert_truth active-alert count,
overdue-PM count, real asset tags) and grounds its answer instead of confabulating.

Root cause this freezes (2026-07-11, FB1): the flagship AI Work Assistant (agent
'assistant' -> ai-orchestrator) was EXCLUDED while only the companion ('voice-journal')
was included, so the assistant answered "9" to "how many open alerts?" when the truth
was 59 (the companion, grounded, said 59). Fixed by adding 'assistant'. This gate FAILs
if either required agent is dropped from the set.
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
GATEWAY = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"
# Every user-facing conversational surface that answers factual ops questions.
REQUIRED_AGENTS = {"voice-journal", "assistant"}


def main() -> int:
    print("\nOps-Snapshot Agent Coverage Gate")
    print("=" * 50)
    if not GATEWAY.exists():
        print(f"  ERROR: {GATEWAY} not found")
        return 1
    src = GATEWAY.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"OPS_SNAPSHOT_AGENTS\s*:\s*Set<string>\s*=\s*new\s+Set\(\s*\[([^\]]*)\]", src)
    if not m:
        print("  FAIL: could not locate the OPS_SNAPSHOT_AGENTS Set definition")
        return 1
    present = set(re.findall(r'"([^"]+)"', m.group(1)))
    missing = REQUIRED_AGENTS - present
    for a in sorted(REQUIRED_AGENTS):
        print(f"  {'PASS' if a in present else 'FAIL'}  agent '{a}' in OPS_SNAPSHOT_AGENTS")
    if missing:
        print(f"\n  FAIL: {sorted(missing)} missing from OPS_SNAPSHOT_AGENTS — that surface will "
              f"confabulate factual ops counts (e.g. answered '9' alerts when v_alert_truth = 59).")
        return 1
    print(f"\n  All {len(REQUIRED_AGENTS)} factual-answer agents are grounded (get the live ops snapshot).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
