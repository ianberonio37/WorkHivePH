"""
tools/apply_proposal.py -- WorkHive Proposal Applicator
========================================================
Reads open findings from findings.json that have _validator_decision
with generated code, applies the code to the target file, registers
new validators/tests in the appropriate runner, marks the finding as
gated, then re-runs L13 to confirm the loop is closed.

This is the application mechanism that closes the gap between
"finding + proposal generated" and "gate locked."

Finding actions handled:
  journey_test      -- append new test scenario to tests/journey-X.spec.ts
  improve_existing  -- append new layer/section to validate_X.py
  add_new           -- create new validate_X.py + register in
                       run_platform_checks.py (requires --allow-new)
  accept            -- mark finding acknowledged, no code change

Usage:
  python tools/apply_proposal.py              # dry-run: show what would apply
  python tools/apply_proposal.py --apply      # apply all safe proposals
  python tools/apply_proposal.py --apply --allow-new  # also create new validators
  python tools/apply_proposal.py --finding <id> --apply  # apply one specific finding
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT          = Path(__file__).parent.parent
FINDINGS_FILE = ROOT / "findings.json"
VALIDATORS    = ROOT / "run_platform_checks.py"
TESTS_DIR     = ROOT / "tests"

DRY_RUN    = "--apply" not in sys.argv
ALLOW_NEW  = "--allow-new" in sys.argv
ONLY_ID    = None
for i, arg in enumerate(sys.argv):
    if arg == "--finding" and i + 1 < len(sys.argv):
        ONLY_ID = sys.argv[i + 1]

SEVERITY_GATE = {"critical", "high", "medium"}


# ── Helpers -------------------------------------------------------------------

def load_findings():
    if not FINDINGS_FILE.exists():
        return []
    with open(FINDINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("findings", []), data


def save_findings(data):
    with open(FINDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def banner(msg):
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print("=" * 60)


def ok(msg):  print(f"  [OK]   {msg}")
def skip(msg): print(f"  [SKIP] {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def err(msg):  print(f"  [ERR]  {msg}")


# ── Apply functions -----------------------------------------------------------

def apply_journey_test(finding: dict, vd: dict) -> bool:
    """Append a new test scenario to an existing journey spec file."""
    target = ROOT / vd.get("target_file", "")
    code   = vd.get("code", "").strip()

    if not target.exists():
        warn(f"Target spec not found: {target}")
        return False
    if not code:
        warn(f"No code in _validator_decision for finding {finding['id']}")
        return False

    if DRY_RUN:
        print(f"\n  Would append to {target.name}:")
        for line in code.splitlines()[:8]:
            print(f"    {line}")
        if len(code.splitlines()) > 8:
            print(f"    ... ({len(code.splitlines())} total lines)")
        return True

    # Append before the last closing `});` of the describe block
    content = target.read_text(encoding="utf-8")
    # Find the last `});` and insert before it
    last_close = content.rfind("\n});")
    if last_close == -1:
        # Fallback: just append at end
        content = content + "\n\n" + code + "\n"
    else:
        content = content[:last_close] + "\n\n" + code + "\n" + content[last_close:]

    target.write_text(content, encoding="utf-8")
    ok(f"Appended test scenario to {target.name}")
    return True


def apply_improve_existing(finding: dict, vd: dict) -> bool:
    """Append a new layer/section to an existing validator file."""
    target = ROOT / vd.get("target_file", "")
    code   = vd.get("code", "").strip()

    if not target.exists():
        warn(f"Validator file not found: {target}")
        return False
    if not code:
        warn(f"No code for finding {finding['id']}")
        return False

    if DRY_RUN:
        print(f"\n  Would append to {target.name}:")
        for line in code.splitlines()[:8]:
            print(f"    {line}")
        return True

    content = target.read_text(encoding="utf-8")
    # Append before `if __name__ == "__main__":` or at end
    main_match = re.search(r'\nif __name__\s*==\s*["\']__main__["\']', content)
    if main_match:
        content = content[:main_match.start()] + "\n\n" + code + "\n" + content[main_match.start():]
    else:
        content = content + "\n\n" + code + "\n"

    target.write_text(content, encoding="utf-8")
    ok(f"Appended to {target.name}")
    return True


def apply_add_new_validator(finding: dict, vd: dict) -> bool:
    """Create a new validator file and register it in run_platform_checks.py."""
    if not ALLOW_NEW:
        skip(f"add_new requires --allow-new flag: {vd.get('target_file')}")
        return False

    target = ROOT / vd.get("target_file", "")
    code   = vd.get("code", "").strip()

    if not code:
        warn(f"No code for new validator {finding['id']}")
        return False
    if target.exists():
        warn(f"File already exists: {target} — use improve_existing instead")
        return False

    if DRY_RUN:
        print(f"\n  Would create {target.name}:")
        for line in code.splitlines()[:6]:
            print(f"    {line}")
        print(f"  Would register in run_platform_checks.py")
        return True

    target.write_text(code, encoding="utf-8")
    ok(f"Created {target.name}")

    # Register in run_platform_checks.py
    _register_validator_in_gate(target.name, vd.get("target_layer", "New validator"))
    return True


def _register_validator_in_gate(script_name: str, label: str):
    """Add a new validator entry to run_platform_checks.py VALIDATORS list."""
    content = VALIDATORS.read_text(encoding="utf-8")
    entry_id = script_name.replace("validate_", "").replace(".py", "").replace("_", "-")

    new_entry = f'''    {{
        "id":           "{entry_id}",
        "script":       "{script_name}",
        "args":         [],
        "label":        "{label}",
        "group":        "Platform",
        "report":       None,
        "skip_if_fast": False,
    }},'''

    # Insert before the closing `]` of the VALIDATORS list
    close_idx = content.rfind("\n]")
    if close_idx == -1:
        warn(f"Could not find closing ] in run_platform_checks.py — register manually")
        return
    content = content[:close_idx] + "\n" + new_entry + content[close_idx:]
    VALIDATORS.write_text(content, encoding="utf-8")
    ok(f"Registered {script_name} in run_platform_checks.py")


# ── Mark finding as gated ----------------------------------------------------

def mark_gated(finding: dict, data: dict, action: str):
    fid = finding["id"]
    for f in data["findings"]:
        if f["id"] == fid:
            if action in ("journey_test",):
                f["has_test"]    = True
                f["test_file"]   = finding.get("_validator_decision", {}).get("target_file")
            else:
                f["has_validator"]   = True
                f["validator_layer"] = finding.get("_validator_decision", {}).get("target_layer", "")
            f["status"]     = "resolved" if action != "accept" else "acknowledged"
            f["fix_commit"] = "apply_proposal"
            break


# ── Run L13 after applying ----------------------------------------------------

def run_l13() -> bool:
    result = subprocess.run(
        [sys.executable, "validate_playwright_staleness.py"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=str(ROOT),
    )
    passed = result.returncode == 0
    for line in (result.stdout + result.stderr).splitlines():
        if any(k in line for k in ["PASS", "FAIL", "WARN", "All ", "open:"]):
            print(f"  L13: {line.strip()}")
    return passed


# ── Main ---------------------------------------------------------------------

def main():
    banner("Proposal Applicator" + (" [DRY-RUN]" if DRY_RUN else " [APPLYING]"))

    findings_list, data = load_findings()

    # Filter to actionable open findings
    candidates = [
        f for f in findings_list
        if f.get("status") == "open"
        and f.get("severity") in SEVERITY_GATE
        and not f.get("has_test")
        and not f.get("has_validator")
        and f.get("_validator_decision")
        and (ONLY_ID is None or f["id"] == ONLY_ID)
    ]

    if not candidates:
        print("\n  No open ungated findings with proposals. Loop is closed.")
        if not DRY_RUN:
            print("\n  Running L13 to confirm...")
            run_l13()
        return

    print(f"\n  Found {len(candidates)} finding(s) with proposals:")
    applied = 0

    for f in candidates:
        vd     = f.get("_validator_decision", {})
        action = vd.get("action", "unknown")
        target = vd.get("target_file", "?")
        reason = vd.get("reason", "")

        print(f"\n  [{f['severity'].upper()}] {f['id'][:55]}")
        print(f"    page:   {f['page']}")
        print(f"    action: {action} -> {target}")
        print(f"    reason: {reason[:80]}")

        success = False

        if action == "journey_test":
            success = apply_journey_test(f, vd)
        elif action == "improve_existing":
            success = apply_improve_existing(f, vd)
        elif action == "add_new":
            success = apply_add_new_validator(f, vd)
        elif action == "accept":
            if not DRY_RUN:
                mark_gated(f, data, "accept")
                success = True
            else:
                print(f"    Would acknowledge (design-by-intent)")
                success = True
        else:
            skip(f"Unknown action: {action}")

        if success and not DRY_RUN:
            mark_gated(f, data, action)
            applied += 1

    if not DRY_RUN:
        save_findings(data)
        print(f"\n  Applied: {applied}/{len(candidates)}")
        if applied > 0:
            print("\n  Running L13 to verify loop closure...")
            closed = run_l13()
            if closed:
                print("\n  Loop CLOSED -- all findings gated.")
            else:
                print("\n  Loop OPEN -- some findings still ungated. Check findings.json.")
    else:
        print(f"\n  [DRY-RUN] Would apply {len(candidates)} proposals.")
        print("  Re-run with --apply to execute.")


if __name__ == "__main__":
    main()
