"""
Em-Dash Validator — WorkHive Platform
======================================
Enforces the standing rule [[feedback-no-em-dashes]]: every public page must
use colons, commas, parentheses, or restructure instead of em dashes (` — `).

Em dashes degrade the natural-language quality of AI-generated answer
extraction (Perplexity, ChatGPT) and look inconsistent with our copy style.
This validator catches regressions before they ship.

What counts as a violation: any literal em-dash character (`—`, U+2014)
appearing inside visible body text. We skip JSON-LD blocks because schema.org
authors sometimes legitimately use em-dashes inside `description` strings,
but flag everything in HTML body / paragraph / heading text.

Usage:  python validate_em_dash.py
Output: em_dash_report.json
"""
import re, json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

LANDING_PAGE = "index.html"
STUB_PAGES   = ["about/index.html", "privacy-policy/index.html",
                "terms-of-service/index.html"]
LEARN_HUB    = "learn/index.html"
LEARN_ARTICLES = [
    "learn/start-digital-logbook-philippine-factory/index.html",
    "learn/what-is-oee-how-to-calculate/index.html",
    "learn/mtbf-vs-mttr-for-supervisors/index.html",
    "learn/maintenance-shift-handover-template/index.html",
    "learn/spare-parts-inventory-philippine-plants/index.html",
    "learn/free-pm-checklist-templates/index.html",
    "learn/skill-matrix-for-maintenance-technicians/index.html",
    "learn/dilo-wilo-day-planner-supervisors/index.html",
    "learn/free-engineering-calculators-philippine-plants/index.html",
    "learn/ai-work-assistant-maintenance-technicians/index.html",
    "learn/predictive-maintenance-on-a-budget-philippines/index.html",
    "learn/connecting-workhive-to-sap-maximo-cmms/index.html",
    "learn/voice-to-text-maintenance-philippine-plant-floor/index.html",
    "learn/building-asset-register-zero-budget/index.html",
    "learn/maintenance-project-planning-template/index.html",
    "learn/joining-and-growing-your-hive/index.html",
    "learn/industrial-community-of-practice-philippines/index.html",
    "learn/gamifying-maintenance-for-engagement/index.html",
    "learn/industrial-marketplace-philippine-specialists/index.html",
    "learn/predictive-alert-thresholds-plants/index.html",
    "learn/dole-iso-audit-trail-from-logbook/index.html",
    "learn/ai-quality-and-roi-stage-2-plants/index.html",
    "learn/sensor-cmms-gateway-operations/index.html",
    "learn/ph-industrial-benchmarks-intelligence/index.html",
]
ALL_PUBLIC = [LANDING_PAGE] + STUB_PAGES + [LEARN_HUB] + LEARN_ARTICLES

# Em-dash characters: U+2014 and the rarer U+2013 (en-dash) when surrounded
# by spaces (the visible " – " pattern). We DO NOT flag bare hyphens.
EM_DASH_RE = re.compile(r"[—]|\s–\s")

# Strip JSON-LD <script type="application/ld+json">...</script> blocks first
# because schema authors sometimes legitimately use em-dashes inside strings.
JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>.*?</script>',
    re.DOTALL | re.IGNORECASE,
)


def check_em_dashes(pages):
    """Every public page must use plain ASCII punctuation, no em or en dashes
    in body text. Reason: AEO/GEO answer-extraction quality + brand voice."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Strip JSON-LD blocks before scanning
        scannable = JSON_LD_RE.sub("", content)
        matches = list(EM_DASH_RE.finditer(scannable))
        if matches:
            # Sample first 3 matches with surrounding context for the report
            samples = []
            for m in matches[:3]:
                start = max(0, m.start() - 35)
                end   = min(len(scannable), m.end() + 35)
                snippet = scannable[start:end].replace("\n", " ").strip()
                samples.append(snippet)
            sample_text = " | ".join(samples)
            issues.append({"check": "em_dashes", "page": page,
                           "reason": (f"{page} has {len(matches)} em-dash(es). "
                                      f"Use colons, commas, parentheses, or restructure. "
                                      f"Samples: {sample_text}")})
    return issues


CHECK_NAMES  = ["em_dashes"]
CHECK_LABELS = {"em_dashes": "L1  No em or en dashes in public body text"}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEm-Dash Validator"))
    print("=" * 55)

    all_issues = check_em_dashes(ALL_PUBLIC)
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed across {len(ALL_PUBLIC)} pages.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "em_dash",
        "total_checks": len(CHECK_NAMES),
        "pages_scanned": len(ALL_PUBLIC),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("em_dash_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
