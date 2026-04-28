"""
Data Governance Validator — WorkHive Platform
==============================================
Governance means: data belongs to someone, only the right people can
touch it, and nothing sensitive leaks where it shouldn't.

  Layer 1 — Data ownership
    1.  Owner tag on inserts       — worker_name in all worker-owned table inserts
    2.  Delete scope               — deletes filter by worker_name or hive_id  [WARN]

  Layer 2 — Sensitive data
    3.  AI widget prompt clean     — floating-ai.js system prompt free of PII/secrets
    4.  Assistant prompt clean     — assistant.html system prompt free of PII/secrets

  Layer 3 — Access control
    5.  Hive role gates (hive.html)  — approve/reject/kick check HIVE_ROLE
    6.  Hive role gates (pm-scheduler) — edit/delete PM assets check HIVE_ROLE

  Layer 4 — Scope
    7.  All write pages in scope   — skillmatrix and new pages included

Usage:  python validate_governance.py
Output: governance_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FLOAT_JS       = "floating-ai.js"
ASSISTANT_HTML = "assistant.html"

WORKER_OWNED_TABLES = ["logbook", "inventory_items", "assets", "pm_assets",
                       "skill_badges", "skill_profiles", "skill_exam_attempts"]

WRITE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "skillmatrix.html",
]

# Supervisor-only functions: (page, func_name, description)
PRIVILEGED_FUNCTIONS = [
    ("hive.html",         "kickMember",       "kick / remove hive member"),
    ("hive.html",         "approveItem",      "approve submitted item"),
    ("hive.html",         "rejectItem",       "reject submitted item"),
    ("pm-scheduler.html", "saveEditPMAsset",    "edit PM asset (supervisor only in hive)"),
    ("pm-scheduler.html", "confirmDeleteAsset", "delete PM asset — gated entry point must check HIVE_ROLE"),
]

# Sensitive patterns that must never appear in AI system prompts
SENSITIVE_PATTERNS = [
    (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "email address"),
    (r"\b(?:password|passwd)\s*[:=]\s*\S+",                  "password value"),
    (r"\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?\w{10,}",    "API key value"),
    (r"\+?[0-9]{7,15}\b",                                    "phone number"),
]


# ── Layer 1: Data ownership ───────────────────────────────────────────────────

def check_owner_tag(pages, tables):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            m = re.search(
                r"db\.from\(['\"](" + "|".join(re.escape(t) for t in tables) + r")['\"]"
                r"\)[^.]*\.(insert|upsert)\s*\(",
                line
            )
            if not m:
                continue
            table = m.group(1)
            window = "\n".join(lines[max(0, i - 20):min(len(lines), i + 10)])
            if "worker_name" not in window and "WORKER_NAME" not in window:
                issues.append({"check": "owner_tag", "page": page, "table": table, "line": i + 1,
                               "reason": f"{page}:{i+1} insert/upsert into '{table}' has no worker_name in surrounding 30 lines — orphaned data with no owner"})
    return issues


def check_delete_scope(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if ".delete()" not in line or "db.from(" not in line:
                continue
            window = "\n".join(lines[i:min(len(lines), i + 4)])
            if not any(k in window for k in ["worker_name", "hive_id", "WORKER_NAME", "HIVE_ID"]):
                issues.append({"check": "delete_scope", "page": page, "line": i + 1,
                               "skip": True,   # WARN — JS guards exist, RLS pending
                               "reason": f"{page}:{i+1} delete scoped only by 'id' — DB-level ownership boundary missing until RLS ships: `{line.strip()[:70]}`"})
    return issues


# ── Layer 2: Sensitive data ───────────────────────────────────────────────────

def _scan_prompt_for_sensitive(content, page, prompt_var="system"):
    """Extract a system prompt string and scan for PII/secrets."""
    if not content:
        return [{"check": "sensitive_prompt", "page": page, "reason": f"{page} not found"}]
    # Match: const system = `...` or const systemPrompt = `...`
    sys_m = re.search(rf"const {prompt_var}\s*=\s*`([\s\S]{{0,8000}}?)`", content)
    if not sys_m:
        return []
    prompt_text = sys_m.group(1)
    issues = []
    for pattern, label in SENSITIVE_PATTERNS:
        m = re.search(pattern, prompt_text, re.IGNORECASE)
        if m:
            issues.append({"check": "sensitive_prompt", "page": page, "found": label,
                           "reason": f"{page} system prompt contains a {label}: `{m.group(0)[:40]}` — appears in plain text in every AI API request"})
    return issues


def check_widget_prompt_clean(path):
    return _scan_prompt_for_sensitive(read_file(path), path, prompt_var="system")


def check_assistant_prompt_clean(path):
    content = read_file(path)
    if not content:
        return []
    # assistant.html uses const systemPrompt = `...` or buildSystemPrompt
    issues = []
    for var in ["systemPrompt", "system_prompt", "SYSTEM_PROMPT", "systemContext"]:
        found = _scan_prompt_for_sensitive(content, path, prompt_var=var)
        issues.extend(found)
    # Also scan any template literal that starts with a persona statement
    for m in re.finditer(r"You are WorkHive[\s\S]{0,5000}?`", content):
        block = m.group(0)
        for pattern, label in SENSITIVE_PATTERNS:
            sm = re.search(pattern, block, re.IGNORECASE)
            if sm:
                issues.append({"check": "sensitive_prompt", "page": path, "found": label,
                               "reason": f"{path} AI context block contains a {label}: `{sm.group(0)[:40]}`"})
        break   # only scan the first persona block
    return issues


# ── Layer 3: Access control ───────────────────────────────────────────────────

def check_role_gates(privileged_functions):
    issues = []
    for page, func_name, description in privileged_functions:
        content = read_file(page)
        if not content:
            continue
        func_m = re.search(rf"(?:async\s+)?function\s+{re.escape(func_name)}\s*\(", content)
        if not func_m:
            continue
        body = "\n".join(content[func_m.start():func_m.start() + 1500].splitlines()[:30])
        if "HIVE_ROLE" not in body:
            issues.append({"check": "role_gates", "page": page, "function": func_name,
                           "reason": f"{page} `{func_name}()` ({description}) has no HIVE_ROLE check — any worker can execute this supervisor action"})
    return issues


# ── Layer 4: Scope ────────────────────────────────────────────────────────────

def check_pages_in_scope():
    import glob, os
    live_set = set(WRITE_PAGES)
    issues   = []
    for path in glob.glob("*.html"):
        fname = os.path.basename(path)
        if fname in live_set:
            continue
        if any(s in fname for s in ["-test", ".backup", "platform-health", "guardian",
                                     "parts-tracker", "symbol-gallery", "architecture"]):
            continue
        content = read_file(fname)
        if not content:
            continue
        # Check if this page writes to a worker-owned table
        for table in WORKER_OWNED_TABLES:
            if re.search(rf"from\(['\"]({re.escape(table)})['\"].*?\.(insert|upsert)\s*\(", content):
                issues.append({"check": "pages_in_scope", "page": fname, "table": table,
                               "reason": f"{fname} writes to worker-owned table '{table}' but is not in WRITE_PAGES — owner_tag and delete_scope checks never run on it"})
                break
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "owner_tag", "delete_scope",
    # L2
    "widget_prompt_clean", "assistant_prompt_clean",
    # L3
    "role_gates",
    # L4
    "pages_in_scope",
]

CHECK_LABELS = {
    # L1
    "owner_tag":             "L1  worker_name in all worker-owned inserts",
    "delete_scope":          "L1  Deletes filter by worker_name or hive_id  [WARN]",
    # L2
    "widget_prompt_clean":   "L2  floating-ai.js prompt free of PII/secrets",
    "assistant_prompt_clean":"L2  assistant.html prompt free of PII/secrets",
    # L3
    "role_gates":            "L3  Privileged ops (hive + pm-scheduler) gated by HIVE_ROLE",
    # L4
    "pages_in_scope":        "L4  All worker-data-writing pages in WRITE_PAGES",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nData Governance Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_owner_tag(WRITE_PAGES, WORKER_OWNED_TABLES)
    all_issues += check_delete_scope(WRITE_PAGES)
    all_issues += check_widget_prompt_clean(FLOAT_JS)
    all_issues += check_assistant_prompt_clean(ASSISTANT_HTML)
    all_issues += check_role_gates(PRIVILEGED_FUNCTIONS)
    all_issues += check_pages_in_scope()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL — delete scope warnings are known (RLS pending)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "governance",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("governance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
