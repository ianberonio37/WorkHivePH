"""
Meta-Gate Recorder Validator (C4 Phase 2c of SELF_IMPROVING_GATE_ROADMAP.md).
=============================================================================
Promotes C4 Phase 2b's `tools/meta_gate.py decide` to a per-gate-run
recorder, mirroring P1's "observation first, driver later" pattern.

WHY OBSERVATION-ONLY AT G0:

The existing 354-validator gate already blocks on any FAIL. The meta-gate's
composition policy is strictly more PERMISSIVE than the monolithic gate
(it converts some FAILs to warn-only via blast-radius + seam-sharpening,
never ADDS blocks). Promoting the meta-gate as a hard-blocking validator
at G0 would therefore be a no-op for ship/block — it can never trip
where the existing gate hasn't already tripped.

What G0 promotion DOES add: every gate run now writes a per-domain
decision line to `meta_gate_decisions.jsonl` with the composition
reasoning + touched seams + blast radius. The P2 promotion engine's
macro-loop can later mine that history for "seams that block most
often", "PRs where seam-sharpening saved a block", and similar
patterns — exactly the input P1's efficacy ledger gives the same
macro-loop for individual validators.

This validator therefore ALWAYS exits 0 in observation mode (clamping
the underlying tool's exit 1 → 0). A future Phase 2d could flip the
semantics so meta-gate verdicts override the monolithic gate — but that
is a deliberate architectural choice, not a side effect of promotion.

Degrade-to-SKIP semantics (mirrors C3 Phase 1):
  - no ledger / no catalog / git diff fails -> exit 0 with SKIP message.
  - normal run -> exit 0 + decision appended to meta_gate_decisions.jsonl.

Exit codes:
  0  always (observation-only at G0 today).
  2  the underlying tool errored (real diagnostic, not a policy block).
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "tools" / "meta_gate.py"

CHECK_NAMES = ["meta_gate"]

# P3 freshness anchors — wake this validator if the tool's CLI moves.
FRESHNESS_ANCHORS = [
    ("tools/meta_gate.py", r"def cmd_decide",         "Tool entrypoint moved; rewire."),
    ("tools/meta_gate.py", r"--write-decision",       "Decision-recording flag moved; the macro-loop input dries up."),
    ("tools/meta_gate.py", r"seam-sharpening",        "Seam-sharpening rule moved; revisit P2c semantics."),
]


def main() -> int:
    if not TOOL.exists():
        print(f"\033[91mFAIL: {TOOL} missing — cannot record meta-gate decision\033[0m")
        return 2
    proc = subprocess.run(
        [sys.executable, "-u", str(TOOL), "decide", "--write-decision"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    # Forward the meta-gate's stdout (its readable summary belongs in the
    # gate log so a human reviewing platform_health can see WHY the meta-
    # gate would have shipped/blocked, even though we don't act on it).
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    if proc.returncode == 2:
        # Insufficient input (no ledger / catalog) — degrade to SKIP.
        print("\033[96mSKIP\033[0m  meta-gate: insufficient inputs (see message above).")
        return 0
    # Observation mode — clamp the meta-gate's exit 1 to 0 so this
    # validator never adds a new ship/block over the monolithic gate.
    # The composition reasoning lives in meta_gate_decisions.jsonl for
    # the macro-loop to consume.
    if proc.returncode == 1:
        print("\033[93mNOTE\033[0m  meta-gate would BLOCK on this diff "
              "(observation-only at G0; existing gate already enforces).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
