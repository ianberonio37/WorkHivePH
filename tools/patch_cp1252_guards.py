"""
Patch missing cp1252 stdout guards into validator scripts.

The validator pattern miner (tools/mine_validator_patterns.py) found 33
validate_*.py files missing the Windows-cp1252 stdout guard. Without it,
the validator crashes on Windows when its stdout receives a Unicode
character (em-dash, emoji, arrow, etc.) that cp1252 cannot encode --
see [[feedback-console-encoding]] in memory.

This script:
  1. Reads the outlier list from validator_pattern_mining_report.json
  2. For each file, finds the `import sys` line
  3. Inserts the canonical 3-line guard right after it
  4. Is IDEMPOTENT -- re-running it on patched files is a no-op
  5. Skips files where `import sys` cannot be located (manual review needed)

The guard inserted matches the canonical short form used by validate_em_dash.py:

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

Run after every validator-miner pass that surfaces new missing-guard
findings (e.g., a brand-new validator was added without the guard).
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "validator_pattern_mining_report.json"

GUARD_BLOCK = """if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""

# Regex used by the miner to detect the guard. Keep this in sync with
# mine_validator_patterns.py so the patcher and the detector agree on
# what counts as "patched."
GUARD_DETECT_RE = re.compile(r"sys\.stdout\s*=\s*io\.TextIOWrapper")

# Match the line where `sys` is imported. Handles all common forms:
#   import sys
#   import sys, json
#   import json, sys
#   import urllib.request, json, time, sys   (dotted modules in the list)
# We insert AFTER the matched line. First run on 33 outliers (2026-05-18)
# missed 2 files because the character class didn't allow `.` -- fixed by
# adding it so dotted import lists match.
SYS_IMPORT_RE = re.compile(
    r"^(import\s+(?:[\w., ]+,\s*)?sys(?:\s*,\s*[\w., ]+)?\s*)$",
    re.MULTILINE,
)


def patch_file(path: Path) -> str:
    """Return one of: 'patched', 'already_present', 'no_sys_import',
    'multiple_sys_imports' (manual review needed)."""
    text = path.read_text(encoding="utf-8", errors="replace")

    if GUARD_DETECT_RE.search(text):
        return "already_present"

    matches = list(SYS_IMPORT_RE.finditer(text))
    if not matches:
        return "no_sys_import"
    if len(matches) > 1:
        # Multiple `import sys` lines is unusual -- pick the FIRST one,
        # which is conventionally the canonical top-of-file import.
        # But log the case so the operator can review.
        pass

    m = matches[0]
    insert_at = m.end()

    # Ensure exactly one blank line between `import sys` and the guard.
    suffix = text[insert_at:]
    # Skip past any trailing whitespace on the import line itself.
    while suffix.startswith(" ") or suffix.startswith("\t"):
        insert_at += 1
        suffix = text[insert_at:]

    new_text = text[:insert_at] + "\n" + GUARD_BLOCK + text[insert_at:]
    path.write_text(new_text, encoding="utf-8")
    return "patched" if len(matches) == 1 else "patched_multiple_sys_imports"


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"ERROR: {REPORT_PATH.name} not found. Run mine_validator_patterns.py first.")
        return 1

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    outliers = report["conformance"]["has_cp1252_stdout_guard"]["outliers"]
    print(f"cp1252 stdout-guard patcher")
    print(f"  targets:           {len(outliers)} validator(s)")
    print()

    results = {"patched": [], "already_present": [], "no_sys_import": [],
               "patched_multiple_sys_imports": []}
    for name in outliers:
        path = ROOT / name
        if not path.exists():
            print(f"  SKIP  {name}  (file not found)")
            continue
        outcome = patch_file(path)
        results.setdefault(outcome, []).append(name)
        tag = {"patched": "OK  ", "already_present": "NOOP",
               "no_sys_import": "WARN", "patched_multiple_sys_imports": "OK*"}[outcome]
        print(f"  {tag}  {name}")

    print()
    print(f"Summary:")
    print(f"  patched (clean):                  {len(results['patched'])}")
    print(f"  patched (multiple `import sys`):  {len(results['patched_multiple_sys_imports'])}")
    print(f"  already_present (no-op):          {len(results['already_present'])}")
    print(f"  no_sys_import (manual review):    {len(results['no_sys_import'])}")

    if results["no_sys_import"]:
        print()
        print("Files needing manual review (no `import sys` line found):")
        for name in results["no_sys_import"]:
            print(f"  - {name}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
