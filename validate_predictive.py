"""
Predictive Analytics Data Quality Validator — WorkHive Platform
================================================================
WorkHive computes MTBF and MTTR from logbook entries on the hive board
AND via the Python Analytics Engine. Garbage in = garbage out.

  Layer 1 — Query guards (hive board)
    1.  MTBF data quality filters  — maintenance_type, non-null machine
    2.  MTBF minimum count         — skip machines with < 2 failures
    3.  MTTR positive filter       — exclude zero and negative repair times

  Layer 2 — Cache integrity
    4.  Cache TTL check present    — MTBF/MTTR cache freshness validated (not just existence)

  Layer 3 — Analytics consistency
    5.  Corrective filter in Python — Python descriptive.py also uses 'Breakdown / Corrective'
    6.  Downtime cap               — data entry max attribute + analytics cap  [WARN]

Usage:  python validate_predictive.py
Output: predictive_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

HIVE_PAGE        = "hive.html"
LOGBOOK_PAGE     = "logbook.html"
DESCRIPTIVE_PY   = os.path.join("python-api", "analytics", "descriptive.py")
MAX_DOWNTIME_HOURS = 720


def extract_function_body(content, func_name, max_chars=8000):
    m = re.search(rf"async function\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        return None
    return content[m.start():m.start() + max_chars]


# ── Layer 1: Query guards ─────────────────────────────────────────────────────

def check_mtbf_filters(page):
    content = read_file(page)
    if not content:
        return [{"check": "mtbf_filters", "page": page, "reason": f"{page} not found"}]
    body = extract_function_body(content, "loadMtbf")
    if not body:
        return [{"check": "mtbf_filters", "page": page, "reason": "loadMtbf() not found"}]
    issues = []
    guards = [
        (r"maintenance_type.*Breakdown.*Corrective|eq\s*\(['\"]maintenance_type['\"]",
         "maintenance_type='Breakdown / Corrective' filter"),
        (r"not\s*\(['\"]machine['\"],\s*['\"]is['\"]|not.*machine.*null",
         ".not('machine', 'is', null) filter"),
        (r"neq\s*\(['\"]machine['\"]|neq.*machine.*''|machine.*neq",
         ".neq('machine', '') filter"),
    ]
    for pattern, label in guards:
        if not re.search(pattern, body, re.IGNORECASE):
            issues.append({"check": "mtbf_filters", "page": page,
                           "reason": f"{page} loadMtbf() missing '{label}' — MTBF includes wrong work types or blank machines"})
    return issues


def check_mtbf_minimum_count(page):
    content = read_file(page)
    if not content:
        return []
    body = extract_function_body(content, "loadMtbf")
    if not body:
        return []
    if not re.search(r"length\s*<\s*2|\.length\s*<\s*2|\bcount\s*<\s*2|timestamps\.length", body):
        return [{"check": "mtbf_min_count", "page": page,
                 "reason": f"{page} loadMtbf() does not skip machines with < 2 failures — MTBF for single-failure machines is meaningless"}]
    return []


def check_mttr_positive_filter(page):
    content = read_file(page)
    if not content:
        return []
    body = extract_function_body(content, "loadMttr")
    if not body:
        return [{"check": "mttr_positive_filter", "page": page, "reason": "loadMttr() not found"}]
    if not re.search(r"repairMs\s*>\s*0|repair.*>\s*0|filter.*>\s*0", body):
        return [{"check": "mttr_positive_filter", "page": page,
                 "reason": f"{page} loadMttr() does not filter zero/negative repair times — data errors corrupt MTTR averages"}]
    return []


# ── Layer 2: Cache integrity ──────────────────────────────────────────────────

def check_cache_ttl(page):
    """
    Both loadMtbf() and loadMttr() use a cache-first pattern reading from
    hive_analytics_cache. The cache validation must check freshness using
    computed_at (TTL check), not just the existence of data.
    If the TTL check is removed, workers see permanently stale metrics.
    """
    content = read_file(page)
    if not content:
        return []
    issues = []
    for fn in ("loadMttr", "loadMtbf"):
        body = extract_function_body(content, fn)
        if not body:
            continue
        if "hive_analytics_cache" not in body:
            continue   # this function doesn't use cache
        if not re.search(r"computed_at|TTL|CACHE_TTL|Date\.now.*cache|cache.*Date\.now", body):
            issues.append({"check": "cache_ttl", "page": page, "function": fn,
                           "reason": f"{page} {fn}() reads hive_analytics_cache but has no computed_at TTL check — workers see stale metrics indefinitely"})
    return issues


# ── Layer 3: Analytics consistency ───────────────────────────────────────────

def check_python_corrective_filter(path):
    """
    The Python descriptive analytics module must also use 'Breakdown / Corrective'
    (or the corrective_only() helper) to filter entries before computing MTBF/MTTR.
    Inconsistency between hive board JS and Python analytics means the same metric
    shows different values depending on which surface the worker uses.
    """
    content = read_file(path)
    if not content:
        return [{"check": "python_corrective_filter", "page": path,
                 "reason": f"{path} not found — Python descriptive analytics cannot be verified"}]
    if not re.search(r"Corrective|corrective_only|maintenance_type.*Corrective", content, re.IGNORECASE):
        return [{"check": "python_corrective_filter", "page": path,
                 "reason": f"{path} Python MTBF/MTTR calculation does not filter by 'Breakdown / Corrective' — differs from hive board JS calculation, causing inconsistent results"}]
    return []


def check_downtime_cap(hive_page, logbook_page):
    issues = []
    logbook = read_file(logbook_page)
    if logbook:
        inputs = re.findall(r'<input[^>]+id=["\'](?:f-downtime|e-downtime)["\'][^>]*>', logbook, re.IGNORECASE | re.DOTALL)
        for inp in inputs:
            if "max=" not in inp:
                issues.append({"check": "downtime_cap", "page": logbook_page,
                               "skip": True,   # WARN
                               "reason": f"{logbook_page} downtime input has no max= attribute — worker can enter 9999h, corrupting MTTR"})
                break
    hive = read_file(hive_page)
    if hive:
        body = extract_function_body(hive, "loadMttr")
        if body and not re.search(
            rf"downtime_hours\s*<=\s*{MAX_DOWNTIME_HOURS}"
            rf"|downtime_hours\s*<\s*{MAX_DOWNTIME_HOURS + 1}"
            rf"|Math\.min.*downtime_hours|downtime_hours.*Math\.min", body
        ):
            issues.append({"check": "downtime_cap", "page": hive_page,
                           "skip": True,   # WARN
                           "reason": f"{hive_page} loadMttr() does not cap downtime_hours at {MAX_DOWNTIME_HOURS}h — outlier entries dominate MTTR average"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "mtbf_filters", "mtbf_min_count", "mttr_positive_filter",
    # L2
    "cache_ttl",
    # L3
    "python_corrective_filter", "downtime_cap",
]

CHECK_LABELS = {
    # L1
    "mtbf_filters":             "L1  MTBF query: maintenance_type + non-null machine filters",
    "mtbf_min_count":           "L1  MTBF skips machines with < 2 failures",
    "mttr_positive_filter":     "L1  MTTR filters out zero and negative repair times",
    # L2
    "cache_ttl":                "L2  MTBF/MTTR cache freshness validated with computed_at TTL",
    # L3
    "python_corrective_filter": "L3  Python descriptive.py uses 'Breakdown / Corrective' filter",
    "downtime_cap":             "L3  Downtime hours capped at 720h (data entry + analytics)  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPredictive Analytics Data Quality Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_mtbf_filters(HIVE_PAGE)
    all_issues += check_mtbf_minimum_count(HIVE_PAGE)
    all_issues += check_mttr_positive_filter(HIVE_PAGE)
    all_issues += check_cache_ttl(HIVE_PAGE)
    all_issues += check_python_corrective_filter(DESCRIPTIVE_PY)
    all_issues += check_downtime_cap(HIVE_PAGE, LOGBOOK_PAGE)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL — downtime cap is known technical debt\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "predictive",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("predictive_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
