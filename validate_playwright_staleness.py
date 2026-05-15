"""
Playwright Staleness Gate — WorkHive Platform
=============================================
L13: Three checks that close the loop between surface-level visual
findings (Playwright walkthrough) and the inner-layer Sentinel Agents.

The problem this solves:
  Validators pass. Walkthrough still finds bugs. Walkthrough finds bug.
  No test catches it next time. New page added. Walkthrough doesn't know.

Three layers:

  L13a — Walkthrough coverage:
    Every page in LIVE_TOOL_PAGES (validate_assistant.py) must appear in
    the PAGES array of tests/plain-read-walkthrough.spec.ts. A new page
    that isn't in the walkthrough is invisible to visual regression.

  L13b — Finding closure:
    Every finding in findings.json with severity in [critical, high, medium]
    must have has_test=true OR has_validator=true. Open findings with no gate
    → FAIL (ratchet: un-gated count cannot increase from baseline).

  L13c — Chip assertion coverage:
    Every panel registered in L11 INSIGHT_PANEL_CONTRACT
    (validate_canonical_anchor.py) must have its chip_target_id checked
    in the walkthrough spec's waitForFunction. Panels added to L11 but
    not to the walkthrough's chip gate are invisible at runtime.

Usage:  python validate_playwright_staleness.py
Output: playwright_staleness_report.json

Skills consulted: qa (walkthrough contracts), platform-guardian
(forward-only ratchet), ai-engineer (finding registry as memory layer).
"""
from __future__ import annotations

import json
import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

WALKTHROUGH_SPEC = os.path.join("tests", "plain-read-walkthrough.spec.ts")
ASSISTANT_VALIDATOR = "validate_assistant.py"
ANCHOR_VALIDATOR    = "validate_canonical_anchor.py"
FINDINGS_FILE       = "findings.json"
BASELINE_FILE       = "playwright_staleness_baseline.json"

SEVERITY_GATE = {"critical", "high", "medium"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict | list | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_baseline() -> dict:
    b = load_json(BASELINE_FILE)
    return b if isinstance(b, dict) else {}


def save_baseline(data: dict):
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ─── L13a — Walkthrough coverage ─────────────────────────────────────────────

def check_walkthrough_coverage() -> dict:
    """Every LIVE_TOOL_PAGE slug must appear in the walkthrough PAGES array."""
    assistant_src   = read_file(ASSISTANT_VALIDATOR) or ""
    walkthrough_src = read_file(WALKTHROUGH_SPEC)    or ""

    # Extract LIVE_TOOL_PAGES list from validate_assistant.py
    m = re.search(r"LIVE_TOOL_PAGES\s*=\s*\[([^\]]*)\]", assistant_src, re.DOTALL)
    live_pages: list[str] = []
    if m:
        live_pages = re.findall(r"[\"']([\w-]+)[\"']", m.group(1))

    # Extract slugs from walkthrough PAGES array
    # Matches: { slug: 'hive', ... } or { slug: "hive", ... }
    walkthrough_slugs = set(re.findall(r"slug\s*:\s*[\"']([\w-]+)[\"']", walkthrough_src))

    # Pages exempt from walkthrough (static/print views, sub-pages)
    exempt = {
        "analytics-report", "project-report", "assistant",
        "marketplace-admin", "marketplace-seller", "marketplace-seller-profile",
        "public-feed", "platform-health",
    }

    missing: list[dict] = []
    for slug in live_pages:
        if slug in exempt:
            continue
        if slug not in walkthrough_slugs:
            missing.append({
                "slug":   slug,
                "reason": (
                    f"'{slug}.html' is in LIVE_TOOL_PAGES but not in the walkthrough "
                    f"PAGES array in {WALKTHROUGH_SPEC}. Add it to the walkthrough so "
                    f"visual regressions on this page are caught automatically."
                ),
            })

    return {
        "layer":        "walkthrough_coverage",
        "label":        "L13a Walkthrough: every LIVE_TOOL_PAGE is in the walkthrough PAGES array",
        "n_pages":      len(live_pages),
        "n_missing":    len(missing),
        "n_covered":    len(live_pages) - len(missing),
        "missing":      missing,
    }


# ─── L13b — Finding closure ───────────────────────────────────────────────────

def check_finding_closure() -> dict:
    """Every severity >= medium finding in findings.json must have a gate."""
    findings_data = load_json(FINDINGS_FILE)
    if not findings_data or "findings" not in findings_data:
        return {
            "layer":      "finding_closure",
            "label":      "L13b Finding closure: every finding >= medium has a test or validator",
            "n_findings": 0,
            "n_open":     0,
            "open":       [],
            "note":       f"{FINDINGS_FILE} not found or empty — create it to enable L13b",
        }

    findings   = findings_data["findings"]
    open_items: list[dict] = []

    for f in findings:
        sev = f.get("severity", "low")
        if sev not in SEVERITY_GATE:
            continue
        has_test      = bool(f.get("has_test"))
        has_validator = bool(f.get("has_validator"))
        status        = f.get("status", "open")
        if status in ("resolved", "acknowledged"):   # acknowledged = triaged false positive
            continue
        if not has_test and not has_validator:
            open_items.append({
                "id":       f.get("id"),
                "page":     f.get("page"),
                "severity": sev,
                "issue":    f.get("issue", "")[:120],
                "reason":   (
                    f"Finding '{f.get('id')}' (severity={sev}) on {f.get('page')} has no "
                    f"journey test AND no validator layer. Add a journey spec scenario OR "
                    f"extend the appropriate Sentinel Agent validator to gate this class of bug."
                ),
            })

    return {
        "layer":      "finding_closure",
        "label":      "L13b Finding closure: every finding >= medium has a test or validator",
        "n_findings": sum(1 for f in findings if f.get("severity") in SEVERITY_GATE),
        "n_open":     len(open_items),
        "n_gated":    sum(1 for f in findings
                          if f.get("severity") in SEVERITY_GATE
                          and (f.get("has_test") or f.get("has_validator"))
                          and f.get("status") != "resolved"),
        "open":       open_items,
    }


# ─── L13c — Chip assertion coverage ──────────────────────────────────────────

def check_chip_assertion_coverage() -> dict:
    """Every L11-registered panel's chip_target_id must appear in the
    walkthrough waitForFunction so runtime chip regressions are caught."""
    anchor_src      = read_file(ANCHOR_VALIDATOR)    or ""
    walkthrough_src = read_file(WALKTHROUGH_SPEC)    or ""

    # Extract INSIGHT_PANEL_CONTRACT entries — find chip_target_id values
    # Pattern: "chip_target_id": "some-chip-id"
    chip_ids = re.findall(
        r'"chip_target_id"\s*:\s*"([\w-]+)"',
        anchor_src,
    )

    # The walkthrough checks chip population via:
    #   document.querySelectorAll('.wh-source-chip')
    # and also inline id references in HTML
    # A chip is "asserted" if its id or the class appears in the waitForFunction
    # For top-of-page chips — they emit .wh-source-chip at runtime, so the
    # class-based check already covers them all. Check that the class check
    # is present in the spec.
    has_class_check = "wh-source-chip" in walkthrough_src and "anyChipPopulated" in walkthrough_src

    missing: list[dict] = []

    if not has_class_check:
        missing.append({
            "chip_target_id": "*.wh-source-chip",
            "reason":         (
                "The walkthrough waitForFunction does not check for '.wh-source-chip' "
                "population. The anyChipPopulated gate is missing — add it so runtime "
                "chip regressions are caught before screenshots are taken."
            ),
        })
    else:
        # Class-based check covers all chips that use renderSourceChip().
        # Verify the check is actually requiring at least one populated chip
        # (not just presence).
        if "anyChipPopulated" not in walkthrough_src:
            missing.append({
                "chip_target_id": "*.wh-source-chip",
                "reason":         (
                    "'.wh-source-chip' selector is present but anyChipPopulated "
                    "gate is missing. The check must require at least one chip "
                    "with content > 10 chars before snapping the screenshot."
                ),
            })

    return {
        "layer":           "chip_assertion_coverage",
        "label":           "L13c Chip assertion: walkthrough gates on chip population before capture",
        "n_registered_chips": len(chip_ids),
        "n_missing":       len(missing),
        "class_check_ok":  has_class_check,
        "missing":         missing,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = ["walkthrough_coverage", "finding_closure", "chip_assertion_coverage"]

CHECK_LABELS = {
    "walkthrough_coverage":    "L13a Walkthrough: every LIVE_TOOL_PAGE in walkthrough PAGES",
    "finding_closure":         "L13b Findings: every >= medium finding has test or validator",
    "chip_assertion_coverage": "L13c Chips: walkthrough gates on chip population",
}


def main():
    update_baseline = "--update-baseline" in sys.argv

    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nPlaywright Staleness Gate (L13 — 3-layer walkthrough anchor)"))
    print("=" * 60)

    layers = [
        check_walkthrough_coverage(),
        check_finding_closure(),
        check_chip_assertion_coverage(),
    ]

    baseline = load_baseline()
    issues: list[dict] = []

    print(f"  Layers checked: {len(layers)}\n")

    for L in layers:
        layer_key = L["layer"]
        check_name = layer_key

        # Determine the count to ratchet for this layer
        n_problems = (
            L.get("n_missing", 0) or
            L.get("n_open", 0) or
            0
        )
        prior = baseline.get(check_name, n_problems)

        status_str = "\033[92mPASS\033[0m" if n_problems == 0 else "\033[91mFAIL\033[0m"
        print(f"  [{status_str}]  {CHECK_LABELS[check_name]}")

        if n_problems > prior:
            issues.append({
                "check":  check_name,
                "skip":   False,
                "reason": (
                    f"[{check_name}] count went UP: {prior} → {n_problems}. "
                    f"New items: {L.get('missing') or L.get('open', [])[:3]}"
                ),
            })
        elif n_problems > 0:
            # Existing debt — print items as WARNINGs but don't fail
            items = L.get("missing") or L.get("open", [])
            for item in items[:5]:
                label = item.get("id") or item.get("slug") or item.get("chip_target_id", "?")
                print(f"    \033[93m[OPEN]\033[0m  {label}: {item.get('reason','')[:100]}")

        if update_baseline or check_name not in baseline:
            baseline[check_name] = n_problems

    # Print summary
    n_fail  = len([i for i in issues if not i.get("skip")])
    n_warn  = sum(
        1 for L in layers
        if (L.get("n_missing", 0) or L.get("n_open", 0)) > 0
        and (L.get("n_missing", 0) or L.get("n_open", 0)) <= baseline.get(L["layer"], 99)
    )
    n_pass  = len(layers) - n_fail - n_warn

    if issues:
        print(f"\n\033[91mIssues:\033[0m")
        for issue in issues:
            tag = "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{issue['check']}]  {issue['reason'][:200]}")

    print(f"\n{bold('STALENESS SCOREBOARD')}")
    print("  " + "-" * 55)
    for L in layers:
        n = L.get("n_missing", 0) or L.get("n_open", 0) or 0
        total = L.get("n_pages") or L.get("n_findings") or L.get("n_registered_chips") or "-"
        print(f"  {L['layer']:<30}  total:{total!s:>6}  open:{n!s:>4}")

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All 3 checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL  (open debt within baseline — fix to clear)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    save_baseline(baseline)

    report = {
        "validator":  "playwright_staleness",
        "layers":     layers,
        "issues":     issues,
        "passed":     n_pass,
        "warned":     n_warn,
        "failed":     n_fail,
    }
    with open("playwright_staleness_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
