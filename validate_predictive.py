"""
Predictive Analytics Data Quality Validator — WorkHive Platform
================================================================
WorkHive computes MTBF (Mean Time Between Failures) and MTTR (Mean Time
to Repair) from logbook entries. These metrics are displayed on the Hive
Board and will power predictive failure alerts as the platform grows.

Garbage in = garbage out. A single logbook entry with downtime_hours=9999
or a machine name left blank corrupts every metric that machine appears in.
The predictive analytics skill says: data quality before models, rules
before ML.

From the Predictive Analytics skill file.

Four things checked:

  1. MTBF query has correct data quality guards
     — loadMtbf() must filter by maintenance_type='Breakdown / Corrective',
       and exclude entries with null or empty machine names. Without these
       filters, the MTBF calculation mixes PM completions and corrective work,
       and produces an 'Unknown' machine category from blank entries.

  2. MTBF skips machines with fewer than 2 failures
     — MTBF = average gap between failures. You need at least 2 failures
       to compute a gap. A machine that has failed exactly once has no
       meaningful MTBF — the only 'gap' would be measured from the first
       failure to now, which is not a historical pattern but elapsed time.
       The code must skip machines with timestamps.length < 2.

  3. MTTR filters out zero and negative repair times
     — If closed_at < created_at (data entry error), the repair time is
       negative. If downtime_hours = 0, the repair time is zero. Both
       corrupt the MTTR average and produce misleading analytics.
       The code must filter entries where repairMs <= 0.

  4. Downtime hours capped at maximum (data entry + analytics)
     — downtime_hours above 720 hours (30 days) are almost certainly
       data entry errors. Without a cap, a single entry with
       downtime_hours=9999 (~416 days) will dominate the MTTR average
       for that machine indefinitely.
       Checked at two levels:
       a. Data entry: logbook downtime input should have max="720"
       b. Analytics: MTTR calculation should filter/cap outlier values
       Reported as WARN — the > 0 filter provides partial protection.

Usage:  python validate_predictive.py
Output: predictive_report.json
"""
import re, json, sys

HIVE_PAGE    = "hive.html"
LOGBOOK_PAGE = "logbook.html"

MAX_DOWNTIME_HOURS = 720  # 30 days — beyond this is almost certainly an error


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_function_body(content, func_name, max_lines=80):
    """Extract the body of a named async function."""
    m = re.search(rf"async function\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        return None
    start = m.start()
    return "\n".join(content[start:start + max_lines * 80].splitlines()[:max_lines])


# ── Check 1: MTBF query has correct data quality guards ──────────────────────

def check_mtbf_filters(page):
    """
    The MTBF query must include three filters that prevent corrupted input:
    1. maintenance_type = 'Breakdown / Corrective' — only failures count
    2. machine is not null — blank machines go into an 'Unknown' bucket
    3. machine != '' — empty string machines also corrupt the grouping

    Without these, MTBF averages over all work types and blank machines
    show up as a noisy 'Unknown' entry that masks real failure patterns.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    body = extract_function_body(content, "loadMtbf")
    if not body:
        return [{"page": page, "reason": "loadMtbf() function not found"}]

    required_filters = [
        (
            r"maintenance_type.*Breakdown.*Corrective|eq\s*\(['\"]maintenance_type['\"]",
            "maintenance_type = 'Breakdown / Corrective' filter",
        ),
        (
            r"not\s*\(['\"]machine['\"],\s*['\"]is['\"]|not.*machine.*null",
            ".not('machine', 'is', null) filter",
        ),
        (
            r"neq\s*\(['\"]machine['\"]|neq.*machine.*''|machine.*neq",
            ".neq('machine', '') filter",
        ),
    ]

    for pattern, label in required_filters:
        if not re.search(pattern, body, re.IGNORECASE):
            issues.append({
                "page":   page,
                "filter": label,
                "reason": (
                    f"{page} loadMtbf() is missing '{label}' — "
                    f"MTBF will include wrong work types or blank machine entries, "
                    f"corrupting the failure frequency calculations"
                ),
            })
    return issues


# ── Check 2: MTBF skips machines with < 2 failures ───────────────────────────

def check_mtbf_minimum_count(page):
    """
    MTBF requires at least 2 failure timestamps to compute a gap.
    A machine with exactly 1 failure cannot have a meaningful MTBF.
    The code must skip such machines (if timestamps.length < 2: continue).
    """
    issues = []
    content = read_file(page)
    if content is None:
        return []

    body = extract_function_body(content, "loadMtbf")
    if not body:
        return []

    # Check for the < 2 gate
    has_min_check = bool(re.search(
        r"length\s*<\s*2|\.length\s*<\s*2|\bcount\s*<\s*2|timestamps\.length",
        body
    ))
    if not has_min_check:
        issues.append({
            "page": page,
            "reason": (
                f"{page} loadMtbf() does not skip machines with fewer than 2 "
                f"failures — MTBF for a machine with a single failure is "
                f"meaningless (there is no gap to average)"
            ),
        })
    return issues


# ── Check 3: MTTR filters zero and negative repair times ─────────────────────

def check_mttr_positive_filter(page):
    """
    MTTR must exclude entries where repairMs <= 0.
    These arise from:
    - Data entry errors: closed_at set before created_at (negative repair time)
    - Zero downtime: downtime_hours=0 with no timestamp gap (zero repair time)

    Including them makes the MTTR average artificially low and misleading.
    The filter(e => e.repairMs > 0) pattern handles both cases.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return []

    body = extract_function_body(content, "loadMttr")
    if not body:
        return [{"page": page, "reason": "loadMttr() function not found"}]

    has_positive_filter = bool(re.search(
        r"repairMs\s*>\s*0|repair.*>\s*0|filter.*>\s*0",
        body
    ))
    if not has_positive_filter:
        issues.append({
            "page": page,
            "reason": (
                f"{page} loadMttr() does not filter out zero or negative repair "
                f"times — data entry errors (closed_at before created_at) will "
                f"corrupt MTTR averages with negative values"
            ),
        })
    return issues


# ── Check 4: Downtime hours capped at maximum ────────────────────────────────

def check_downtime_cap(hive_page, logbook_page):
    """
    Downtime hours above 720 (30 days) are data entry errors.
    Without a cap, a single entry with downtime_hours=9999 (~416 days)
    will dominate the MTTR average for that machine indefinitely.

    Two checks:
    a. logbook.html downtime input should have max="720" or max="744"
    b. loadMttr() should filter/cap entries before averaging

    Reported as WARN because the repairMs > 0 filter provides partial
    protection (negative times removed), but extreme values are not capped.
    """
    issues = []

    # Check a: data entry max attribute
    logbook = read_file(logbook_page)
    if logbook:
        downtime_inputs = re.findall(
            r'<input[^>]+id=["\'](?:f-downtime|e-downtime)["\'][^>]*>',
            logbook, re.IGNORECASE | re.DOTALL
        )
        for inp in downtime_inputs:
            if "max=" not in inp:
                issues.append({
                    "page": logbook_page,
                    "reason": (
                        f"{logbook_page} downtime input has no max= attribute — "
                        f"workers can enter any value (e.g. 9999 hours = ~416 days) "
                        f"which will corrupt MTTR averages for that machine"
                    ),
                })
                break  # one report is enough

    # Check b: analytics cap in loadMttr
    hive = read_file(hive_page)
    if hive:
        body = extract_function_body(hive, "loadMttr")
        if body:
            has_cap = bool(re.search(
                rf"downtime_hours\s*<=\s*{MAX_DOWNTIME_HOURS}"
                rf"|downtime_hours\s*<\s*{MAX_DOWNTIME_HOURS + 1}"
                rf"|Math\.min.*downtime_hours|downtime_hours.*Math\.min",
                body
            ))
            if not has_cap:
                issues.append({
                    "page": hive_page,
                    "reason": (
                        f"{hive_page} loadMttr() does not cap downtime_hours at "
                        f"{MAX_DOWNTIME_HOURS}h — an outlier entry (e.g. 9999h) "
                        f"will dominate the MTTR average for that machine"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Predictive Analytics Data Quality Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] MTBF query has correct data quality guards (maintenance_type, machine)",
        check_mtbf_filters(HIVE_PAGE),
        "FAIL",
    ),
    (
        "[2] MTBF skips machines with fewer than 2 failure events",
        check_mtbf_minimum_count(HIVE_PAGE),
        "FAIL",
    ),
    (
        "[3] MTTR filters out zero and negative repair times",
        check_mttr_positive_filter(HIVE_PAGE),
        "FAIL",
    ),
    (
        f"[4] Downtime hours capped at {MAX_DOWNTIME_HOURS}h (data entry + analytics)",
        check_downtime_cap(HIVE_PAGE, LOGBOOK_PAGE),
        "WARN",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("predictive_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved predictive_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll predictive analytics checks PASS (warnings are known technical debt).")
