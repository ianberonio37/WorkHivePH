"""
AI Eval Regression Validator (C3 Phase 1 of SELF_IMPROVING_GATE_ROADMAP.md).
=============================================================================
Promotes C2's `tools/ai_eval_gate.py gate` to a G0 validator, mirroring how
P1's ledger and P6's split shipped standalone first.

The gate is degrade-to-SKIP by design (see C2 spec in the roadmap §8 +
[[project_self_improving_gate]]):
  - no committed golden baseline yet  -> exit 0 with "run `baseline` first" msg
  - no fresh results to score          -> exit 0 with SKIP (the paid eval-runner
                                          cron / companion flywheel hasn't run)
  - results + baseline + clean run     -> exit 0
  - locked-test split regression       -> exit 1 (the AI-feature path is blocked)

This is the on-commit "pre-deploy" half of C3. The "clock + prod" half (running
the same policy continuously off `ai_quality_log` in production via Grafana/
Sentry) is C3 Phase 2 — separate, needs edge-fn deploy, and lives past the
deploy line.

Exit codes:
  0  no regression, or insufficient data (SKIP / "baseline first").
  1  locked-test split regressed beyond tolerance.
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "tools" / "ai_eval_gate.py"

CHECK_NAMES = ["ai_eval_regression"]

# P3 freshness anchors — wake this validator if the gate command name or its
# locked-test policy moves, so the validator can't quietly drift from the tool.
FRESHNESS_ANCHORS = [
    ("tools/ai_eval_gate.py", r"def gate\(",                        "Tool entrypoint renamed; rewire."),
    ("tools/ai_eval_gate.py", r"LOCKED-TEST REGRESSION",            "Locked-test FAIL banner moved; verify policy intent."),
    ("tools/ai_eval_gate.py", r"degrade-to-SKIP",                   "Degrade-to-SKIP guarantee moved; revisit exit codes."),
]


def main() -> int:
    if not TOOL.exists():
        print(f"\033[91mFAIL: {TOOL} missing — cannot run AI eval regression gate\033[0m")
        return 2
    proc = subprocess.run(
        [sys.executable, "-u", str(TOOL), "gate"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
