"""
Tenant Boundary Escape Validator — WorkHive Platform
=====================================================
Multi-tenancy means Worker A cannot see Worker B's hive data.
The boundary is enforced in JavaScript (no RLS yet). Any query that
forgets the hive_id/worker_name filter exposes all tenants' data.

  Layer 1 — Query scope
    1.  SELECT queries filtered      — every .select() on shared tables has ownership filter
    2.  Realtime subscription scope  — channels on shared tables must have filter

  Layer 2 — Identity integrity
    3.  HIVE_ID from trusted source  — never from URLSearchParams or user input
    4.  WORKER_NAME from trusted source — never from URLSearchParams or user input

  Layer 3 — Membership validation
    5.  Hive switcher validates      — membership confirmed before writing HIVE_ID to localStorage
    6.  URL params not injected      — URL params not written to hive context

  Layer 4 — Scope
    7.  All tenant-aware pages checked — LIVE_PAGES covers analytics + all data pages

Usage:  python validate_tenant_boundary.py
Output: tenant_boundary_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "assistant.html",
    "community.html",
    "index.html",
]

SHARED_TABLES = [
    "logbook",
    "inventory_items",
    "inventory_transactions",
    "assets",
    "pm_assets",
    "pm_completions",
    "hive_members",
    "schedule_items",
    "skill_exam_attempts",
    "skill_badges",
    "community_xp",
]

USER_CONTROLLED = [
    r"URLSearchParams",
    r"location\.search",
    r"location\.hash",
    r"searchParams\.get\s*\(",
    r"\.value\b",
]

HIVE_LOCAL_KEYS = ["wh_hive_id", "wh_active_hive_id", "wh_hive_role", "wh_hive_name"]


# ── Layer 1: Query scope ──────────────────────────────────────────────────────

def check_select_filters(pages, tables):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table = next((t for t in tables
                          if f"from('{t}')" in line or f'from("{t}")' in line), None)
            if not table or ".select(" not in line:
                continue
            prev = lines[i - 1] if i > 0 else ""
            if re.search(r"\.(insert|upsert)\s*\(", line) or \
               re.search(r"\.(insert|upsert)\s*\(", prev):
                continue
            window = "\n".join(lines[i:min(len(lines), i + 8)])
            has_filter = any([
                "hive_id"     in window,
                "worker_name" in window,
                "WORKER_NAME" in window,
                "HIVE_ID"     in window,
                "auth_uid"    in window,   # C3: auth.uid() based scoping is valid
                "_authUid"    in window,   # C3: client-side auth session variable
                re.search(r'\.eq\s*\(["\']id["\']',        window),
                re.search(r'\.in\s*\(["\']id["\']',        window),
                re.search(r'\.in\s*\(["\']asset_id["\']',  window),
                re.search(r'\.in\s*\(["\']worker_name["\']', window),
            ])
            if not has_filter:
                issues.append({"check": "select_filters", "page": page, "table": table, "line": i + 1,
                               "reason": f"{page}:{i+1} .select() on '{table}' has no hive_id or worker_name filter in 8 lines — returns all tenants' rows"})
    return issues


def check_realtime_subscription_scope(pages, tables):
    """
    Realtime channel .on('postgres_changes', {...}) subscriptions on shared
    tables must include a filter like 'hive_id=eq.XXX' or 'worker_name=eq.XXX'.
    Without it, the client receives events from ALL tenants, potentially
    exposing other hives' logbook entries or inventory changes in real time.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        for m in re.finditer(
            r"\.on\s*\(['\"]postgres_changes['\"][^)]*table\s*:\s*['\"](\w+)['\"]",
            content
        ):
            table = m.group(1)
            if table not in tables:
                continue
            # Get the surrounding channel block (~200 chars after the .on call)
            block = content[m.start():m.start() + 300]
            has_filter = bool(re.search(
                r"filter\s*:\s*['\"](?:hive_id|worker_name)=eq\.",
                block
            ))
            if not has_filter:
                line = content[:m.start()].count("\n") + 1
                issues.append({"check": "realtime_scope", "page": page, "table": table, "line": line,
                               "reason": f"{page}:{line} Realtime subscription on '{table}' has no hive_id/worker_name filter — receives events from ALL tenants"})
    return issues


# ── Layer 2: Identity integrity ───────────────────────────────────────────────

def check_identity_source(pages, var_name, check_id):
    """
    Identity variables (HIVE_ID, WORKER_NAME) must only be assigned from
    trusted sources (localStorage, DB query results). Never from URL params.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if not re.search(rf"\b{re.escape(var_name)}\s*=\s*", line):
                continue
            for pattern in USER_CONTROLLED:
                if re.search(pattern, line):
                    issues.append({"check": check_id, "page": page, "line": i + 1,
                                   "reason": f"{page}:{i+1} {var_name} assigned from user-controlled input — attacker can impersonate any worker/hive: `{line.strip()[:70]}`"})
                    break
    return issues


# ── Layer 3: Membership validation ────────────────────────────────────────────

def check_switcher_validation(page):
    content = read_file(page)
    if not content:
        return [{"check": "switcher_validation", "page": page, "reason": f"{page} not found"}]
    m = re.search(r"async function\s+renderHiveSwitcher\s*\(", content)
    if not m:
        return []
    body = "\n".join(content[m.start():m.start() + 8000].splitlines()[:120])
    if "hive_members" not in body:
        return [{"check": "switcher_validation", "page": page,
                 "reason": f"{page} renderHiveSwitcher() does not query hive_members before switching — kicked members can re-enter via stale localStorage"}]
    if "kicked" not in body and "membership.status" not in body:
        return [{"check": "switcher_validation", "page": page,
                 "reason": f"{page} renderHiveSwitcher() queries hive_members but doesn't check membership.status — kicked members may still be admitted"}]
    return []


def check_url_param_injection(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if not re.search(r"searchParams\.get|URLSearchParams|location\.search|location\.hash", line):
                continue
            window = "\n".join(lines[i:min(len(lines), i + 10)])
            if any(k in window for k in HIVE_LOCAL_KEYS) or re.search(r"\bHIVE_ID\s*=", window):
                issues.append({"check": "url_param_injection", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} URL parameter read followed by hive context write — attacker can set hive context via URL: `{line.strip()[:70]}`"})
    return issues


# ── Layer 4: Scope ────────────────────────────────────────────────────────────

def check_pages_in_scope():
    import glob, os
    live_set = set(LIVE_PAGES)
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
        for table in SHARED_TABLES:
            if f"from('{table}')" in content or f'from("{table}")' in content:
                issues.append({"check": "pages_in_scope", "page": fname, "table": table,
                               "reason": f"{fname} reads from shared table '{table}' but is not in validate_tenant_boundary.py LIVE_PAGES"})
                break
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "select_filters", "realtime_scope",
    # L2
    "hive_id_source", "worker_name_source",
    # L3
    "switcher_validation", "url_param_injection",
    # L4
    "pages_in_scope",
]

CHECK_LABELS = {
    # L1
    "select_filters":      "L1  SELECT queries on shared tables have ownership filter",
    "realtime_scope":      "L1  Realtime subscriptions on shared tables have filter",
    # L2
    "hive_id_source":      "L2  HIVE_ID never from URL params or user input",
    "worker_name_source":  "L2  WORKER_NAME never from URL params or user input",
    # L3
    "switcher_validation": "L3  Hive switcher validates membership before switch",
    "url_param_injection": "L3  URL params not written to hive context",
    # L4
    "pages_in_scope":      "L4  All shared-table pages in LIVE_PAGES",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nTenant Boundary Escape Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_select_filters(LIVE_PAGES, SHARED_TABLES)
    all_issues += check_realtime_subscription_scope(LIVE_PAGES, SHARED_TABLES)
    all_issues += check_identity_source(LIVE_PAGES, "HIVE_ID", "hive_id_source")
    all_issues += check_identity_source(LIVE_PAGES, "WORKER_NAME", "worker_name_source")
    all_issues += check_switcher_validation("hive.html")
    all_issues += check_url_param_injection(LIVE_PAGES)
    all_issues += check_pages_in_scope()

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "tenant_boundary",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("tenant_boundary_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
