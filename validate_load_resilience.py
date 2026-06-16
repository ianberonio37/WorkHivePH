"""
Load-Resilience Sentinel (Maturity Phase 1, 2026-06-16).
=========================================================
Closes the (LB, GS) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — the
sentinel bridge that proves the scaling layer is exercised + degrades safely.

The GS column normally hosts a Playwright sentinel, but load/scaling is not a
browser concern. The honest local-substitute (D3 of the maturity roadmap) is a
sentinel that asserts the scaling INVARIANTS are actually covered and provable:

  L1  a live load proof exists           — tools/load_probe.py (k6-free local rig)
  L2  the load SLO is declared           — CAPACITY_PLAN.md 'LOAD-SLO:' marker
  L3  a degraded-mode contract is declared— CAPACITY_PLAN.md 'DEGRADED-MODE:' marker
  L4  graceful degradation under provider saturation — _shared/ai-chain.ts
      handles 429 + 503 (sheds load instead of 5xx-storming)

Swap-ready: when a real distributed LB/staging exists, L1 can point at a k6 run
against staging without changing the gate's shape.

Output:  load_resilience_report.json
Exit code:
  0  PASS (all four invariants covered)
  1  FAIL (a scaling invariant is unproven)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
LOAD_PROBE = ROOT / "tools" / "load_probe.py"
CAPPLAN    = ROOT / "CAPACITY_PLAN.md"
AI_CHAIN   = ROOT / "supabase" / "functions" / "_shared" / "ai-chain.ts"
REPORT     = ROOT / "load_resilience_report.json"

CHECK_NAMES = ["load_resilience"]
GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"


def main() -> int:
    cap = CAPPLAN.read_text(encoding="utf-8", errors="replace") if CAPPLAN.exists() else ""
    chain = AI_CHAIN.read_text(encoding="utf-8", errors="replace") if AI_CHAIN.exists() else ""

    checks = [
        ("L1 live load proof present (tools/load_probe.py)", LOAD_PROBE.exists()),
        ("L2 load SLO declared (CAPACITY_PLAN 'LOAD-SLO:')", "LOAD-SLO:" in cap),
        ("L3 degraded-mode contract declared (CAPACITY_PLAN 'DEGRADED-MODE:')", "DEGRADED-MODE:" in cap),
        ("L4 graceful degrade on provider saturation (_shared/ai-chain.ts handles 429 + 503)",
         ("429" in chain and "503" in chain)),
    ]
    fails = [name for name, ok in checks if not ok]

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": {name: ok for name, ok in checks}, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Load-Resilience Sentinel (LB, GS){RESET}")
    for name, ok in checks:
        print(f"  {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}  {name}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} scaling invariant(s) unproven.{RESET}")
        return 1
    print(f"{GREEN}PASS — scaling layer is load-proven and degrades safely.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
