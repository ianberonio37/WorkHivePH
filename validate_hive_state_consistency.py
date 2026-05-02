"""
Hive-State LocalStorage Consistency Validator — WorkHive Platform
==================================================================
Catches branch asymmetry in hive.html where one code path writes only a
subset of the hive-identity localStorage keys, leaving downstream pages
to fall back to defaults like 'worker' role.

Root cause of the May 2026 community page bug:
  hive.html had 5 branches that write hive state — create-hive,
  join-hive, switch-active (twice), and recoverHiveMembership.
  Four wrote (id + active_id + name + role + code).
  One — the recovery branch — wrote only (id + active_id + code), missing
  name and role. On a fresh-device sign-in for a hive supervisor, every
  other page (community, marketplace-admin, mod queue, supervisor-only
  sections) read wh_hive_role as null, fell back to 'worker', and hid
  all supervisor UI from the actual hive supervisor.

Approach:
  Walk hive.html, find every block that calls
  localStorage.setItem('wh_active_hive_id', ...)
  and assert that within ~30 lines of that call, all four required keys
  appear together: wh_active_hive_id, wh_hive_id, wh_hive_name, wh_hive_role.
  wh_hive_code is optional (only known on create + join paths).

  Layer 1 — Branch symmetry
    1.  Every branch writing wh_active_hive_id also writes id + name + role  [FAIL]

Usage:  python validate_hive_state_consistency.py
Output: hive_state_consistency_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

PAGE = "hive.html"

# All 4 required keys per write-group (code is optional)
REQUIRED_KEYS = ("wh_active_hive_id", "wh_hive_id", "wh_hive_name", "wh_hive_role")

# Lines to inspect on each side of the anchor setItem call.
# Use a centered window because some branches put wh_active_hive_id FIRST
# (recovery, switch) and others put it LAST (create-hive: id → name → role → code → active_id).
WINDOW_LINES = 12

# Skip blocks that look like a legacy-migration step rather than a fresh write.
# In hive.html line ~669-674 there's a one-time migration that sets active_hive_id
# from `legId` after reading legName/legRole — name and role are already in
# localStorage from the legacy single-hive keys; the migration step doesn't need
# to re-write them.
LEGACY_MIGRATION_MARKERS = ("legId", "legName", "legRole", "legacy")

CHECKS = {
    "branch_symmetry":  "L1  Every branch writing wh_active_hive_id also writes id + name + role",
}
CHECK_LABELS = CHECKS
CHECK_NAMES  = list(CHECKS.keys())


def find_anchor_lines(content):
    """Return list of (line_number, line_text) for every setItem of wh_active_hive_id."""
    anchors = []
    for m in re.finditer(r"localStorage\.setItem\(\s*['\"]wh_active_hive_id['\"]", content):
        line = content[:m.start()].count("\n") + 1
        anchors.append(line)
    return anchors


def check_branch_symmetry(content):
    issues = []
    lines = content.split("\n")
    anchors = find_anchor_lines(content)
    if not anchors:
        # Page doesn't write hive-state localStorage at all — out of scope, not a bug
        return issues

    for anchor_line in anchors:
        # Centered window: WINDOW_LINES before + after
        start = max(0, anchor_line - 1 - WINDOW_LINES)
        end   = min(len(lines), anchor_line + WINDOW_LINES)
        block = "\n".join(lines[start:end])

        # Skip legacy-migration blocks (one-time read of legacy single-hive keys)
        if any(marker in block for marker in LEGACY_MIGRATION_MARKERS):
            continue

        missing = []
        for key in REQUIRED_KEYS:
            # Match either setItem of the key OR a forEach loop array that includes it
            pattern = (
                r"localStorage\.setItem\(\s*['\"]" + re.escape(key) + r"['\"]"
                r"|\[[^\]]*['\"]" + re.escape(key) + r"['\"]"
            )
            if not re.search(pattern, block):
                missing.append(key)
        if missing:
            issues.append({
                "check": "branch_symmetry",
                "reason": (
                    f"hive.html line {anchor_line}: branch writes wh_active_hive_id "
                    f"but the surrounding window is missing setItem for: {', '.join(missing)}. "
                    f"Every branch must write all 4 keys together — otherwise downstream "
                    f"pages (community, marketplace-admin, mod queue) fall back to default "
                    f"role and hide supervisor UI."
                )
            })
    return issues


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nHive-State LocalStorage Consistency Validator (1-layer)"))
    print("=" * 55)

    content = read_file(PAGE)
    if not content:
        print(f"  ERROR: {PAGE} not found")
        sys.exit(1)

    all_issues = check_branch_symmetry(content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)

    if n_fail == 0:
        anchors = find_anchor_lines(content)
        print(f"\033[92m\n  All {total} checks passed. ({len(anchors)} write-groups inspected)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "hive_state_consistency",
        "page":         PAGE,
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("hive_state_consistency_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
