"""
WorkHive Platform Guardian — Phase 3: Self-Learning
=====================================================
Extracts lessons from:
  1. WARNs in current validator reports (known gaps not yet resolved)
  2. Recent "Fix" commits in git log (bugs fixed = rules to codify)
  3. Cross-cutting patterns (bugs that appear across multiple pages/layers)

For each lesson:
  - Determines which skill file(s) should learn it
  - Checks if the rule is already documented (string search)
  - If new: appends to skill file under "## Auto-learned [date]"
  - Writes to lessons_report.json for human review

Usage:
  python learn.py              # learn from last run + last 20 commits
  python learn.py --dry-run    # show what would be written, don't write
  python learn.py --commits N  # look back N commits (default: 20)

Output:
  lessons_report.json          — all lessons extracted + action taken
"""
import re, json, os, sys, datetime, subprocess

SKILLS_ROOT = os.path.expanduser(r"C:\Users\ILBeronio\.claude\skills")
HEALTH_FILE = "platform_health.json"
DRY_RUN     = "--dry-run" in sys.argv
COMMIT_N    = 20
for a in sys.argv:
    if a.startswith("--commits"):
        try: COMMIT_N = int(a.split("=")[1])
        except: pass

# ── Skill file → validator/topic mapping ─────────────────────────────────────
# When a lesson is about topic X, write to these skill files.
SKILL_MAP = {
    "cross-page-flow":  "cross-page-flow-validator",
    "hive":             "hive-validator",
    "logbook":          "logbook-validator",
    "inventory":        "inventory-validator",
    "pm":               "pm-validator",
    "skillmatrix":      "skillmatrix-validator",
    "assistant":        "assistant-validator",
    "calc":             "engineering-calc-validator",
    "guardian":         "platform-guardian",
    # Cross-cutting skills
    "qa":               "qa-tester",
    "frontend":         "frontend",
    "devops":           "devops",
}

# Report files produced by each validator
REPORT_FILES = {
    "cross-page-flow": "cross_page_report.json",
    "hive":            "hive_report.json",
    "logbook":         "logbook_report.json",
    "inventory":       "inventory_report.json",
    "pm":              "pm_report.json",
    "skillmatrix":     "skillmatrix_report.json",
    "assistant":       "assistant_report.json",
    "calc-renderers":  "renderer_mismatch_report.json",
    "calc-bom-sow":    "bom_sow_mismatch_report.json",
}


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_skill(skill_id):
    path = os.path.join(SKILLS_ROOT, skill_id, "SKILL.md")
    if not os.path.exists(path):
        return None, path
    with open(path, encoding="utf-8") as f:
        return f.read(), path


def append_to_skill(skill_id, rule_md):
    content, path = read_skill(skill_id)
    if content is None:
        return False, f"Skill not found: {path}"
    # Check if rule already documented (avoid duplicates)
    # Use first 80 chars of rule as a fingerprint
    fingerprint = rule_md.strip()[:80]
    if fingerprint.lower() in content.lower():
        return False, "already documented"
    # Append under auto-learned section
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + rule_md)
    return True, f"Appended to {path}"


def write_autofix_rule(skill_id, rule_dict, dry_run=False):
    """
    Inserts an Auto-Fix Rule into the ## Auto-Fix Rules section of a skill file.
    These rules are read at runtime by autofix.py to build SkillRule recipes.
    Returns (written: bool, reason: str)
    """
    content, path = read_skill(skill_id)
    if content is None:
        return False, f"Skill not found: {path}"

    rule_id = rule_dict["id"]
    if f"### rule: {rule_id}" in content:
        return False, "rule already exists"

    rule_block = (
        f"\n### rule: {rule_id}\n"
        f"**file:** `{rule_dict['file']}`\n"
        f"**detect:** `{rule_dict['detect']}`\n"
        f"**replace:** `{rule_dict['replace']}`\n"
        f"**confidence:** {rule_dict['confidence']}\n"
        f"**description:** {rule_dict['description']}\n"
    )

    if dry_run:
        return True, f"DRY: would write rule '{rule_id}' to {path}"

    section_header = "## Auto-Fix Rules"
    if section_header not in content:
        intro = "\n---\n\n## Auto-Fix Rules\n<!-- Read by autofix.py — keep ### rule: format -->\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(intro + rule_block)
    else:
        idx = content.index(section_header) + len(section_header)
        nxt = re.search(r"\n## ", content[idx:])
        if nxt:
            ins = idx + nxt.start()
            new_content = content[:ins] + "\n" + rule_block + content[ins:]
        else:
            new_content = content + "\n" + rule_block
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_content)

    return True, f"Wrote rule '{rule_id}' to {path}"


def git_log(n):
    try:
        r = subprocess.run(
            ["git", "log", f"--oneline", f"-{n}"],
            capture_output=True, text=True
        )
        return r.stdout.strip().splitlines()
    except Exception:
        return []


def git_show_stat(commit_hash):
    try:
        r = subprocess.run(
            ["git", "show", "--stat", "--format=%s", commit_hash],
            capture_output=True, text=True
        )
        return r.stdout.strip()
    except Exception:
        return ""


# ── Extract lessons ───────────────────────────────────────────────────────────

def lessons_from_warns(report_id, report_data):
    """Extract WARNs from a validator report as learnable lessons."""
    lessons = []
    if not report_data or not isinstance(report_data, dict):
        return lessons

    # Walk the report dict looking for WARN patterns
    report_str = json.dumps(report_data, indent=2)
    warn_sections = re.findall(
        r'"reason"\s*:\s*"([^"]{20,})"',
        report_str
    )
    for reason in warn_sections:
        if any(w in reason.lower() for w in ["missing", "not in", "broken", "wrong", "fail"]):
            lessons.append({
                "source":   f"validator:{report_id}",
                "type":     "warn",
                "finding":  reason,
                "skill":    SKILL_MAP.get(report_id, report_id),
            })
    return lessons[:5]  # cap per validator


def lessons_from_commits(lines):
    """Extract bug fix patterns from git commit messages."""
    lessons = []
    fix_pattern = re.compile(r"^([a-f0-9]{7})\s+Fix\s+(.*)", re.IGNORECASE)

    for line in lines:
        m = fix_pattern.match(line.strip())
        if not m:
            continue
        commit_hash = m.group(1)
        message     = m.group(2).strip()

        # Determine which skill(s) this fix teaches
        skills = []
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["logbook", "logcat", "log_cat", "closed_at", "parts used"]):
            skills.append("logbook-validator")
        if any(w in msg_lower for w in ["pm_cat", "pm category", "pm scheduler", "freq_days"]):
            skills.append("pm-validator")
        if any(w in msg_lower for w in ["cross-page", "inventory_transactions", "qty_after", "pm_completions"]):
            skills.append("cross-page-flow-validator")
        if any(w in msg_lower for w in ["renderer", "alias", "r.field", "undefined", "calc", "python api"]):
            skills.append("engineering-calc-validator")
        if any(w in msg_lower for w in ["hive", "realtime", "channel", "approval"]):
            skills.append("hive-validator")
        if any(w in msg_lower for w in ["assistant", "platform tools", "discipline", "skill matrix"]):
            skills.append("assistant-validator")
        if any(w in msg_lower for w in ["floating-ai", "nav-hub", "utils.js"]):
            skills.append("qa-tester")
        if any(w in msg_lower for w in ["deploy", "render", "supabase", "netlify", "cache"]):
            skills.append("devops")

        if not skills:
            skills = ["platform-guardian"]  # catch-all

        lessons.append({
            "source":  f"git:{commit_hash}",
            "type":    "fix",
            "finding": message,
            "skills":  skills,
            "hash":    commit_hash,
        })
    return lessons


def lessons_from_health(health):
    """Extract overall platform health learnings."""
    lessons = []
    if not health:
        return lessons

    # Regressions are the most important lesson source
    for reg in health.get("regressions", []):
        lessons.append({
            "source":   "regression-detection",
            "type":     "regression",
            "finding":  f"Validator '{reg['label']}' regressed: was {reg['was']}, now {reg['now']}",
            "skills":   ["platform-guardian", "qa-tester"],
        })

    return lessons


# ── Format rule markdown ──────────────────────────────────────────────────────

def infer_rule(finding):
    """Generate a specific rule from a finding description."""
    f = finding.lower()

    if "qty_after" in f:
        return "Every inventory_transactions INSERT must include qty_after (the balance after the change). Missing it breaks the running-balance display in inventory history."
    if "pm_cat_to_log_cat" in f or "logbook categories" in f:
        return "PM_CAT_TO_LOG_CAT values must match VALID_LOGBOOK_CATEGORIES exactly. Run validate_logbook.py after adding any new PM category."
    if "alias" in f and ("renderer" in f or "r." in f):
        return "When Python returns a field under a different name than the renderer reads, add a renderer alias in the Python return dict. Run validate_renderers.py to detect mismatches."
    if "n_actual" in f and "before" in f:
        return "Variables used in Python return values must be assigned before use. Variables computed from other derived values (like layout grid dimensions) must be computed first."
    if "platform tools" in f and "missing" in f:
        return "Every live tool page must appear in the PLATFORM TOOLS section of the floating AI system prompt. Run validate_assistant.py when adding a new page."
    if "discipline" in f and ("wrong" in f or "hvac" in f or "civil" in f):
        return "AI system prompt discipline names must match the actual DISCIPLINES array in skill-content.js. Run validate_assistant.py after updating skill-content.js."
    if "total_connected_kva" in f or "alias" in f and "load schedule" in f:
        return "Load Schedule renderer reads lowercase field names (total_connected_kva) but Python returns PascalCase (total_connected_kW). Add lowercase aliases in the Python return dict."
    if "print" in f and ("header" in f or "footer" in f or "popup" in f):
        return "Print styling must suppress browser headers/footers. Use the popup window pattern with explicit page-break CSS for clean PDFs."
    if "calendar period" in f or "rolling window" in f:
        return "Analytics date ranges must use calendar periods (this month, last month) rather than rolling windows to match shift handover expectations."
    if "analytics" in f or "rolling" in f:
        return "When computing analytics, verify whether the user expects calendar-aligned periods (MTBF this month) vs rolling windows. Calendar periods are almost always correct for maintenance reporting."
    if "cache" in f or "netlify" in f or "browser" in f:
        return "After deploying HTML changes, instruct users to hard-refresh (Ctrl+Shift+R) before testing. Browser cache serves stale HTML even after Netlify deploys."
    if "render" in f and "deploy" in f:
        return "Render.com free-tier deploys take 2-3 minutes after git push. Verify with a direct curl call before running UI tests."

    # Generic fallback
    return f"Review this fix and add a specific rule: {finding[:100]}"


def infer_autofix(finding):
    """
    Returns a rule dict if the finding maps to a deterministic string-replace fix,
    else None. These dicts are written to SKILL.md ## Auto-Fix Rules sections
    so that autofix.py can read and apply them at runtime.
    """
    f = finding.lower()

    if "qty_after" in f and ("inventory_transactions" in f or "logbook" in f):
        return {
            "id":          "qty-after-logbook",
            "file":        "logbook.html",
            "detect":      "qty_change: -p.qty, type: 'use',",
            "replace":     "qty_change: -p.qty, qty_after: newQty, type: 'use',",
            "confidence":  "HIGH",
            "description": "Missing qty_after in inventory_transactions inserts",
        }
    if ("pm_cat_to_log_cat" in f or "logbook categories" in f) and "hvac" in f:
        return {
            "id":          "pm-cat-hvac",
            "file":        "pm-scheduler.html",
            "detect":      "'HVAC': 'HVAC'",
            "replace":     "'HVAC': 'Mechanical'",
            "confidence":  "HIGH",
            "description": "PM_CAT_TO_LOG_CAT maps HVAC to invalid logbook category",
        }
    if "total_connected_kva" in f or ("alias" in f and "load schedule" in f):
        return {
            "id":          "load-schedule-kva-alias",
            "file":        "engineering-design.html",
            "detect":      "total_connected_kW,",
            "replace":     "total_connected_kva: r.total_connected_kW, total_connected_kW,",
            "confidence":  "MEDIUM",
            "description": "Load Schedule renderer missing lowercase alias for total_connected_kva",
        }
    return None


def format_rule(lesson, today, has_autofix=False):
    """Convert a lesson into a markdown rule block with an inferred rule."""
    src_label = {
        "warn":       "WARN from validator",
        "fix":        "Bug fix in git history",
        "regression": "Regression detected",
    }.get(lesson["type"], lesson["type"])

    rule_text    = infer_rule(lesson["finding"])
    autofix_note = (
        "\n**Auto-Fix:** Rule generated — `autofix.py` will apply this fix automatically."
        if has_autofix else ""
    )

    rule = f"""
---

## Auto-learned ({today})

**Source:** {src_label} — `{lesson.get('hash', lesson['source'])}`

**Finding:** {lesson['finding']}

**Rule:** {rule_text}{autofix_note}
"""
    return rule.strip()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today  = datetime.date.today().isoformat()
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    print("\n" + "=" * 70)
    print(f"  WorkHive Platform Guardian — Self-Learning")
    print(f"  {now_ts}  |  {'DRY RUN (no writes)' if DRY_RUN else 'WRITE mode'}")
    print("=" * 70)

    all_lessons  = []
    actions_taken = []

    # ── 1. WARNs from validator reports ────────────────────────────────────────
    print("\n[1] Scanning validator reports for WARNs and known gaps...\n")
    for report_id, report_file in REPORT_FILES.items():
        data = read_json(report_file)
        if not data:
            continue
        w = lessons_from_warns(report_id, data)
        if w:
            print(f"  Found {len(w)} finding(s) in {report_file}")
            all_lessons.extend(w)

    if not any(l["type"] == "warn" for l in all_lessons):
        print("  No WARNs found in current reports — all clean.")

    # ── 2. Fix commits from git log ────────────────────────────────────────────
    print(f"\n[2] Scanning last {COMMIT_N} git commits for bug fixes...\n")
    commits = git_log(COMMIT_N)
    fix_lessons = lessons_from_commits(commits)
    print(f"  Found {len(fix_lessons)} fix commit(s) to learn from")
    all_lessons.extend(fix_lessons)

    # ── 3. Platform health regressions ────────────────────────────────────────
    health = read_json(HEALTH_FILE)
    reg_lessons = lessons_from_health(health)
    if reg_lessons:
        print(f"\n[3] Found {len(reg_lessons)} regression(s) to learn from\n")
        all_lessons.extend(reg_lessons)

    # ── 4. Write lessons to skill files ───────────────────────────────────────
    print(f"\n[4] Writing lessons to skill files...\n")
    written  = 0
    skipped  = 0

    for lesson in all_lessons:
        skills       = lesson.get("skills") or [lesson.get("skill", "platform-guardian")]
        autofix_rule = infer_autofix(lesson["finding"])
        rule         = format_rule(lesson, today, has_autofix=autofix_rule is not None)

        for skill_id in skills:
            if DRY_RUN:
                print(f"  DRY  {skill_id}:")
                print(f"       {lesson['finding'][:80]}")
                if autofix_rule:
                    print(f"       + autofix rule: {autofix_rule['id']}")
                skipped += 1
            else:
                ok, reason = append_to_skill(skill_id, rule)
                if ok:
                    print(f"  WROTE  {skill_id}")
                    print(f"         {lesson['finding'][:80]}")
                    written += 1
                else:
                    if reason != "already documented":
                        print(f"  SKIP   {skill_id} ({reason})")
                    skipped += 1

                # Write autofix rule once, to the primary skill only
                if autofix_rule and skill_id == skills[0]:
                    af_ok, af_reason = write_autofix_rule(skill_id, autofix_rule, dry_run=False)
                    if af_ok:
                        print(f"  AUTOFIX  {skill_id}: rule '{autofix_rule['id']}' written")

        actions_taken.append({
            "lesson":       lesson["finding"][:120],
            "source":       lesson["source"],
            "skills":       skills,
            "written":      not DRY_RUN,
            "autofix_rule": autofix_rule["id"] if autofix_rule else None,
        })

    # ── Save report ────────────────────────────────────────────────────────────
    report = {
        "timestamp":     now_ts,
        "dry_run":       DRY_RUN,
        "total_lessons": len(all_lessons),
        "written":       written,
        "skipped":       skipped,
        "actions":       actions_taken,
    }
    with open("lessons_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"  {written} lessons written  |  {skipped} skipped (already known or dry-run)")
    print(f"  Saved lessons_report.json")
    if DRY_RUN:
        print(f"\n  Run without --dry-run to write to skill files.")
    else:
        print(f"\n  Review auto-learned sections in skill files.")
        print(f"  Remove or refine any rules that don't apply.\n")


if __name__ == "__main__":
    main()
