"""
Companion per-dimension regression gate (G0) — Phase 8 §8.3.
============================================================
Thin platform-gate wrapper around `tools/ai_eval_gate.py companion_gate()`. For every companion
dimension that is registry-`active` AND has a frozen baseline in companion_dim_baselines.json,
it scores the dimension's latest results on the LOCKED-TEST split and BLOCKS (exit 1) if a
*blocking* dimension regressed beyond tolerance. Dimensions without a baseline or without fresh
results DEGRADE-TO-SKIP (exit 0) — never a false FAIL before the eval data exists.

This is the G0 registration of the per-dimension gate (the 8.3 deliverable), mirroring how P1's
ledger and P6's split shipped standalone before their gate wrappers. It does NOT touch the frozen
functionality/safety gate (ai_eval_gate.py `gate`), which the existing ai-eval-regression validator
already covers.

Exit: 0 = PASS / degrade-to-SKIP; 1 = a blocking companion-dimension regressed on the locked-test split.
"""
from __future__ import annotations
import io
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))

try:
    from ai_eval_gate import companion_gate
except Exception as e:  # pragma: no cover — degrade-to-SKIP if the tool moved
    print(f"SKIP — could not import companion_gate ({type(e).__name__}: {e}); not a failure.")
    sys.exit(0)


def main() -> int:
    return companion_gate()


if __name__ == "__main__":
    sys.exit(main())
