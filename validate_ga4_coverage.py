"""
GA4 Coverage Validator — WorkHive Platform
===========================================
Enforces [[project-phase-5-measurement-live]]: every public-facing HTML page
MUST have the GA4 gtag snippet AND load wh-ga4.js. Without this, new pages
silently miss analytics.

Catches the most common drift pattern: someone adds a new article (or stub),
adds it to sitemap.xml, but forgets to run `python tools/wire_ga4.py`.

Layer 1: <!-- WorkHive GA4 --> block present in <head> of every public page
Layer 2: wh-ga4.js loaded via <script src="/wh-ga4.js"> on every public page
Layer 3: Measurement ID is the canonical G-ENMGLTFR2J on every page
         (catches the case where someone hardcodes a placeholder or wrong ID)
Layer 4: wh-ga4.js file exists at project root (the script the pages load)

Usage:  python validate_ga4_coverage.py
Output: ga4_coverage_report.json
"""
import re, json, sys, os
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

CANONICAL_GA4_ID = "G-ENMGLTFR2J"

PUBLIC_PAGES = [
    "index.html", "about/index.html", "privacy-policy/index.html",
    "terms-of-service/index.html", "learn/index.html",
] + [f"learn/{slug}/index.html" for slug in [
    "start-digital-logbook-philippine-factory",
    "what-is-oee-how-to-calculate",
    "mtbf-vs-mttr-for-supervisors",
    "maintenance-shift-handover-template",
    "spare-parts-inventory-philippine-plants",
    "free-pm-checklist-templates",
    "skill-matrix-for-maintenance-technicians",
    "dilo-wilo-day-planner-supervisors",
    "free-engineering-calculators-philippine-plants",
    "ai-work-assistant-maintenance-technicians",
    "predictive-maintenance-on-a-budget-philippines",
    "connecting-workhive-to-sap-maximo-cmms",
    "voice-to-text-maintenance-philippine-plant-floor",
    "building-asset-register-zero-budget",
    "maintenance-project-planning-template",
    "joining-and-growing-your-hive",
    "industrial-community-of-practice-philippines",
    "gamifying-maintenance-for-engagement",
    "industrial-marketplace-philippine-specialists",
    "predictive-alert-thresholds-plants",
    "dole-iso-audit-trail-from-logbook",
    "ai-quality-and-roi-stage-2-plants",
    "sensor-cmms-gateway-operations",
    "ph-industrial-benchmarks-intelligence",
]]

GA4_BLOCK_RE  = re.compile(r"<!--\s*WorkHive GA4\s*-->.*?<!--\s*/WorkHive GA4\s*-->", re.DOTALL)
WH_GA4_LOAD   = re.compile(r'<script[^>]+src=["\']/wh-ga4\.js["\']', re.IGNORECASE)


def check_block_present(pages):
    """Every public page must have the canonical GA4 block in <head>."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            issues.append({"check": "block_present", "page": page,
                           "reason": f"{page} not found"})
            continue
        if not GA4_BLOCK_RE.search(content):
            issues.append({"check": "block_present", "page": page,
                           "reason": (f"{page} missing <!-- WorkHive GA4 --> "
                                      f"block. Run: "
                                      f"python tools/wire_ga4.py {CANONICAL_GA4_ID}")})
    return issues


def check_wh_ga4_loaded(pages):
    """Every public page must load wh-ga4.js (the 6-custom-event helper)."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not WH_GA4_LOAD.search(content):
            issues.append({"check": "wh_ga4_loaded", "page": page,
                           "reason": (f"{page} does not load /wh-ga4.js. "
                                      f"Without it, the 6 WorkHive custom "
                                      f"events (signup_form_view, faq_open, "
                                      f"learn_article_read_80pct, etc.) won't "
                                      f"fire. Re-run tools/wire_ga4.py.")})
    return issues


def check_canonical_id(pages):
    """Every page's GA4 block must reference G-ENMGLTFR2J (not a placeholder
    or a wrong ID typo)."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        m = GA4_BLOCK_RE.search(content)
        if not m:
            continue   # already reported by block_present check
        block = m.group(0)
        if CANONICAL_GA4_ID not in block:
            # Find what ID IS in the block, if any
            id_m = re.search(r"G-[A-Z0-9]{6,12}", block)
            wrong_id = id_m.group(0) if id_m else "(none)"
            issues.append({"check": "canonical_id", "page": page,
                           "reason": (f"{page} GA4 block uses ID '{wrong_id}', "
                                      f"expected '{CANONICAL_GA4_ID}'. "
                                      f"Re-run tools/wire_ga4.py to fix.")})
    return issues


def check_wh_ga4_file_exists():
    """The wh-ga4.js file (the actual JS the pages load) must exist at root."""
    if not os.path.isfile("wh-ga4.js"):
        return [{"check": "wh_ga4_file", "page": "wh-ga4.js",
                 "reason": ("wh-ga4.js missing at project root. Without this "
                            "file, the 6 custom WorkHive events never fire "
                            "even though every page tries to load it (404 "
                            "in production).")}]
    # Sanity: confirm it has the expected custom-event keys
    content = read_file("wh-ga4.js") or ""
    required_events = ["signup_form_view", "signup_form_submit",
                       "learn_article_read_80pct", "cta_tool_click",
                       "faq_open", "external_link_click"]
    missing = [e for e in required_events if e not in content]
    if missing:
        return [{"check": "wh_ga4_file", "page": "wh-ga4.js",
                 "reason": (f"wh-ga4.js exists but missing event handler(s) "
                            f"for: {missing}. Restore from git history or "
                            f"re-author per project_phase_5_measurement_live.")}]
    return []


CHECK_NAMES  = ["block_present", "wh_ga4_loaded", "canonical_id", "wh_ga4_file"]
CHECK_LABELS = {
    "block_present": "L1  Every public page has <!-- WorkHive GA4 --> block in <head>",
    "wh_ga4_loaded": "L2  Every public page loads /wh-ga4.js",
    "canonical_id":  "L3  Every GA4 block uses the canonical G-ENMGLTFR2J Measurement ID",
    "wh_ga4_file":   "L4  /wh-ga4.js exists at project root with all 6 custom events",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nGA4 Coverage Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_block_present(PUBLIC_PAGES)
    all_issues += check_wh_ga4_loaded(PUBLIC_PAGES)
    all_issues += check_canonical_id(PUBLIC_PAGES)
    all_issues += check_wh_ga4_file_exists()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed across "
              f"{len(PUBLIC_PAGES)} public pages.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "ga4_coverage",
        "total_checks":   len(CHECK_NAMES),
        "pages_scanned":  len(PUBLIC_PAGES),
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    with open("ga4_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
