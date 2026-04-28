"""
Skill Matrix Validator — WorkHive Platform
==========================================
Four-layer validation of skillmatrix.html + skill-content.js:

  Layer 1 — Structure checks (JS config integrity)
    1.  DISCIPLINE_COLORS coverage     — every DISCIPLINES entry has a color
    2.  DISCIPLINE_ICONS coverage      — every DISCIPLINES entry has an SVG icon path
    3.  LEVEL_LABELS completeness      — exactly levels 1-5 defined
    4.  SKILL_CONTENT discipline cover — every discipline has content entries

  Layer 2 — Exam content integrity
    5.  All 25 exam arrays present     — 5 disciplines x 5 levels = 25 exams
    6.  Exam question count            — every exam has exactly 10 questions
    7.  Answer index validity          — every answer value is 0, 1, 2, or 3
    8.  Options count per question     — every question has exactly 4 options
    9.  All discipline+level complete  — every block has both module + exam keys

  Layer 3 — HTML logic rules
    10. Badge upsert conflict key      — onConflict includes 'level' not just discipline
    11. Cooldown on failure only       — cooldown gate checks passed===false
    12. Pass threshold defined         — score >= N with N between 1 and 9
    13. Auth gate present              — WORKER_NAME redirect to sign-in
    14. Draft cleanup in submitExam    — localStorage draft removed after submit

  Layer 4 — XSS / security
    15. escHtml on dynamic output      — user data and discipline names escaped in innerHTML

Usage:  python validate_skillmatrix.py
Output: skillmatrix_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, extract_js_array, extract_js_object_keys, format_result

SKILL_PAGE    = "skillmatrix.html"
CONTENT_FILE  = "skill-content.js"

EXPECTED_LEVELS      = {1, 2, 3, 4, 5}
EXPECTED_DISCIPLINES = None   # read from file
EXPECTED_EXAM_SIZE   = 10
EXPECTED_OPTIONS     = 4


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_numeric_object_keys(content, var_name):
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\{{([^}}]+)\}}",
        content, re.DOTALL
    )
    if not m:
        return set()
    return set(int(k) for k in re.findall(r'^\s*(\d+)\s*:', m.group(1), re.MULTILINE))


def extract_exam_blocks(content):
    """
    Walk the JS source and extract each exam array by bracket depth.
    Returns list of (char_offset, question_count, answer_values, options_counts).
    """
    results = []
    for m in re.finditer(r'\bexam\s*:\s*\[', content):
        start = m.end() - 1
        depth = 0
        i = start
        while i < len(content):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    block = content[start:i + 1]
                    # Count questions
                    q_count = len(re.findall(r'\bq\s*:', block))
                    # Extract answer values
                    answers = [int(a) for a in re.findall(r'\banswer\s*:\s*(\d+)', block)]
                    # Count options per question — handles escaped quotes e.g. contractor\'s
                    opts = []
                    for opt_m in re.finditer(r'\boptions\s*:\s*\[([^\]]*)\]', block):
                        # Match single-quoted strings that allow \' inside
                        opts.append(len(re.findall(r"'(?:[^'\\]|\\.)*'", opt_m.group(1))))
                    results.append((m.start(), q_count, answers, opts))
                    break
            i += 1
    return results


# ── Layer 1: Structure checks ─────────────────────────────────────────────────

def check_discipline_colors(content, page):
    disciplines = extract_js_array(content, "DISCIPLINES")
    color_keys  = extract_js_object_keys(content, "DISCIPLINE_COLORS")
    if not disciplines:
        return [{"check": "discipline_colors", "page": page,
                 "reason": "DISCIPLINES array not found in skill-content.js"}]
    issues = []
    for d in disciplines:
        if d not in color_keys:
            issues.append({"check": "discipline_colors", "page": page, "discipline": d,
                           "reason": f"'{d}' missing from DISCIPLINE_COLORS — discipline card renders without color"})
    return issues


def check_discipline_icons(content, page):
    disciplines = extract_js_array(content, "DISCIPLINES")
    icon_keys   = extract_js_object_keys(content, "DISCIPLINE_ICONS")
    if not disciplines:
        return []
    issues = []
    for d in disciplines:
        if d not in icon_keys:
            issues.append({"check": "discipline_icons", "page": page, "discipline": d,
                           "reason": f"'{d}' missing from DISCIPLINE_ICONS — discipline card renders without icon"})
    return issues


def check_level_labels(content, page):
    keys = extract_numeric_object_keys(content, "LEVEL_LABELS")
    if not keys:
        return [{"check": "level_labels", "page": page,
                 "reason": "LEVEL_LABELS not found — exam results show blank level names"}]
    issues = []
    missing = EXPECTED_LEVELS - keys
    extra   = keys - EXPECTED_LEVELS
    if missing:
        issues.append({"check": "level_labels", "page": page, "missing": sorted(missing),
                       "reason": f"LEVEL_LABELS missing levels {sorted(missing)}"})
    if extra:
        issues.append({"check": "level_labels", "page": page, "extra": sorted(extra),
                       "reason": f"LEVEL_LABELS has unexpected levels {sorted(extra)}"})
    return issues


def check_skill_content_coverage(content, page):
    disciplines = extract_js_array(content, "DISCIPLINES")
    if not disciplines:
        return [{"check": "skill_content_coverage", "page": page,
                 "reason": "DISCIPLINES array not found"}]
    issues = []
    for d in disciplines:
        if f"'{d}'" not in content and f'"{d}"' not in content:
            issues.append({"check": "skill_content_coverage", "page": page, "discipline": d,
                           "reason": f"SKILL_CONTENT has no entry for '{d}' — exam unavailable"})
    return issues


# ── Layer 2: Exam content integrity ──────────────────────────────────────────

def check_exam_count(content, page):
    disciplines = extract_js_array(content, "DISCIPLINES")
    n_disc      = len(disciplines) if disciplines else 5
    expected    = n_disc * len(EXPECTED_LEVELS)
    blocks      = extract_exam_blocks(content)
    actual      = len(blocks)
    if actual != expected:
        return [{"check": "exam_array_count", "page": page,
                 "expected": expected, "found": actual,
                 "reason": f"Expected {expected} exam arrays ({n_disc} disciplines x 5 levels), found {actual}"}]
    return []


def check_exam_question_counts(content, page):
    blocks = extract_exam_blocks(content)
    issues = []
    for idx, (offset, q_count, answers, opts) in enumerate(blocks):
        exam_num = idx + 1
        if q_count != EXPECTED_EXAM_SIZE:
            issues.append({"check": "exam_question_counts", "page": page,
                           "exam_index": exam_num, "found": q_count,
                           "reason": f"Exam #{exam_num}: has {q_count} questions, expected {EXPECTED_EXAM_SIZE} — exam score will be wrong"})
    return issues


def check_answer_index_valid(content, page):
    blocks = extract_exam_blocks(content)
    issues = []
    for idx, (offset, q_count, answers, opts) in enumerate(blocks):
        exam_num = idx + 1
        for q_idx, ans in enumerate(answers):
            if ans < 0 or ans >= EXPECTED_OPTIONS:
                issues.append({"check": "answer_index_valid", "page": page,
                               "exam_index": exam_num, "question": q_idx + 1, "answer_value": ans,
                               "reason": f"Exam #{exam_num} Q{q_idx+1}: answer={ans} is out of range 0-{EXPECTED_OPTIONS-1} — question has no correct answer"})
    return issues


def check_options_count(content, page):
    blocks = extract_exam_blocks(content)
    issues = []
    for idx, (offset, q_count, answers, opts) in enumerate(blocks):
        exam_num = idx + 1
        for q_idx, count in enumerate(opts):
            if count != EXPECTED_OPTIONS:
                issues.append({"check": "options_count", "page": page,
                               "exam_index": exam_num, "question": q_idx + 1, "found": count,
                               "reason": f"Exam #{exam_num} Q{q_idx+1}: has {count} options, expected {EXPECTED_OPTIONS}"})
    return issues


def check_all_levels_complete(content, page):
    """Every discipline+level block must have both 'module' and 'exam' keys."""
    disciplines = extract_js_array(content, "DISCIPLINES")
    if not disciplines:
        return []
    issues = []
    for disc in disciplines:
        # Find where this discipline's block starts in SKILL_CONTENT
        dm = re.search(rf"['\"]?{re.escape(disc)}['\"]?\s*:\s*\{{", content)
        if not dm:
            continue
        # Use bracket depth to find the full discipline block (may be 20000+ chars)
        start = dm.end() - 1
        depth = 0
        disc_end = start
        for i in range(start, min(start + 60000, len(content))):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    disc_end = i
                    break
        disc_block = content[start:disc_end]

        for level in sorted(EXPECTED_LEVELS):
            # Find each level key inside the discipline block
            lm = re.search(rf"(?<!\d){level}\s*:\s*\{{", disc_block)
            if not lm:
                issues.append({"check": "level_content_complete", "page": page,
                               "discipline": disc, "level": level,
                               "reason": f"'{disc}' level {level} block not found — exam unavailable"})
                continue
            # Extract the level block via bracket depth
            lstart = lm.end() - 1
            ldepth = 0
            lend = lstart
            for i in range(lstart, min(lstart + 20000, len(disc_block))):
                if disc_block[i] == '{':
                    ldepth += 1
                elif disc_block[i] == '}':
                    ldepth -= 1
                    if ldepth == 0:
                        lend = i
                        break
            level_block = disc_block[lstart:lend]
            if not re.search(r'\bmodule\s*:', level_block):
                issues.append({"check": "level_content_complete", "page": page,
                               "discipline": disc, "level": level,
                               "reason": f"'{disc}' level {level}: 'module' key missing — learning content unavailable"})
            if not re.search(r'\bexam\s*:', level_block):
                issues.append({"check": "level_content_complete", "page": page,
                               "discipline": disc, "level": level,
                               "reason": f"'{disc}' level {level}: 'exam' key missing — no exam questions"})
    return issues


# ── Layer 3: HTML logic rules ─────────────────────────────────────────────────

def check_badge_upsert_key(content, page):
    m = re.search(
        r"from\(['\"]skill_badges['\"]\)[\s\S]{0,600}?onConflict\s*:\s*['\"]([^'\"]+)['\"]",
        content, re.DOTALL
    )
    if not m:
        return [{"check": "badge_upsert_key", "page": page,
                 "reason": "skill_badges upsert onConflict key not found — duplicate badges may silently overwrite earned_at"}]
    key = m.group(1)
    if "level" not in key:
        return [{"check": "badge_upsert_key", "page": page, "found_key": key,
                 "reason": f"Badge upsert onConflict='{key}' missing 'level' — re-passing an exam overwrites original earned_at"}]
    return []


def check_cooldown_on_failure_only(content, page):
    m = re.search(r"cooldown\s*=\s*\d+\s*\*\s*\d+", content)
    if not m:
        return [{"check": "cooldown_on_failure", "page": page,
                 "reason": "Cooldown constant not found"}]
    start = max(0, m.start() - 300)
    block = content[start:m.end() + 100]
    if not re.search(r"!\s*\w+\.passed|passed\s*===?\s*false|!passed", block):
        return [{"check": "cooldown_on_failure", "page": page,
                 "reason": "Cooldown does not check passed===false — workers who passed must also wait before next level"}]
    return []


def check_pass_threshold(content, page):
    m = re.search(r"passed\s*=\s*score\s*>=\s*(\d+)", content)
    if not m:
        return [{"check": "pass_threshold", "page": page,
                 "reason": "Pass threshold (score >= N) not found in submitExam — exam pass/fail logic may be broken"}]
    n = int(m.group(1))
    if n <= 0:
        return [{"check": "pass_threshold", "page": page, "threshold": n,
                 "reason": f"Pass threshold is {n} — everyone passes automatically"}]
    if n >= 10:
        return [{"check": "pass_threshold", "page": page, "threshold": n,
                 "reason": f"Pass threshold is {n}/10 — perfect score required, may be too strict"}]
    return []


def check_auth_gate(content, page):
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)", content):
        return [{"check": "auth_gate", "page": page,
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users can access the page"}]
    return []


def check_draft_cleanup(content, page):
    submit_m = re.search(r"async\s+function\s+submitExam\s*\(", content)
    if not submit_m:
        return [{"check": "draft_cleanup", "page": page,
                 "reason": "submitExam() function not found"}]
    # Look for localStorage.removeItem in a window around submitExam
    window = content[submit_m.start():submit_m.start() + 2000]
    if "removeItem" not in window and "localStorage.removeItem" not in content:
        return [{"check": "draft_cleanup", "page": page,
                 "reason": "localStorage.removeItem(draftKey) not found after submitExam — draft answers persist after submission"}]
    return []


# ── Layer 4: XSS / security ───────────────────────────────────────────────────

def check_esc_html_on_dynamic(content, page):
    """
    Find innerHTML assignments that include DISCIPLINES-sourced values.
    Each must pass through escHtml() — direct disc insertion is XSS risk.
    """
    if "escHtml" not in content:
        return [{"check": "esc_html_dynamic", "page": page,
                 "reason": "escHtml function not found in skillmatrix.html — XSS protection missing"}]
    # Look for innerHTML = with disc or d variable without escHtml nearby
    raw_assigns = re.findall(r'innerHTML\s*=\s*[^;]{0,200}(?:disc|d\b)[^;]{0,200}', content, re.DOTALL)
    issues = []
    for assign in raw_assigns:
        if "escHtml" not in assign and "${disc}" in assign:
            issues.append({"check": "esc_html_dynamic", "page": page,
                           "snippet": assign[:80].strip(),
                           "reason": "innerHTML assignment uses ${disc} without escHtml — discipline names from DB could inject HTML"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1 — structure
    "discipline_colors", "discipline_icons", "level_labels", "skill_content_coverage",
    # L2 — exam content
    "exam_array_count", "exam_question_counts", "answer_index_valid",
    "options_count", "level_content_complete",
    # L3 — HTML logic
    "badge_upsert_key", "cooldown_on_failure", "pass_threshold",
    "auth_gate", "draft_cleanup",
    # L4 — XSS
    "esc_html_dynamic",
]

CHECK_LABELS = {
    # L1
    "discipline_colors":      "L1  DISCIPLINE_COLORS covers all DISCIPLINES",
    "discipline_icons":       "L1  DISCIPLINE_ICONS covers all DISCIPLINES",
    "level_labels":           "L1  LEVEL_LABELS has exactly levels 1-5",
    "skill_content_coverage": "L1  SKILL_CONTENT covers all disciplines",
    # L2
    "exam_array_count":       "L2  All 25 exam arrays present (5 x 5)",
    "exam_question_counts":   "L2  Every exam has exactly 10 questions",
    "answer_index_valid":     "L2  All answer indices are 0-3",
    "options_count":          "L2  Every question has exactly 4 options",
    "level_content_complete": "L2  All discipline+level blocks have module + exam",
    # L3
    "badge_upsert_key":       "L3  Badge upsert onConflict includes 'level'",
    "cooldown_on_failure":    "L3  Cooldown gate checks passed===false",
    "pass_threshold":         "L3  Pass threshold defined and reasonable (1-9)",
    "auth_gate":              "L3  WORKER_NAME auth gate present",
    "draft_cleanup":          "L3  Draft localStorage cleared after submitExam",
    # L4
    "esc_html_dynamic":       "L4  escHtml used on dynamic innerHTML",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSkill Matrix Validator (4-layer)"))
    print("=" * 55)

    sm      = read_file(SKILL_PAGE)
    content = read_file(CONTENT_FILE)

    if not sm:
        print(f"  ERROR: {SKILL_PAGE} not found")
        sys.exit(1)
    if not content:
        print(f"  ERROR: {CONTENT_FILE} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_discipline_colors(content, CONTENT_FILE)
    all_issues += check_discipline_icons(content, CONTENT_FILE)
    all_issues += check_level_labels(content, CONTENT_FILE)
    all_issues += check_skill_content_coverage(content, CONTENT_FILE)

    # L2
    all_issues += check_exam_count(content, CONTENT_FILE)
    all_issues += check_exam_question_counts(content, CONTENT_FILE)
    all_issues += check_answer_index_valid(content, CONTENT_FILE)
    all_issues += check_options_count(content, CONTENT_FILE)
    all_issues += check_all_levels_complete(content, CONTENT_FILE)

    # L3
    all_issues += check_badge_upsert_key(sm, SKILL_PAGE)
    all_issues += check_cooldown_on_failure_only(sm, SKILL_PAGE)
    all_issues += check_pass_threshold(sm, SKILL_PAGE)
    all_issues += check_auth_gate(sm, SKILL_PAGE)
    all_issues += check_draft_cleanup(sm, SKILL_PAGE)

    # L4
    all_issues += check_esc_html_on_dynamic(sm, SKILL_PAGE)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator": "skillmatrix",
        "total_checks": total,
        "passed": n_pass,
        "skipped": n_skip,
        "failed": n_fail,
        "issues": [i for i in all_issues if not i.get("skip")],
    }
    with open("skillmatrix_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
