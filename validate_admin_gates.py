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
  L4  Loopback is opt-in     — a 127.0.0.1/localhost bypass needs localStorage wh_local_founder (2026-10-13)
  L5  Retired overlay gated  — a "has moved" overlay starts hidden or sits behind a head gate (2026-10-13)

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

# HTML files that MUST have an active admin gate. The second group joined 2026-10-13: the whole admin cohort (absent from
# nav-hub, reached by URL), after a driver persona read five of them in full on a local stack (Ian: "it seems that
# founder/admins function button or functions can still be seen by non-admins?").
ADMIN_SURFACES = [
    "founder-console.html",
    "marketplace-admin.html",
    "platform-actions.html",
    "llm-observability.html",
    "agentic-rag-observability.html",
]

LOOPBACK_LIST = re.compile(r"\[\s*['\"]127\.0\.0\.1['\"]\s*,\s*['\"]localhost['\"][^\]]*\]")


def _code_only(content: str) -> str:
    """Blank HTML and JS comments, keeping every newline (so line numbers hold) - a comment that QUOTES a bypass is not one."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    s = re.sub(r"<!--[\s\S]*?-->", blank, content)
    s = re.sub(r"/\*[\s\S]*?\*/", blank, s)
    s = re.sub(r"(?<![:'\"\\])//[^\n]*", blank, s)
    return s


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
        # the head-gate pattern (architecture, validator-catalog, symbol-gallery, the two observability pages): the
        # document stays hidden until the check, and a refusal replaces the body - "Founder access only"
        or "founder access only" in content.lower()
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

    code = _code_only(content)

    # L4 (2026-10-13): a LOOPBACK bypass is opt-in on the machine. Five admin pages skipped their gate entirely on
    # 127.0.0.1 / localhost for EVERY signed-in person, so on a local stack a driver read the founder pages in full.
    # founder-console.html made its bypass opt-in on 2026-10-09 (localStorage wh_local_founder = '1'); every loopback
    # host list in code must sit with that opt-in.
    for m in LOOPBACK_LIST.finditer(code):
        if "wh_local_founder" not in code[m.start(): m.end() + 300]:
            line = code.count("\n", 0, m.start()) + 1
            issues.append({
                "check": "admin_loopback_opt_in",
                "file": html_path.name,
                "line": line,
                "reason": (
                    f"{html_path.name}:{line} - a loopback host list with no wh_local_founder opt-in beside it: on a "
                    "local stack this admin page opens to every signed-in person."
                )
            })

    # L5 (2026-10-13): a RETIRED overlay on an admin page must not show before the admin check. founder-console and
    # marketplace-admin rendered "has moved" (Founder Ops dashboard, Platform Actions) to anyone, on every host, because
    # their boot returned before the gate. Protected means: the overlay starts display:none in the markup, OR the page
    # hides the whole document until the check passes (the head-gate pattern).
    ov = re.search(r'<div[^>]*id="wh-retired-overlay"[^>]*style="([^"]*)"', code)
    if ov:
        starts_hidden = re.search(r"display\s*:\s*none", ov.group(1)) and not re.search(r"display\s*:\s*(flex|block|grid)", ov.group(1))
        head_gate = re.search(r"documentElement\.style\.visibility\s*=\s*['\"]hidden['\"]", code)
        if not (starts_hidden or head_gate):
            line = code.count("\n", 0, ov.start()) + 1
            issues.append({
                "check": "admin_retired_overlay_before_gate",
                "file": html_path.name,
                "line": line,
                "reason": (
                    f"{html_path.name}:{line} - the retired overlay is visible before the admin check (no display:none "
                    "in its markup, no head gate): every visitor reads it."
                )
            })

    return issues


def main():
    def green(s): return f"\033[92m{s}\033[0m"
    def red(s):   return f"\033[91m{s}\033[0m"
    def bold(s):  return f"\033[1m{s}\033[0m"

    print(bold("\nAdmin Gate Validator (5-layer)"))
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
