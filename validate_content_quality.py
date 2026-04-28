"""
Content Quality Validator — WorkHive Platform
==============================================
This validator closes the remaining data quality gaps identified from the
"Top 20 Data Problems That Break AI Systems":

  Layer 1 — Embedding content guard                        [Problem 01]
    1.  embed-entry must refuse near-empty entries — a logbook row with
        only category set produces text "Category: Electrical" (22 chars),
        which is embedded as a near-zero vector with no diagnostic value.
        These entries pollute the fault knowledge base and return as false
        positives in semantic search.

  Layer 2 — Fault knowledge type filtering                 [Problem 16]
    2.  embed-entry inserts ALL maintenance types into fault_knowledge —
        Preventive Maintenance, Inspection, and Project Work entries all
        become part of the failure knowledge base. When the AI answers
        "what's our most common failure?", it draws from PM completions
        too. Only Breakdown / Corrective entries belong in fault_knowledge.

  Layer 3 — MTBF filter consistency between surfaces       [Problem 04, 16]
    3.  hive.html uses exact string match:  .eq('maintenance_type', 'Breakdown / Corrective')
        Python descriptive.py uses:          str.contains("Corrective|Breakdown", case=False)
        These are NOT equivalent — a typo entry "Breakdown/Corrective" (no spaces)
        is caught by Python but missed by hive.html, producing different MTBF
        values from the same dataset. Both surfaces must agree on the same filter.

  Layer 4 — New logbook fields in Python analytics         [Problem 04]
    4.  failure_consequence was added to the logbook schema (Apr 2026) but
        Python descriptive.py never reads it. The Diagnostic analytics phase
        (RCM Consequence Analysis) has no data to work from — it would compute
        zero distribution across all consequence types.

  Layer 5 — New field column safety in Python              [Problem 04]
    5.  Python analytics accesses new logbook fields (readings_json,
        production_output) using if-in-columns guards. failure_consequence
        must follow the same safe access pattern when added.

  Layer 6 — Python analytics and hive board agree on MTTR filter  [Problem 04, 16]
    6.  MTTR must filter out zero-downtime entries consistently. Python
        checks `downtime_hours not in df.columns` as a guard; hive.html
        uses .filter(e => e.repairMs > 0). Both must handle the same
        zero/null downtime edge case identically.

Usage:  python validate_content_quality.py
Output: content_quality_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

EMBED_ENTRY      = os.path.join("supabase", "functions", "embed-entry", "index.ts")
DESCRIPTIVE_PY   = os.path.join("python-api", "analytics", "descriptive.py")
HIVE_PAGE        = "hive.html"

# Minimum text length for a useful fault embedding (chars)
# "Category: Electrical" = 22 chars — too short for useful semantic retrieval
MIN_FAULT_TEXT_CHARS = 50

# The canonical maintenance_type value used for MTBF — both surfaces must agree
CANONICAL_BREAKDOWN_TYPE = "Breakdown / Corrective"


# ── Layer 1: Embedding content guard ─────────────────────────────────────────

def check_embed_content_guard(embed_path):
    """
    The embed-entry fault handler builds text from logbook fields using
    .filter(Boolean).join(). If most fields are null (common for brief
    PM entries), the text can be under 30 characters — meaningless for
    semantic retrieval.

    Without a minimum length check, embed-entry:
    1. Makes a Groq API call for a near-empty string (wastes tokens)
    2. Stores a near-zero vector in fault_knowledge
    3. This entry becomes a false positive: similarity search ranks it
       highly for ANY query because its cosine distance is near-1.0 with
       everything (zero vector matches nothing specifically)

    The fix:
      if (text.length < 50) {
        console.warn(`embed-entry: skipping near-empty fault entry (${text.length} chars)`);
        return new Response(JSON.stringify({ skipped: true, reason: 'insufficient_content' }), ...);
      }
    """
    content = read_file(embed_path)
    if content is None:
        return [{"check": "embed_content_guard", "source": embed_path,
                 "reason": f"{embed_path} not found"}]

    # Find the fault text construction block
    fault_m = re.search(r"type === ['\"]fault['\"]", content)
    if not fault_m:
        return []

    body = content[fault_m.start():fault_m.start() + 1000]

    # Check for minimum length guard on the constructed text
    has_length_guard = bool(re.search(
        r"text\.length|text\.trim\(\)\.length|insufficient|skip.*empty|min.*char|char.*min",
        body, re.IGNORECASE
    ))
    if not has_length_guard:
        return [{"check": "embed_content_guard", "source": embed_path,
                 "reason": (f"{embed_path} fault handler has no minimum content length guard — "
                            f"entries with only 1-2 fields populated produce text under 50 chars "
                            f"which embeds as a near-zero vector; add: "
                            f"if (text.length < {MIN_FAULT_TEXT_CHARS}) {{ return skip response }}")}]
    return []


# ── Layer 2: Fault knowledge type filtering ───────────────────────────────────

def check_fault_knowledge_type_filter(embed_path):
    """
    embed-entry inserts ALL logbook entries into fault_knowledge regardless
    of maintenance_type. This means:

    - "PM completed on Pump A — lubrication" → fault_knowledge ← wrong
    - "Pump A seized, replaced bearing" → fault_knowledge ← correct

    When the AI answers "what are our most common equipment failures?", it
    retrieves PM completion notes alongside actual breakdowns, making failure
    frequency analysis unreliable.

    The fix: only embed fault entries where maintenance_type includes "Breakdown"
    or "Corrective":
      if (entry.maintenance_type &&
          !entry.maintenance_type.includes('Breakdown') &&
          !entry.maintenance_type.includes('Corrective')) {
        return new Response(JSON.stringify({ skipped: true, reason: 'not_corrective' }), ...);
      }
    """
    content = read_file(embed_path)
    if content is None:
        return []

    fault_m = re.search(r"type === ['\"]fault['\"]", content)
    if not fault_m:
        return []

    body = content[fault_m.start():fault_m.start() + 1500]

    has_type_filter = bool(re.search(
        r"maintenance_type.*Breakdown|Breakdown.*maintenance_type"
        r"|Corrective.*maintenance_type|maintenance_type.*Corrective"
        r"|not_corrective|skip.*type|type.*skip",
        body, re.IGNORECASE
    ))
    if not has_type_filter:
        return [{"check": "fault_knowledge_type_filter", "source": embed_path,
                 "skip": True,
                 "reason": (f"{embed_path} embeds ALL logbook types into fault_knowledge — "
                            f"Preventive Maintenance, Inspection, and Project Work entries pollute "
                            f"the failure knowledge base; add a maintenance_type filter: "
                            f"only embed entries where maintenance_type includes 'Breakdown' or 'Corrective'")}]
    return []


# ── Layer 3: MTBF filter consistency ─────────────────────────────────────────

def check_mtbf_filter_consistency(hive_page, python_path):
    """
    hive.html uses:    .eq('maintenance_type', 'Breakdown / Corrective')
    Python uses:       str.contains("Corrective|Breakdown", case=False, na=False)

    These produce different results:
    - "Breakdown / Corrective" (canonical) → both match ✓
    - "Breakdown/Corrective" (missing spaces) → Python yes, hive.html no ✗
    - "Corrective Maintenance" → Python yes (contains "Corrective"), hive.html no ✗
    - "breakdown / corrective" (lowercase) → Python yes, hive.html no ✗

    A worker whose data has a typo in maintenance_type (e.g., copied from
    an older version) gets included in Python MTBF but excluded from the
    hive board MTBF — two different numbers for the same dataset.

    The fix: Python should use the same exact filter as hive.html:
      df[df["maintenance_type"] == "Breakdown / Corrective"]
    Or: hive.html should switch to case-insensitive contains to match Python.
    The important thing is they agree.
    """
    hive_content   = read_file(hive_page)
    python_content = read_file(python_path)

    if hive_content is None or python_content is None:
        return []

    # Check hive.html uses exact match
    hive_exact = bool(re.search(
        rf"\.eq\s*\(['\"]maintenance_type['\"],\s*['\"]Breakdown / Corrective['\"]",
        hive_content
    ))
    # Check Python uses case-insensitive contains
    python_contains = bool(re.search(
        r'str\.contains\(["\']Corrective\|Breakdown["\'],\s*case=False',
        python_content
    ))

    if hive_exact and python_contains:
        return [{"check": "mtbf_filter_consistency",
                 "skip": True,
                 "reason": (f"MTBF filter mismatch: {hive_page} uses exact .eq('maintenance_type', "
                            f"'Breakdown / Corrective') but {python_path} uses case-insensitive "
                            f"str.contains('Corrective|Breakdown') — typos or legacy entries "
                            f"appear in Python MTBF but not hive board MTBF; "
                            f"standardize to the same filter on both surfaces")}]
    return []


# ── Layer 4: New logbook fields in Python analytics ───────────────────────────

def check_failure_consequence_in_python(python_path):
    """
    failure_consequence was added to the logbook schema in April 2026
    (migration 20260428000000_logbook_failure_consequence.sql).

    Python descriptive.py computes RCM Consequence distribution for the
    Diagnostic analytics phase, but it does NOT read failure_consequence
    from the logbook data. The analytics orchestrator passes logbook records
    to Python, but descriptive.py ignores this field entirely.

    Result: the Diagnostic phase shows 0% consequence distribution across
    all 4 SAE JA1011 categories — an empty chart that looks like a bug
    to the supervisor, when actually the data exists but Python never reads it.

    The fix: add a consequence_distribution() function to descriptive.py
    that groups logbook Breakdown entries by failure_consequence and returns
    counts per category (Hidden, Running reduced, Safety risk, Stopped production).
    """
    content = read_file(python_path)
    if content is None:
        return [{"check": "failure_consequence_in_python", "source": python_path,
                 "reason": f"{python_path} not found"}]

    has_consequence = bool(re.search(
        r"failure_consequence|consequence_dist|consequence_analysis|rCM.*consequence",
        content, re.IGNORECASE
    ))
    if not has_consequence:
        return [{"check": "failure_consequence_in_python", "source": python_path,
                 "reason": (f"{python_path} does not read or compute failure_consequence — "
                            f"the Diagnostic analytics phase (RCM Consequence Analysis) has no data; "
                            f"add a consequence_distribution() function that groups Breakdown entries "
                            f"by failure_consequence and returns counts per SAE JA1011 category")}]
    return []


# ── Layer 5: New field column safety in Python ────────────────────────────────

def check_python_column_safety(python_path):
    """
    Python descriptive.py correctly guards most optional columns with
    if-in-columns checks (e.g., production_output, status, downtime_hours).
    But failure_consequence and readings_json access must follow the same
    pattern when they are added.

    Safe pattern (already used for other fields):
      if "failure_consequence" in df.columns:
          consequence = df["failure_consequence"]

    Unsafe pattern (KeyError if column not in data from older periods):
      consequence = df["failure_consequence"]  # KeyError on pre-Apr-2026 data

    This check verifies that any access to failure_consequence or
    readings_json in descriptive.py uses the column existence guard.
    """
    content = read_file(python_path)
    if content is None:
        return []

    # Only fails if these columns are accessed WITHOUT the safety guard
    for col in ("failure_consequence", "readings_json"):
        # Find any direct dict/df access to these columns
        direct_access = re.findall(
            rf'df\s*\[\s*["\']({re.escape(col)})["\']',
            content
        )
        if direct_access:
            # Check if there's a preceding column existence guard
            for m in re.finditer(
                rf'df\s*\[\s*["\']({re.escape(col)})["\']',
                content
            ):
                context = content[max(0, m.start() - 600):m.start()]
                if (f'"{col}" in df.columns' not in context
                        and f"'{col}' in df.columns" not in context
                        and f'"{col}" not in df.columns' not in context
                        and f"'{col}' not in df.columns" not in context):
                    line_no = content[:m.start()].count("\n") + 1
                    return [{"check": "python_column_safety", "source": python_path,
                             "reason": (f"{python_path}:{line_no} accesses df['{col}'] without "
                                        f"a preceding 'if \"{col}\" in df.columns' guard — "
                                        f"pre-April-2026 logbook data will raise KeyError when "
                                        f"this column is missing from the Supabase query result")}]
    return []


# ── Layer 6: MTTR zero-downtime filter consistency ───────────────────────────

def check_mttr_zero_filter_consistency(hive_page, python_path):
    """
    MTTR (Mean Time To Repair) must exclude zero and negative downtime values.
    Both surfaces must apply this filter consistently:

    hive.html:       .filter(e => e.repairMs > 0)
    Python:          guarded by `if "downtime_hours" not in df.columns` check
                     but does NOT explicitly filter df[downtime_hours] > 0
                     before computing mean — a 0-hour entry pulls MTTR down.

    Inconsistency: hive.html excludes zero-downtime entries from MTTR average,
    but Python includes them (0 hours averaged in). For an asset with 5
    failures: 4 hours, 6 hours, 8 hours, 0 hours, 2 hours —
    hive.html MTTR: (4+6+8+2)/4 = 5.0 hours
    Python MTTR:    (4+6+8+0+2)/5 = 4.0 hours — different answers from same data.
    """
    python_content = read_file(python_path)
    if python_content is None:
        return []

    # Find the MTTR function
    mttr_m = re.search(r"def.*mttr|mttr.*def|mean.*repair|repair.*mean", python_content, re.IGNORECASE)
    if not mttr_m:
        return []

    mttr_body = python_content[mttr_m.start():mttr_m.start() + 500]

    # Check if Python filters out zero downtime
    has_zero_filter = bool(re.search(
        r"downtime_hours.*>\s*0|> 0.*downtime|downtime.*positive|filter.*zero",
        mttr_body, re.IGNORECASE
    ))
    if not has_zero_filter:
        return [{"check": "mttr_zero_filter_consistency", "source": python_path,
                 "skip": True,
                 "reason": (f"{python_path} MTTR function does not filter out zero-downtime entries — "
                            f"hive.html uses .filter(e => e.repairMs > 0) but Python includes 0-hour entries; "
                            f"add: df = df[df['downtime_hours'] > 0] before computing MTTR mean to match "
                            f"hive board calculation")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "embed_content_guard",
    "fault_knowledge_type_filter",
    "mtbf_filter_consistency",
    "failure_consequence_in_python",
    "python_column_safety",
    "mttr_zero_filter_consistency",
]

CHECK_LABELS = {
    "embed_content_guard":            "L1  embed-entry rejects near-empty fault entries (< 50 chars)",
    "fault_knowledge_type_filter":    "L2  embed-entry only stores Breakdown entries in fault_knowledge  [WARN]",
    "mtbf_filter_consistency":        "L3  Python and hive board use identical MTBF maintenance_type filter  [WARN]",
    "failure_consequence_in_python":  "L4  Python descriptive.py reads and computes failure_consequence",
    "python_column_safety":           "L5  New logbook fields accessed with column existence guard in Python",
    "mttr_zero_filter_consistency":   "L6  Python MTTR excludes zero-downtime entries (matches hive board)  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nContent Quality Validator (6-layer)"))
    print("=" * 55)
    print("  Addresses: missing context, schema drift, poor labeling quality\n")

    all_issues = []
    all_issues += check_embed_content_guard(EMBED_ENTRY)
    all_issues += check_fault_knowledge_type_filter(EMBED_ENTRY)
    all_issues += check_mtbf_filter_consistency(HIVE_PAGE, DESCRIPTIVE_PY)
    all_issues += check_failure_consequence_in_python(DESCRIPTIVE_PY)
    all_issues += check_python_column_safety(DESCRIPTIVE_PY)
    all_issues += check_mttr_zero_filter_consistency(HIVE_PAGE, DESCRIPTIVE_PY)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "content_quality",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("content_quality_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
