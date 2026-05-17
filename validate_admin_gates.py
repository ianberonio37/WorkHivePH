"""
Admin Gate Validator — WorkHive Platform
=========================================
Verifies that admin-only HTML surfaces have an ACTIVE (not commented-out)
admin authentication gate before rendering the page content.

Background (2026-05-17):
  Layer 2 role permission runner found founder-console accessible to ALL
  roles including solo. Root cause: admin gate was disabled for local
  testing and the comment block was never re-enabled. This validator
  prevents that class of regression from shipping.

Layers:
  L1  Admin gate present     — file calls isPlatformAdmin(db) at top-level
  L2  Gate not commented     — the isPlatformAdmin call is not inside //
  L3  Gate logic complete    — file shows no-access UI when gate fails

Usage:  python validate_admin_gates.py
Output: admin_gates_report.json
"""
import re
import sys
import json
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# HTML files that MUST have an active admin gate
ADMIN_SURFACES = [
    "founder-console.html",
    "marketplace-admin.html",
    "platform-health.html",
]


def check_admin_gate_active(html_path: Path) -> list:
    """Return a list of issue dicts (empty if all checks pass)."""
    if not html_path.exists():
        return [{
            "check": "admin_gate_active",
            "file": html_path.name,
            "reason": f"{html_path.name} not found — cannot verify admin gate"
        }]

    try:
        content = html_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"check": "admin_gate_active", "file": html_path.name, "reason": f"Read error: {e}"}]

    issues = []

    # L1: file must verify admin access. Accept either:
    #  (a) call to a helper: isPlatformAdmin / verifyPlatformAdmin / etc.
    #  (b) direct query to the marketplace_platform_admins table
    admin_fn_names = ["isPlatformAdmin", "verifyPlatformAdmin", "is_platform_admin", "checkAdminAccess"]
    has_fn_call    = any(name in content for name in admin_fn_names)
    has_direct_qry = "marketplace_platform_admins" in content
    has_admin_call = has_fn_call or has_direct_qry
    if not has_admin_call:
        issues.append({
            "check": "admin_gate_present",
            "file": html_path.name,
            "reason": (
                f"{html_path.name} has no isPlatformAdmin(db) call. "
                "Admin-only surfaces must verify access before rendering."
            )
        })
        return issues

    # L2: the admin verification CALL must NOT be commented out.
    # Match actual function call patterns, not doc-comments mentioning the name.
    call_pattern = re.compile(r"(await\s+)?(isPlatformAdmin|verifyPlatformAdmin|checkAdminAccess)\s*\(")
    has_active_call = False
    for i, line in enumerate(content.splitlines(), 1):
        if not call_pattern.search(line):
            continue
        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("*"):
            issues.append({
                "check": "admin_gate_not_commented",
                "file": html_path.name,
                "line": i,
                "reason": (
                    f"{html_path.name}:{i} — isPlatformAdmin() call is commented out. "
                    "This was the founder-console regression on 2026-05-17. "
                    "Uncomment the gate before deploy."
                )
            })
        else:
            has_active_call = True

    if not has_active_call and has_fn_call and not has_direct_qry:
        # File uses helper-function pattern but the call is commented out
        issues.append({
            "check": "admin_gate_active_call",
            "file": html_path.name,
            "reason": (
                f"{html_path.name} has no ACTIVE admin verification call "
                "(only comments or doc references). Admin gate must be enforced."
            )
        })

    # L3: must have a no-access UI element (no-access-gate or similar)
    has_no_access_ui = (
        "no-access-gate" in content
        or "no-access" in content
        or "restricted" in content.lower()
        or "not signed in or not admin" in content.lower()
    )
    if not has_no_access_ui:
        issues.append({
            "check": "admin_gate_no_access_ui",
            "file": html_path.name,
            "reason": (
                f"{html_path.name} has no no-access UI element. "
                "Users who fail the admin check should see a clear message."
            )
        })

    return issues


def main():
    def green(s): return f"\033[92m{s}\033[0m"
    def red(s):   return f"\033[91m{s}\033[0m"
    def bold(s):  return f"\033[1m{s}\033[0m"

    print(bold("\nAdmin Gate Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    for surface in ADMIN_SURFACES:
        path = ROOT / surface
        issues = check_admin_gate_active(path)
        if issues:
            for iss in issues:
                print(f"  {red('FAIL')}  {surface:30}  {iss['reason'][:60]}")
            all_issues.extend(issues)
        else:
            print(f"  {green('PASS')}  {surface:30}  admin gate active")

    print()
    total = len(ADMIN_SURFACES)
    fails = len(all_issues)
    passed = total - fails  # rough: each surface either passes all or fails

    if fails == 0:
        print(green(f"  All {total} admin surfaces have active gates."))
    else:
        print(red(f"  {fails} issue(s) across {total} admin surfaces."))

    # Write report
    report = {
        "validator": "admin_gates",
        "total_surfaces": total,
        "issues": all_issues,
        "passed": fails == 0,
    }
    (ROOT / "admin_gates_report.json").write_text(json.dumps(report, indent=2))
    print("  Report: admin_gates_report.json")

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
