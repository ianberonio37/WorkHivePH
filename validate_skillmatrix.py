"""
Skill Matrix Validator — WorkHive Platform

Static analysis of skillmatrix.html + skill-content.js covering:

  1. DISCIPLINE_COLORS coverage — every DISCIPLINES entry has a color
  2. LEVEL_LABELS completeness — exactly levels 1-5 defined
  3. Badge upsert conflict key — uses (worker_name, discipline, level), not just (worker_name, discipline)
  4. Cooldown on failure only — cooldown gate checks passed=false, not all attempts
  5. Pass threshold defined  — score threshold present and > 0
  6. SKILL_CONTENT discipline coverage — every discipline has content entries

Usage:  python validate_skillmatrix.py
Output: skillmatrix_report.json
"""
import re, json, sys

SKILL_PAGE    = "skillmatrix.html"
CONTENT_FILE  = "skill-content.js"

EXPECTED_LEVELS = {1, 2, 3, 4, 5}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_array(content, var_name):
    """Extract string values from a JS array: const NAME = ['a', 'b', ...]"""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\[([^\]]+)\]",
        content, re.DOTALL
    )
    if not m:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))


def extract_object_keys(content, var_name):
    """Extract top-level keys from a JS object: const NAME = { 'k1': ..., 'k2': ... }"""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\{{",
        content
    )
    if not m:
        return set()
    start = m.end() - 1
    depth = 0
    for i in range(start, min(start + 5000, len(content))):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                block = content[start + 1:i]
                return set(re.findall(r"^\s*['\"]?(\w[^'\":]*?)['\"]?\s*:", block, re.MULTILINE))
    return set()


def extract_numeric_object_keys(content, var_name):
    """Extract numeric keys from LEVEL_LABELS = { 1: '...', 2: '...' }"""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\{{([^}}]+)\}}",
        content, re.DOTALL
    )
    if not m:
        return set()
    block = m.group(1)
    return set(int(k) for k in re.findall(r'^\s*(\d+)\s*:', block, re.MULTILINE))


# ── Check 1: DISCIPLINE_COLORS covers all DISCIPLINES ─────────────────────────
def check_discipline_colors(content, page):
    issues = []
    disciplines  = extract_array(content, "DISCIPLINES")
    color_keys   = extract_object_keys(content, "DISCIPLINE_COLORS")

    if not disciplines:
        return [{"page": page, "reason": "DISCIPLINES array not found in skill-content.js"}]

    for disc in disciplines:
        if disc not in color_keys:
            issues.append({
                "page": page, "discipline": disc,
                "reason": f"'{disc}' has no entry in DISCIPLINE_COLORS — discipline card will render without color",
            })
    return issues


# ── Check 2: LEVEL_LABELS has exactly levels 1-5 ─────────────────────────────
def check_level_labels(content, page):
    issues = []
    keys = extract_numeric_object_keys(content, "LEVEL_LABELS")
    if not keys:
        return [{"page": page, "reason": "LEVEL_LABELS not found in skill-content.js"}]

    missing  = EXPECTED_LEVELS - keys
    extra    = keys - EXPECTED_LEVELS

    if missing:
        issues.append({
            "page": page, "missing_levels": sorted(missing),
            "reason": f"LEVEL_LABELS missing levels {sorted(missing)} — exam results for those levels will show blank label",
        })
    if extra:
        issues.append({
            "page": page, "extra_levels": sorted(extra),
            "reason": f"LEVEL_LABELS has unexpected levels {sorted(extra)} — may indicate a level numbering change",
        })
    return issues


# ── Check 3: Badge upsert conflict key includes level ────────────────────────
def check_badge_upsert_key(content, page):
    """
    skill_badges upsert must use onConflict: 'worker_name,discipline,level'.
    Specifically look at the skill_badges upsert block (not skill_profiles).
    """
    issues = []
    # Find skill_badges upsert block and its onConflict value
    m = re.search(
        r"from\(['\"]skill_badges['\"]\)[\s\S]{0,600}?onConflict\s*:\s*['\"]([^'\"]+)['\"]",
        content, re.DOTALL
    )
    if not m:
        issues.append({
            "page": page,
            "reason": "skill_badges upsert onConflict key not found — duplicate badges may silently overwrite earned_at",
        })
        return issues

    key = m.group(1)
    if "level" not in key:
        issues.append({
            "page": page, "found_key": key,
            "reason": f"Badge upsert onConflict='{key}' is missing 'level' — re-passing an exam overwrites the original earned_at for that (worker, discipline) pair",
        })
    return issues


# ── Check 4: Cooldown applied only on failed attempts ─────────────────────────
def check_cooldown_on_failure_only(content, page):
    """
    Cooldown must check lastAttempt.passed === false before enforcing the wait.
    If the check is missing, workers who passed must also wait before the next level.
    """
    issues = []
    # Look for the cooldown block; it should reference 'passed' being false
    cooldown_block_m = re.search(r"cooldown\s*=\s*\d+\s*\*\s*\d+", content)
    if not cooldown_block_m:
        return [{"page": page, "reason": "Cooldown constant not found"}]

    # Extract context around cooldown
    start = max(0, cooldown_block_m.start() - 300)
    block = content[start:cooldown_block_m.end() + 100]

    has_passed_check = bool(re.search(
        r"!\s*\w+\.passed|passed\s*===\s*false|passed\s*==\s*false|!passed",
        block
    ))
    if not has_passed_check:
        issues.append({
            "page": page,
            "reason": "Cooldown enforcement does not check passed===false — workers who passed must also wait before taking the next level exam",
        })
    return issues


# ── Check 5: Pass threshold defined and reasonable ───────────────────────────
def check_pass_threshold(content, page):
    issues = []
    # Look for: const passed = score >= N  or  score >= N  in submit context
    m = re.search(r"passed\s*=\s*score\s*>=\s*(\d+)", content)
    if not m:
        issues.append({
            "page": page,
            "reason": "Pass threshold (score >= N) not found in submitExam() — exam pass/fail logic may be broken",
        })
        return issues

    threshold = int(m.group(1))
    if threshold <= 0:
        issues.append({
            "page": page, "threshold": threshold,
            "reason": f"Pass threshold is {threshold} — everyone passes automatically",
        })
    elif threshold >= 10:
        issues.append({
            "page": page, "threshold": threshold,
            "reason": f"Pass threshold is {threshold}/10 — perfect score required, may be too strict",
        })
    return issues


# ── Check 6: SKILL_CONTENT has all disciplines ────────────────────────────────
def check_skill_content_coverage(content, skill_content_file, page):
    """
    SKILL_CONTENT must have an entry for every discipline in DISCIPLINES.
    Missing discipline = exam questions unavailable for that discipline.
    """
    issues = []
    disciplines = extract_array(content, "DISCIPLINES")
    if not disciplines:
        return [{"page": page, "reason": "DISCIPLINES array not found"}]

    sc_content = read_file(skill_content_file)
    if not sc_content:
        return [{"page": skill_content_file, "reason": f"{skill_content_file} not found"}]

    # SKILL_CONTENT is a large nested object; use string search instead of key extraction
    for disc in disciplines:
        if f"'{disc}'" not in sc_content and f'"{disc}"' not in sc_content:
            issues.append({
                "page": skill_content_file, "discipline": disc,
                "reason": f"SKILL_CONTENT has no entry for '{disc}' — exam and learning content unavailable for this discipline",
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Skill Matrix Validator")
print("=" * 70)

sm_content      = read_file(SKILL_PAGE)
content_content = read_file(CONTENT_FILE)

if not sm_content:
    print(f"ERROR: {SKILL_PAGE} not found")
    sys.exit(1)
if not content_content:
    print(f"ERROR: {CONTENT_FILE} not found")
    sys.exit(1)

# Merge both files for checks that span both
combined = sm_content + "\n" + content_content

fail_count = 0
warn_count = 0
report     = {}

checks = [
    ("[1] DISCIPLINE_COLORS covers all DISCIPLINES",  check_discipline_colors(content_content, CONTENT_FILE)),
    ("[2] LEVEL_LABELS has exactly levels 1-5",       check_level_labels(content_content, CONTENT_FILE)),
    ("[3] Badge upsert conflict key includes level",  check_badge_upsert_key(sm_content, SKILL_PAGE)),
    ("[4] Cooldown on failed attempts only",          check_cooldown_on_failure_only(sm_content, SKILL_PAGE)),
    ("[5] Pass threshold defined and reasonable",     check_pass_threshold(sm_content, SKILL_PAGE)),
    ("[6] SKILL_CONTENT covers all disciplines",      check_skill_content_coverage(content_content, CONTENT_FILE, CONTENT_FILE)),
]

for label, issues in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  FAIL  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
            fail_count += 1
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("skillmatrix_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved skillmatrix_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll skill matrix checks PASS.")
