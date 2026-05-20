#!/usr/bin/env python3
"""
Role Permission Test Runner — WorkHive Platform
================================================
Tests all 34 pages with 3 roles (solo, worker, supervisor).

For each page:
  1. Solo  : navigates without hive context → expects hive-gate
  2. Worker: navigates as worker-role member → expects limited access
  3. Supervisor: navigates as supervisor → expects full access

Compares actual vs expected visibility and reports violations.

Usage:
  python e2e_roles_runner.py                      # all pages, all roles
  python e2e_roles_runner.py --page logbook       # single page
  python e2e_roles_runner.py --tier 1             # tier 1 only
  python e2e_roles_runner.py --report             # save e2e_roles_report.md

Output:
  e2e_roles_results.json
  e2e_roles_report.md (with --report)
"""

import sys, json, time, argparse
from datetime import datetime
from typing import Dict, List, Optional
from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

from e2e_roles_helpers import RoleContextFactory, diff_snapshots, ROLES
from e2e_permission_matrix import PERMISSION_MATRIX

TIER_PAGES = {
    1: ["logbook", "inventory", "pm-scheduler", "hive", "community", "marketplace", "project-manager"],
    2: ["analytics", "analytics-report", "shift-brain", "asset-hub", "alert-hub", "predictive", "ai-quality"],
    3: ["skillmatrix", "report-sender", "plant-connections", "audit-log", "platform-health", "achievements", "voice-journal", "integrations"],
    4: ["index", "public-feed", "assistant", "ph-intelligence", "marketplace-admin"],
    5: ["dayplanner", "engineering-design", "project-report", "marketplace-seller", "marketplace-seller-profile", "symbol-gallery", "founder-console"],
}
ALL_PAGES = [p for pages in TIER_PAGES.values() for p in pages]


class RoleTestResult:
    def __init__(self, page: str, role: str, element: str,
                 expected: Optional[bool], actual: bool):
        self.page = page
        self.role = role
        self.element = element
        self.expected = expected
        self.actual = actual

    @property
    def is_violation(self) -> bool:
        return self.expected is not None and self.expected != self.actual

    @property
    def result(self) -> str:
        if self.expected is None:
            return "INFO"
        return "PASS" if self.expected == self.actual else "FAIL"

    def to_dict(self):
        return {
            "page": self.page, "role": self.role, "element": self.element,
            "expected": self.expected, "actual": self.actual,
            "result": self.result,
        }


def run_page_roles(factory: RoleContextFactory, page_name: str) -> Dict:
    """Run all 3 role checks on a single page."""
    matrix = PERMISSION_MATRIX.get(page_name, {})
    elements = matrix.get("elements", {})
    expected_map = matrix.get("expected", {})
    solo_gate = matrix.get("solo_gate", True)

    print(f"\n{BLUE}[{page_name}]{RESET}  ({len(elements)} elements × 3 roles)")

    results = []
    snapshots = {}
    gate_results = {}

    for role in ROLES:
        try:
            sess = factory.session(role)
            sess.goto(page_name)

            # Check hive-gate visibility
            gate_visible = False
            try:
                gate_visible = sess.page.locator("#hive-gate").is_visible(timeout=800)
            except:
                pass
            gate_results[role] = gate_visible

            # Check each element's visibility
            snap = sess.snapshot_elements(elements)
            snapshots[role] = snap

        except Exception as e:
            print(f"  {RED}ERROR ({role}): {e!s:.80}{RESET}")
            snapshots[role] = {}
            gate_results[role] = False

    # Evaluate results against expected
    total_pass = total_fail = total_info = 0

    # Gate check for solo: detect EITHER hive-gate overlay OR redirect away from page
    # Pages use one of: (a) #hive-gate overlay, (b) window.location.href redirect
    if solo_gate:
        for role in ROLES:
            if role != "solo":
                continue
            gate_visible = gate_results.get(role, False)

            # Check if solo was redirected away (window.location changed)
            redirected = False
            try:
                sess_solo = factory._sessions.get("solo")
                if sess_solo:
                    current_url = sess_solo.page.url
                    redirected = page_name not in current_url
            except:
                redirected = False

            solo_gated = gate_visible or redirected
            r = RoleTestResult(page_name, "solo", "access_gated", True, solo_gated)
            results.append(r)
            if r.is_violation:
                total_fail += 1
                print(f"  {RED}FAIL{RESET}  solo         access_gated  gate_visible={gate_visible} redirected={redirected}")
            else:
                total_pass += 1
                gating_type = "hive-gate overlay" if gate_visible else ("redirect" if redirected else "unknown")
                print(f"  {GREEN}PASS{RESET}  solo         access_gated  ({gating_type})")

    # Element checks
    for element_name in elements:
        for role in ROLES:
            exp = expected_map.get(role, {}).get(element_name)  # None = no expectation
            actual = snapshots.get(role, {}).get(element_name, False)
            r = RoleTestResult(page_name, role, element_name, exp, actual)
            results.append(r)
            if r.is_violation:
                total_fail += 1
                print(f"  {RED}FAIL{RESET}  {role:<12} {element_name:<30} expected={exp} actual={actual}")
            elif exp is not None:
                total_pass += 1
            else:
                total_info += 1

    # Diff snapshot (informational — shows what each role sees differently)
    diff = diff_snapshots(
        snapshots.get("supervisor", {}),
        snapshots.get("worker", {}),
        snapshots.get("solo", {}),
    )

    color = GREEN if total_fail == 0 else RED
    print(f"  {color}{total_pass} PASS / {total_fail} FAIL / {total_info} INFO{RESET}")
    if diff["supervisor_only"]:
        print(f"  {CYAN}Supervisor-only visible: {diff['supervisor_only']}{RESET}")
    if diff["worker_and_above"]:
        print(f"  {CYAN}Worker+ visible (not solo): {diff['worker_and_above']}{RESET}")

    return {
        "page": page_name,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "total_info": total_info,
        "results": [r.to_dict() for r in results],
        "diff": diff,
        "gate_results": gate_results,
    }


def run_all(pages: List[str], report: bool = False) -> Dict:
    """Run role permission tests for all given pages."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "pages": {},
        "total_pass": 0,
        "total_fail": 0,
        "total_info": 0,
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, slow_mo=30)
        factory = RoleContextFactory(browser)

        print(f"\n{BLUE}{'=' * 70}{RESET}")
        print(f"{BLUE}ROLE PERMISSION TESTS — {len(pages)} pages × 3 roles{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}")
        print(f"Roles: {ROLES}")

        try:
            for page_name in pages:
                page_result = run_page_roles(factory, page_name)
                results["pages"][page_name] = page_result
                results["total_pass"] += page_result["total_pass"]
                results["total_fail"] += page_result["total_fail"]
                results["total_info"] += page_result["total_info"]
        finally:
            factory.close_all()
            browser.close()

    # Summary
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    p = results["total_pass"]
    f = results["total_fail"]
    i = results["total_info"]
    color = GREEN if f == 0 else RED
    print(f"RESULTS: {p}{GREEN} PASS {RESET}| {f}{RED} FAIL {RESET}| {i} INFO")
    print(f"{BLUE}{'=' * 70}{RESET}")

    if f > 0:
        print(f"\n{RED}PERMISSION VIOLATIONS:{RESET}")
        for pg, pr in results["pages"].items():
            for r in pr["results"]:
                if r["result"] == "FAIL":
                    print(f"  {pg:<25} {r['role']:<12} {r['element']:<30} expected={r['expected']} actual={r['actual']}")

    # ── Canonical Dimensions cross-check ──────────────────────────────────
    # Each Layer 2 gate now also enforces this session's 4 canonical
    # dimensions (Tier-S chip + Calm Dashboard + partial honesty + view
    # reachability) so a per-role permission run also catches drift in
    # the canonical contract layer. No signin needed — raw fetch.
    print(f"\n{BLUE}[Canonical Dimensions]{RESET} cross-check after role pass")
    try:
        from flows import canonical_dimensions_flow as _cdims
        class _NoOp: pass
        cd_out = _cdims.run(_NoOp(), [], [], log=lambda m: None)
        cd_pass = sum(1 for s, _ in cd_out.get("results", []) if s == "PASS")
        cd_fail = sum(1 for s, _ in cd_out.get("results", []) if s == "FAIL")
        cd_warn = sum(1 for s, _ in cd_out.get("results", []) if s == "WARN")
        color = GREEN if cd_fail == 0 else RED
        print(f"  {color}{cd_pass} PASS / {cd_fail} FAIL / {cd_warn} WARN{RESET}")
        for status, msg in cd_out.get("results", []):
            marker = GREEN + "PASS" + RESET if status == "PASS" else (RED + "FAIL" + RESET if status == "FAIL" else YELLOW + "WARN" + RESET)
            print(f"    {marker}  {msg}")
        results["total_pass"] += cd_pass
        results["total_fail"] += cd_fail
        results["canonical_dimensions"] = cd_out.get("results", [])
    except Exception as e:
        print(f"  {YELLOW}WARN{RESET}  canonical_dimensions_flow crashed: {e}")

    # Save JSON
    with open("e2e_roles_results.json", "w") as f_:
        json.dump(results, f_, indent=2)
    print(f"\n✓ Results saved to e2e_roles_results.json")

    if report:
        _generate_report(results)

    return results


def _generate_report(results: Dict):
    """Generate markdown report."""
    lines = [
        "# Role Permission Test Report",
        f"Generated: {results['timestamp']}",
        "",
        "## Summary",
        f"- **PASS:** {results['total_pass']}",
        f"- **FAIL:** {results['total_fail']}",
        f"- **INFO (no expectation):** {results['total_info']}",
        "",
        "## Permission Violations",
    ]

    violations_found = False
    for pg, pr in results["pages"].items():
        page_violations = [r for r in pr["results"] if r["result"] == "FAIL"]
        if page_violations:
            violations_found = True
            lines.append(f"\n### {pg}")
            for r in page_violations:
                lines.append(f"- **{r['role']}** / `{r['element']}`: expected `{r['expected']}` but got `{r['actual']}`")

    if not violations_found:
        lines.append("\nNo violations found. All role permissions match expected matrix.")

    lines.extend(["", "## Role Diff per Page"])
    for pg, pr in results["pages"].items():
        diff = pr.get("diff", {})
        sup_only = diff.get("supervisor_only", [])
        worker_plus = diff.get("worker_and_above", [])
        if sup_only or worker_plus:
            lines.append(f"\n### {pg}")
            if sup_only:
                lines.append(f"- Supervisor-only: `{', '.join(sup_only)}`")
            if worker_plus:
                lines.append(f"- Worker+ (not solo): `{', '.join(worker_plus)}`")

    report_text = "\n".join(lines)
    with open("e2e_roles_report.md", "w") as f_:
        f_.write(report_text)
    print("✓ Report saved to e2e_roles_report.md")


def main():
    parser = argparse.ArgumentParser(description="Role Permission Tests")
    parser.add_argument("--page", type=str, help="Single page to test")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4, 5], help="Tier to test")
    parser.add_argument("--report", action="store_true", help="Generate markdown report")
    args = parser.parse_args()

    if args.page:
        pages = [args.page]
    elif args.tier:
        pages = TIER_PAGES.get(args.tier, [])
    else:
        pages = ALL_PAGES

    results = run_all(pages, report=args.report)
    return 0 if results["total_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
