"""
AI Asset Versioning Validator (C5 of SELF_IMPROVING_GATE_ROADMAP.md).
======================================================================
Treats AI assets (golden eval fixtures, prompts, model chain, judge
prompt, eval baseline) the way `validate_migration_immutability_strict`
treats SQL migrations: hash + record + FAIL on edits without version
bumps. Prevents silent rollover of the artifacts C2's eval gate scores
against.

Delegates to `tools/ai_asset_baseline.py verify` so the policy lives in
ONE place. Run that tool directly for `build` (idempotent seed) or
`report` (human inspect).

Exit codes:
  0  every manifest asset matches its recorded version+hash, or was
     legitimately bumped (version moved AND hash moved together).
  1  one or more assets violated policy (silent change, no-op bump,
     downgrade, missing required file, or unparseable version).
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "tools" / "ai_asset_baseline.py"

CHECK_NAMES = ["ai_asset_versioning"]

# P3 freshness anchors — wake this validator the day either the tool or
# the manifest field name moves, so the gate can't quietly skip C5.
FRESHNESS_ANCHORS = [
    ("tools/ai_asset_baseline.py", r"def cmd_verify",                     "Tool entrypoint moved; rewire."),
    ("tools/ai_asset_baseline.py", r"ai_asset_version",                   "Manifest version-field name moved."),
]


def main() -> int:
    if not TOOL.exists():
        print(f"\033[91mFAIL: {TOOL} missing — cannot run AI-asset versioning check\033[0m")
        return 2
    proc = subprocess.run(
        [sys.executable, "-u", str(TOOL), "verify"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
