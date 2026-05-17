"""
Audience Block Validator — WorkHive Platform
=============================================
Enforces [[feedback-full-audience-spectrum]]: every /learn/ article must
explicitly address the FULL industrial audience (field workers, engineers,
supervisors, managers, suppliers, contractors, new graduates, upskilling
workers), not just maintenance technicians.

The enforcement mechanism is the cyan "Who this is for" mini-section near
the top of every article. If an article ships without it, the article
silently excludes 60% of the addressable audience.

Layer 1: Every /learn/<slug>/index.html has a "Who this is for" or "Who
         this is for:" heading block
Layer 2: That block enumerates at least 4 distinct audience role types
         (so a single-role article doesn't slip through with just
         "Maintenance technicians" listed)
Layer 3: At least ONE of the roles must be from the broader-than-technicians
         set: field worker / engineer / supervisor / manager / supplier /
         contractor / graduate / new hire / upskilling

Usage:  python validate_audience_block.py
Output: audience_block_report.json
"""
import re, json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

LEARN_ARTICLES = [f"learn/{slug}/index.html" for slug in [
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

# Match the "Who this is for" heading in any common form (h2/h3/strong/b)
# with optional trailing colon.
HEADING_RE = re.compile(r"who this is for\s*:?\s*<", re.IGNORECASE)

# Roles considered "broader than technicians" per feedback_full_audience_spectrum.
# Expanded after 2026-05-17 first-run caught two articles whose audience blocks
# legitimately covered officers/coordinators/inspectors/auditors/directors/
# analysts/consultants but the validator's keyword set was too narrow.
BROADER_ROLES = [
    # field roles
    "field worker", "field operator", "operator",
    # engineering roles
    "engineer", "reliability engineer", "design engineer",
    # supervisory + planning
    "supervisor", "shift supervisor", "planner", "coordinator",
    # management + executive
    "manager", "plant manager", "operations manager", "director",
    "officer", "safety officer",
    # external roles
    "supplier", "vendor", "contractor", "subcontractor",
    "auditor", "inspector",
    "analyst", "consultant",
    # career-track
    "graduate", "new graduate", "new hire", "junior",
    "upskill", "upskilling",
]


def _extract_audience_block(content: str) -> str:
    """Return the ~600-char window starting at 'Who this is for' so we can
    inspect it for role enumeration. Returns '' if heading not found."""
    m = HEADING_RE.search(content)
    if not m:
        return ""
    start = m.start()
    return content[start:start + 1200]


def check_heading_present(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not HEADING_RE.search(content):
            issues.append({"check": "heading_present", "page": page,
                           "reason": (f"{page} missing 'Who this is for' "
                                      f"audience block. Required by "
                                      f"feedback_full_audience_spectrum. "
                                      f"Without it the article silently "
                                      f"excludes the 60% non-technician "
                                      f"audience.")})
    return issues


def check_role_count(pages):
    """The audience block must enumerate 4+ distinct role types so a
    single-role article doesn't slip through."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        block = _extract_audience_block(content)
        if not block:
            continue   # heading_present already flagged
        # Count distinct role-keyword hits in the block (case-insensitive)
        low = block.lower()
        seen = set()
        all_role_terms = BROADER_ROLES + ["technician", "operator", "worker"]
        for role in all_role_terms:
            if role in low:
                # Normalise so "engineer" and "reliability engineer" don't
                # double-count the same audience type.
                seen.add(role.split()[-1])
        if len(seen) < 4:
            issues.append({"check": "role_count", "page": page,
                           "reason": (f"{page} audience block only mentions "
                                      f"{len(seen)} distinct role(s): "
                                      f"{sorted(seen)}. Expand to 4+ roles "
                                      f"(field worker, engineer, supervisor, "
                                      f"manager, supplier, contractor, "
                                      f"graduate, upskiller).")})
    return issues


def check_beyond_technicians(pages):
    """At least one role must be from the broader-than-technicians set."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        block = _extract_audience_block(content)
        if not block:
            continue   # heading_present already flagged
        low = block.lower()
        broader_hits = [r for r in BROADER_ROLES if r in low]
        if not broader_hits:
            issues.append({"check": "beyond_technicians", "page": page,
                           "reason": (f"{page} audience block lists only "
                                      f"technicians / operators / workers. "
                                      f"Add at least one of: engineer, "
                                      f"supervisor, manager, supplier, "
                                      f"contractor, graduate, upskiller.")})
    return issues


CHECK_NAMES  = ["heading_present", "role_count", "beyond_technicians"]
CHECK_LABELS = {
    "heading_present":    "L1  Every /learn/ article has 'Who this is for' heading",
    "role_count":         "L2  Audience block enumerates 4+ distinct role types",
    "beyond_technicians": "L3  At least one role from the broader (non-technician) set",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAudience Block Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_heading_present(LEARN_ARTICLES)
    all_issues += check_role_count(LEARN_ARTICLES)
    all_issues += check_beyond_technicians(LEARN_ARTICLES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed across "
              f"{len(LEARN_ARTICLES)} /learn/ articles.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":     "audience_block",
        "total_checks":  len(CHECK_NAMES),
        "articles_scanned": len(LEARN_ARTICLES),
        "passed":        n_pass,
        "warned":        n_warn,
        "failed":        n_fail,
        "issues":        [i for i in all_issues if not i.get("skip")],
        "warnings":      [i for i in all_issues if i.get("skip")],
    }
    with open("audience_block_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
