"""
Data Quality Validator — WorkHive Platform
==========================================
Addresses the top data problems that break AI systems (per industry research).
WorkHive's MTBF calculations, RAG knowledge base, and predictive analytics
all depend on clean, consistent, labelled logbook data. Garbage in = garbage out.

  Layer 1 — Machine name consistency                        [Problem 09, 12, 17]
    1.  MTBF groups by raw machine name — "PUMP A" and "pump a" create separate
        MTBF buckets. The loadMtbf() function must normalize machine names
        (at minimum .trim()) before grouping by machine key.

  Layer 2 — Breakdown entry data completeness               [Problem 06, 08]
    2.  Breakdown / Corrective entries must enforce failure_consequence on save.
        The consequence section is shown but never required — workers can save
        without it, leaving RCM Consequence Analysis with no data to work with.
    3.  category is shown in the save form but never validated as required.
        A null category means the entry cannot be grouped in Pareto analysis
        or filtered in RAG semantic search.

  Layer 3 — Canonical label consistency                     [Problem 12, 16]
    4.  Both the add form and the edit form must use identical maintenance_type
        and category option lists. A mismatch means edited entries can have
        values the add form never produces, creating inconsistent groupings.
    5.  failure_consequence accepts only the 4 SAE JA1011 canonical values
        (Hidden / Running reduced / Safety risk / Stopped production).
        Any other value silently breaks RCM consequence distribution charts.

  Layer 4 — Duplicate entry prevention                      [Problem 05]
    6.  No UNIQUE constraint or pre-insert duplicate check on logbook entries.
        Same worker + machine + date = duplicate — inflates failure count,
        corrupts MTBF, and creates noisy RAG embeddings of identical context.

Usage:  python validate_data_quality.py
Output: data_quality_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LOGBOOK_PAGE = "logbook.html"
HIVE_PAGE    = "hive.html"

# ── Canonical values ──────────────────────────────────────────────────────────

CANONICAL_MAINT_TYPES = [
    "Breakdown / Corrective",
    "Preventive Maintenance",
    "Inspection",
    "Project Work",
]

CANONICAL_CATEGORIES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Other",
]

CANONICAL_CONSEQUENCES = [
    "Hidden",
    "Running reduced",
    "Safety risk",
    "Stopped production",
]


# ── Layer 1: Machine name consistency ─────────────────────────────────────────

def check_mtbf_machine_normalization(page):
    """
    loadMtbf() in hive.html groups entries by raw e.machine string.
    Without normalization, "PUMP A", "pump a", and "Pump A" each become
    a separate MTBF group — a single machine appears as 3 machines with
    1 failure each (below the 2-failure minimum), silently excluded from
    all MTBF calculations entirely.

    The fix: use a normalized key for grouping:
      const key = (e.machine || '').trim();
      if (!byMachine[key]) byMachine[key] = [];
      byMachine[key].push(...);

    The DISPLAY name can still use the original casing. Only the GROUP KEY
    needs normalization. This aligns with the asset lookup pattern already
    in logbook.html which uses .toUpperCase() for matching.
    """
    content = read_file(page)
    if content is None:
        return [{"check": "mtbf_machine_normalization", "page": page,
                 "reason": f"{page} not found"}]

    # Find the loadMtbf function body
    m = re.search(r"async function loadMtbf\s*\(", content)
    if not m:
        return [{"check": "mtbf_machine_normalization", "page": page,
                 "reason": f"{page} loadMtbf() not found — cannot verify machine name normalization"}]

    body = content[m.start():m.start() + 2000]

    # Check for the byMachine grouping line
    group_m = re.search(r"byMachine\s*\[\s*e\.machine\s*\]", body)
    if group_m:
        # Found raw machine name as key — check if there's a trim/normalize nearby
        surrounding = body[max(0, group_m.start() - 100):group_m.end() + 100]
        has_normalization = bool(re.search(r"\.trim\(\)|\.toLowerCase\(\)|\.toUpperCase\(\)", surrounding))
        if not has_normalization:
            return [{"check": "mtbf_machine_normalization", "page": page,
                     "reason": (f"{page} loadMtbf() groups by raw e.machine string without normalization — "
                                f"'PUMP A', 'pump a', and 'Pump A' become 3 separate MTBF groups, each with "
                                f"1 failure (below the 2-failure minimum), silently excluded from all MTBF; "
                                f"change to: const key = (e.machine || '').trim(); byMachine[key] = ...")}]
    return []


# ── Layer 2: Breakdown entry data completeness ────────────────────────────────

def check_breakdown_consequence_required(page):
    """
    When maintenance_type is 'Breakdown / Corrective', failure_consequence
    must be required before the entry can be saved. Without enforcement:
    - Workers skip it (it's extra effort)
    - RCM Consequence Analysis (Diagnostic phase) has 0% data to work with
    - The AI assistant cannot answer "what is the most common consequence of failure?"

    The consequence section is correctly shown for Breakdown entries, but the
    save function never validates that it is non-null for that maintenance type.
    Required fix: add a guard like:
      if (maintType.includes('Breakdown') && !failureConsequence) {
        showToast('Please select a failure consequence for Breakdown entries.');
        return;
      }
    Reported as WARN — functional but RCM analysis has no data without it.
    """
    content = read_file(page)
    if content is None:
        return []

    # Check if the save function validates failure_consequence for Breakdown
    save_m = re.search(r"async function saveEntry\s*\(|const failureConsequence", content)
    if not save_m:
        return []

    # Get the save function area (look for the region around failureConsequence + maintType)
    consequence_m = re.search(r"failureConsequence\s*=\s*document\.getElementById", content)
    if not consequence_m:
        return []

    # Look for a guard requiring consequence on breakdown (within 200 lines)
    save_block = content[consequence_m.start():consequence_m.start() + 3000]
    has_guard = bool(re.search(
        r"if\s*\([^)]*Breakdown[^)]*failureConsequence|if\s*\([^)]*failureConsequence[^)]*Breakdown"
        r"|Breakdown.*consequence.*required|consequence.*null.*Breakdown",
        save_block, re.IGNORECASE
    ))
    if not has_guard:
        return [{"check": "breakdown_consequence_required", "page": page,
                 "skip": True,
                 "reason": (f"{page} save function does not require failure_consequence for Breakdown entries — "
                            f"workers skip it, RCM Consequence Analysis has 0%% adoption; "
                            f"add: if (maintType.includes('Breakdown') && !failureConsequence) {{ return; }}")}]
    return []


def check_category_required_on_save(page):
    """
    The category field is shown in the save form but the save function does not
    validate it as required. A null category means the logbook entry:
    - Cannot be grouped in Pareto failure distribution charts
    - Cannot be filtered in RAG semantic search by discipline
    - Is excluded from category-based PM correlation analysis

    The fix: add `if (!category) { showToast('Please select a category'); return; }`
    to the save function after the machine name check.
    Reported as WARN — functional but degrades analytics and RAG quality.
    """
    content = read_file(page)
    if content is None:
        return []

    # Find the category validation in the save function
    # Look for !category guard near the machine guard
    machine_guard_m = re.search(r"if\s*\(\s*!machine\s*\)", content)
    if not machine_guard_m:
        return []

    # Check the save function area for a category guard
    save_area = content[machine_guard_m.start():machine_guard_m.start() + 1000]
    has_category_guard = bool(re.search(
        r"if\s*\(\s*!category\s*\)|category.*required|!category.*return",
        save_area, re.IGNORECASE
    ))
    if not has_category_guard:
        return [{"check": "category_required_on_save", "page": page,
                 "skip": True,
                 "reason": (f"{page} save function does not validate category as required — "
                            f"null category entries cannot be grouped in Pareto analysis or "
                            f"filtered in RAG semantic search; add category validation after machine check")}]
    return []


# ── Layer 3: Canonical label consistency ─────────────────────────────────────

def check_canonical_maint_type_consistency(page, canonical_types):
    """
    Both the add form (<select id="f-maint-type">) and the edit form (JS array
    in the template literal) must use identical maintenance_type values.
    A mismatch means edited entries can have values the add form never produces,
    creating orphaned groups in MTBF and the Python analytics filter.
    """
    content = read_file(page)
    if content is None:
        return [{"check": "canonical_maint_type_consistency", "page": page,
                 "reason": f"{page} not found"}]

    # Find the edit form JS array — template literal pattern
    edit_m = re.search(r"(\[\s*'Breakdown[^]]+?\])\s*\.map\(t\s*=>", content)
    if not edit_m:
        return [{"check": "canonical_maint_type_consistency", "page": page,
                 "reason": f"{page} edit form maintenance_type array not found — cannot verify consistency"}]

    edit_types = re.findall(r"['\"]([^'\"]+)['\"]", edit_m.group(1))
    missing_from_edit = [t for t in canonical_types if t not in edit_types]
    extra_in_edit     = [t for t in edit_types if t not in canonical_types]

    issues = []
    for t in missing_from_edit:
        issues.append({"check": "canonical_maint_type_consistency", "page": page,
                       "reason": (f"{page} edit form missing maintenance_type value '{t}' — "
                                  f"entries with this type cannot be edited back to canonical value")})
    for t in extra_in_edit:
        issues.append({"check": "canonical_maint_type_consistency", "page": page,
                       "reason": (f"{page} edit form has extra maintenance_type '{t}' not in canonical list — "
                                  f"creates orphaned group in MTBF and analytics filters")})
    return issues


def check_canonical_consequence_values(page, canonical_values):
    """
    failure_consequence must only accept the 4 SAE JA1011 canonical values.
    Each consequence button's data-value attribute must match exactly.
    Any extra or renamed value silently breaks the RCM consequence distribution
    chart in the Diagnostic analytics phase.
    Regression guard — currently correct, will fail if someone adds a free-text input.
    """
    content = read_file(page)
    if content is None:
        return [{"check": "canonical_consequence_values", "page": page,
                 "reason": f"{page} not found"}]

    declared = re.findall(r'data-value=["\']([^"\']+)["\']', content)
    declared_consequences = [v for v in declared if any(
        kw in v.lower() for kw in ['hidden', 'running', 'safety', 'stopped', 'production']
    )]

    issues = []
    for val in declared_consequences:
        if val not in canonical_values:
            issues.append({"check": "canonical_consequence_values", "page": page,
                           "reason": (f"{page} non-canonical failure_consequence value '{val}' — "
                                      f"only {canonical_values} are valid SAE JA1011 consequence classes; "
                                      f"this value breaks RCM consequence distribution charts")})
    return issues


# ── Layer 4: Duplicate entry prevention ──────────────────────────────────────

def check_duplicate_entry_guard(page):
    """
    There is no UNIQUE constraint or pre-insert duplicate check on logbook entries.
    A worker who double-taps Save, or an enterprise system (SAP/Maximo) that retries
    a failed webhook, creates a duplicate logbook entry:
    - MTBF inflated: 1 failure looks like 2, halving the calculated MTBF
    - RAG knowledge base contains 2 identical embeddings — noise
    - PM compliance rate doubled for that day

    The fix options (either is sufficient):
    Option A: Add a DB UNIQUE constraint: UNIQUE(worker_name, machine, date::date)
    Option B: Add a pre-insert check in saveEntry():
      const today = new Date().toISOString().slice(0, 10);
      const { data: existing } = await db.from('logbook')
        .select('id').eq('worker_name', WORKER_NAME).eq('machine', machine)
        .gte('date', today + 'T00:00:00').lt('date', today + 'T23:59:59').maybeSingle();
      if (existing) { showToast('Entry already exists for this machine today.'); return; }
    Reported as WARN — duplicate entries are recoverable but degrade AI quality.
    """
    content = read_file(page)
    if content is None:
        return []

    # Check for a pre-insert duplicate detection pattern
    has_duplicate_check = bool(re.search(
        r"duplicate|already.*exist|same.*machine.*date|date.*machine.*exist"
        r"|\.maybeSingle.*machine.*date|worker_name.*machine.*gte.*date",
        content, re.IGNORECASE
    ))
    if not has_duplicate_check:
        return [{"check": "duplicate_entry_guard", "page": page, "skip": True,
                 "reason": (f"{page} has no duplicate entry detection before logbook insert — "
                            f"double-submit or SAP/Maximo retry creates duplicate entries: "
                            f"inflated MTBF, noisy RAG embeddings, inflated PM compliance; "
                            f"add pre-insert check: same worker + machine + date = block with toast")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "mtbf_machine_normalization",
    "breakdown_consequence_required",
    "category_required_on_save",
    "canonical_maint_type_consistency",
    "canonical_consequence_values",
    "duplicate_entry_guard",
]

CHECK_LABELS = {
    "mtbf_machine_normalization":       "L1  MTBF groups by normalized machine name (not raw string)",
    "breakdown_consequence_required":   "L2  Breakdown entries require failure_consequence on save  [WARN]",
    "category_required_on_save":        "L2  Category required on logbook save  [WARN]",
    "canonical_maint_type_consistency": "L3  Add form and edit form use identical maintenance_type values",
    "canonical_consequence_values":     "L3  failure_consequence only accepts 4 SAE JA1011 canonical values",
    "duplicate_entry_guard":            "L4  Logbook save checks for duplicate entry (same worker+machine+date)  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nData Quality Validator (4-layer)"))
    print("=" * 55)
    print("  Addresses: duplicate records, incomplete data, poor quality,")
    print("  unstructured chaos, inconsistent formats, data bias\n")

    all_issues = []
    all_issues += check_mtbf_machine_normalization(HIVE_PAGE)
    all_issues += check_breakdown_consequence_required(LOGBOOK_PAGE)
    all_issues += check_category_required_on_save(LOGBOOK_PAGE)
    all_issues += check_canonical_maint_type_consistency(LOGBOOK_PAGE, CANONICAL_MAINT_TYPES)
    all_issues += check_canonical_consequence_values(LOGBOOK_PAGE, CANONICAL_CONSEQUENCES)
    all_issues += check_duplicate_entry_guard(LOGBOOK_PAGE)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "data_quality",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("data_quality_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
