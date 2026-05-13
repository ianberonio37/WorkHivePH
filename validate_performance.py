"""
Performance Anti-Pattern Validator — WorkHive Platform
=======================================================
Performance issues are invisible during development when the database is
small — they emerge silently in production as data grows.

  Layer 1 — Query anti-patterns
    1.  Unbounded queries     [WARN] — logbook/inv_transactions without .limit()
    2.  select('*') on wide   [WARN] — wide tables should use named columns
    3.  DB calls in loops     [WARN] — N+1 pattern: one DB call per item
    4.  Sequential awaits     [WARN] — independent awaits should use Promise.all

  Layer 2 — JS runtime anti-patterns
    5.  setInterval leak      [FAIL] — every setInterval must have clearInterval
    6.  innerHTML += in loops [WARN] — repeated DOM reparse/reflow per iteration

  Layer 3 — Rendering safety
    7.  body animation guard  [FAIL] — opacity:0 body needs animationend fallback

  Layer 4 — Scope completeness
    8.  All pages in scope    — analytics.html and new pages included in checks

Usage:  python validate_performance.py
Output: performance_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LIVE_PAGES = [
    "index.html",
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "analytics-report.html",
    "report-sender.html",
    "community.html",
    "marketplace.html",
    "marketplace-admin.html",
    "marketplace-seller.html",
    "marketplace-seller-profile.html",
    "public-feed.html",
    "project-manager.html",
    "integrations.html",
    "ph-intelligence.html",
    "project-report.html",
    "predictive.html",
    "ai-quality.html",          # Phase 4.1 — AI Quality + ROI dashboard
    "plant-connections.html",   # Phase 5 Track C — Plant Connections Console
    "achievements.html",
    "asset-hub.html",
    "shift-brain.html",
    "alert-hub.html",
    "audit-log.html",
    "voice-journal.html",
]

# Tables that grow row-by-row over time (one row per event, hour, or
# write). A `.select()` on these without `.limit()` / `.range()` / a row
# filter pulls every historical row and chokes the page once data grows.
# Per the performance skill: "Enforce .limit(50) on every list query.
# Never allow unbounded fetches."
HIGH_GROWTH_TABLES = [
    # Workforce write paths (one row per event)
    "logbook",                    # 3,700+ rows in seed; grows per shift
    "inventory_transactions",     # one row per stock move
    "schedule_items",             # one row per Day Planner task
    "pm_completions",             # one row per PM done
    "engineering_calcs",          # one row per calc saved
    "voice_journal_entries",      # one row per voice note
    # Community / social
    "community_posts",
    "community_replies",
    "community_reactions",
    "community_xp",
    # Achievements XP
    "achievement_xp_log",
    "worker_achievements",        # bounded by definitions but log grows
    # AI / observability
    "ai_cost_log",                # every AI call appends a row
    "ai_quality_log",
    "gateway_audit_log",
    "automation_log",
    "hive_route_calls",
    # Domain append-only
    "amc_briefings",              # one per hive per shift_date
    "failure_signature_alerts",
    "asset_risk_scores",          # one per asset per scoring run
    "parts_records",              # parts usage history
    "parts_staged_reservations",
    "parts_staging_recommendations",
    # Audit / safety
    "audit_log",
    "hive_audit_log",
    "cmms_audit_log",
    # Plant telemetry (highest growth — every sensor reading)
    "sensor_readings",
    # External integrations
    "external_sync",
    # Misc
    "pdf_jobs",
    "agent_memory",               # one per agent turn
    "asset_embeddings",           # one per asset, but multiplied per re-embed
    "fault_knowledge",            # paraphrased from logbook breakdowns
]
WIDE_TABLES        = ["logbook", "inventory_items", "inventory_transactions",
                      "pm_scope_items", "pm_completions"]
SEQUENTIAL_AWAIT_THRESHOLD = 2

# Baseline ratchet for unbounded_queries. Pre-existing platform debt is
# locked in as a baseline; FAIL only on per-page count INCREASES.
# Same pattern proven on UX Contract A2 (input_label baseline).
UNBOUNDED_BASELINE_FILE = "performance_unbounded_baseline.json"


# ── Layer 1: Query anti-patterns ──────────────────────────────────────────────

def _load_unbounded_baseline() -> dict:
    if not os.path.exists(UNBOUNDED_BASELINE_FILE):
        return {}
    try:
        with open(UNBOUNDED_BASELINE_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("per_page", {})
    except Exception:
        return {}


def _save_unbounded_baseline(per_page: dict) -> None:
    payload = {
        "_doc": (
            "Per-page baseline of unbounded queries on HIGH_GROWTH_TABLES. "
            "New violations FAIL the gate; existing ones are accepted. "
            "Regenerate (count can only go DOWN) with: "
            "python validate_performance.py --update-unbounded-baseline"
        ),
        "total":    sum(per_page.values()),
        "per_page": per_page,
    }
    with open(UNBOUNDED_BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def check_unbounded_queries():
    """Returns issues only when a page exceeds its baseline count. The first
    run with no baseline file writes one and reports nothing. The advisory-
    style raw findings (every violation, even at-or-under baseline) are
    persisted in the report JSON for visibility, but only over-baseline
    pages are FAIL-emitted."""
    baseline = _load_unbounded_baseline()
    raw_per_page: dict = {}
    all_findings: list[dict] = []

    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        page_count = 0
        for i, line in enumerate(lines):
            table = next((t for t in HIGH_GROWTH_TABLES
                          if f"from('{t}')" in line or f'from("{t}")' in line), None)
            if not table or ".select(" not in line:
                continue
            # Skip the `.insert(...).select()` pattern — that's a write
            # operation returning the inserted row, not a list query.
            if re.search(r"\.(?:insert|upsert|update|delete)\s*\(", line):
                continue
            if "head: true" in line or "count: 'exact'" in line or 'count: "exact"' in line:
                continue
            window = "\n".join(lines[i:min(len(lines), i + 15)])
            if ".limit(" in window or ".range(" in window:
                continue
            # Bounded filters accepted as "not unbounded":
            #   .single() / .maybeSingle()   — single row fetch
            #   .eq('id', ...)               — single row by id
            #   .in('<col>', [list])         — bounded set of rows
            #   .gte('<time-col>', ...)      — time window
            if re.search(r"\.maybeSingle\s*\(|\.single\s*\(", window):
                continue
            if re.search(r"\.eq\s*\(\s*['\"]id['\"]", line):
                continue
            if re.search(r"\.in\s*\(\s*['\"]", line):
                continue
            if re.search(r"\.gte\s*\(\s*['\"](?:created_at|recorded_at|generated_at|date|logged_at|completed_at|ts|timestamp)['\"]", window):
                continue
            page_count += 1
            all_findings.append({
                "page":   page,
                "line":   i + 1,
                "table":  table,
                "snippet": line.strip()[:80],
            })
        raw_per_page[page] = page_count

    # First run: write baseline, emit nothing.
    if not os.path.exists(UNBOUNDED_BASELINE_FILE) and raw_per_page:
        _save_unbounded_baseline(raw_per_page)
        return []

    # Ratchet: FAIL only on per-page increases.
    issues = []
    for page, count in raw_per_page.items():
        base = baseline.get(page, 0)
        if count > base:
            new = count - base
            issues.append({
                "check": "unbounded_queries",
                "page":  page,
                "skip":  False,
                "reason": (
                    f"{page}: {count} unbounded queries on HIGH_GROWTH_TABLES "
                    f"but baseline is {base}. +{new} new violation(s). "
                    f"Add .limit(50) within 15 lines of the .select() call "
                    f"(see performance skill: Query-First pattern + keyset "
                    f"pagination). If legitimately new debt, regenerate the "
                    f"baseline via --update-unbounded-baseline."
                ),
            })
    # Stash raw_per_page on the issue list for the runner to expose.
    issues.append({
        "_raw_per_page": raw_per_page,
        "_findings":     all_findings,
        "_skip_render":  True,
    })
    return issues


def check_select_star():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table = next((t for t in WIDE_TABLES
                          if f"from('{t}')" in line or f'from("{t}")' in line), None)
            if not table:
                continue
            if not re.search(r"\.select\s*\(\s*['\*]['\*]?\s*\)", line):
                continue
            if "head: true" in line:
                continue
            issues.append({"check": "select_star", "page": page, "line": i + 1,
                           "skip": True,   # WARN — bandwidth waste, not broken
                           "reason": f"{page}:{i+1} select('*') on '{table}' — use named columns to reduce bandwidth 3-10x"})
    return issues


def check_db_in_loop():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "db.from(" not in line or line.strip().startswith("//"):
                continue
            window_back = "\n".join(lines[max(0, i - 2):i])
            if re.search(r"\bforEach\s*\(|\bfor\s*\(|\bfor\s+(?:const|let|var)\b", window_back):
                issues.append({"check": "db_in_loop", "page": page, "line": i + 1,
                               "skip": True,   # WARN — migration paths are known exceptions
                               "reason": f"{page}:{i+1} db.from() inside a loop (N+1 pattern) — use a single .in() batch query: `{line.strip()[:70]}`"})
    return issues


def check_sequential_awaits():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            if "await db.from(" not in lines[i] or lines[i].strip().startswith("//"):
                i += 1
                continue
            run = [i]
            j = i + 1
            while j < min(i + 6, len(lines)):
                l = lines[j].strip()
                if not l or l.startswith("//"):
                    j += 1
                    continue
                if "await db.from(" in lines[j]:
                    run.append(j); j += 1
                else:
                    break
            if len(run) >= SEQUENTIAL_AWAIT_THRESHOLD:
                first, second = lines[run[0]], lines[run[1]]
                var_m = re.search(r"const\s*\{[^}]+\}\s*=\s*await", first)
                if var_m:
                    var_names = re.findall(r"\b(\w+)\b", first[:first.find("= await")])
                    if not any(v in second for v in var_names if len(v) > 2):
                        issues.append({"check": "sequential_awaits", "page": page,
                                       "lines": [r + 1 for r in run[:2]],
                                       "skip": True,   # WARN — not broken, just slow
                                       "reason": f"{page}:{run[0]+1}-{run[1]+1} {len(run)} sequential await db.from() — wrap in Promise.all() to halve load time"})
            i = run[-1] + 1 if len(run) > 1 else i + 1
    return issues


# ── Layer 2: JS runtime anti-patterns ────────────────────────────────────────

def check_set_interval_leak():
    """
    Every setInterval() call must be stored in a variable so clearInterval()
    can stop it. A setInterval with no clearInterval is a memory/CPU leak —
    the callback keeps firing even after the page component is torn down.
    """
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        # Find all setInterval calls
        intervals = list(re.finditer(r'\bsetInterval\s*\(', content))
        if not intervals:
            continue
        has_clear = "clearInterval" in content
        if not has_clear:
            issues.append({"check": "set_interval_leak", "page": page,
                           "reason": f"{page} calls setInterval() but has no clearInterval() — timers accumulate on repeated navigation and never stop"})
            continue
        # Check each setInterval is assigned to a variable
        for m in intervals:
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:content.find('\n', m.start())].strip()
            if line.startswith("//") or line.startswith("*"):
                continue
            # Assigned to a variable? (const x = setInterval / let x = setInterval / x = setInterval)
            is_assigned = bool(re.search(r'(?:const|let|var)\s+\w+\s*=\s*setInterval|^\s*\w+\s*=\s*setInterval', line))
            if not is_assigned:
                line_no = content[:m.start()].count('\n') + 1
                issues.append({"check": "set_interval_leak", "page": page, "line": line_no,
                               "reason": f"{page}:{line_no} setInterval() result not stored in a variable — cannot be cleared: `{line[:70]}`"})
    return issues


def check_inner_html_concat_in_loop():
    """
    `element.innerHTML += ...` inside a loop re-parses the ENTIRE innerHTML on
    every iteration. 100 items = 100 full DOM re-parses instead of 1.
    The correct pattern is to build the string first and assign once:
      let html = items.map(...).join('');
      element.innerHTML = html;
    """
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "innerHTML +=" not in line:
                continue
            if line.strip().startswith("//"):
                continue
            # Look back 3 lines for a loop opener
            window_back = "\n".join(lines[max(0, i - 3):i])
            if re.search(r"\bforEach\s*\(|\bfor\s*\(|\bfor\s+(?:const|let|var)\b|\bwhile\s*\(", window_back):
                issues.append({"check": "innerHTML_concat_loop", "page": page, "line": i + 1,
                               "skip": True,   # WARN — degrades with data size
                               "reason": f"{page}:{i+1} innerHTML += inside loop — re-parses DOM {'{N}'} times. Build string first, assign once."})
    return issues


# ── Layer 3: Rendering safety ─────────────────────────────────────────────────

def check_body_animation_safety_guard():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        if not re.search(r"body\s*\{[^}]*\banimation\s*:", content, re.DOTALL):
            continue
        if not re.search(r"addEventListener\s*\(\s*['\"]animationend['\"]", content):
            issues.append({"check": "body_animation_guard", "page": page,
                           "reason": f"{page} has body {{ animation }} but no animationend safety guard — blank page if animation stalls (background tab or prefers-reduced-motion)"})
    return issues


# ── Layer 4: Scope completeness ───────────────────────────────────────────────

def check_pages_in_scope():
    """Every .html page that makes db.from() calls should be in LIVE_PAGES."""
    import glob
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
        if content and "db.from(" in content:
            issues.append({"check": "pages_in_scope", "page": fname,
                           "reason": f"{fname} makes DB calls but is not in validate_performance.py LIVE_PAGES — performance checks never run on it"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "unbounded_queries", "select_star", "db_in_loop", "sequential_awaits",
    # L2
    "set_interval_leak", "innerHTML_concat_loop",
    # L3
    "body_animation_guard",
    # L4
    "pages_in_scope",
]

CHECK_LABELS = {
    # L1
    "unbounded_queries":    "L1  No NEW unbounded queries on append-only tables (ratcheted)",
    "select_star":          "L1  No select('*') on wide tables  [WARN]",
    "db_in_loop":           "L1  No db.from() inside loops (N+1)  [WARN]",
    "sequential_awaits":    "L1  No consecutive sequential await DB calls  [WARN]",
    # L2
    "set_interval_leak":    "L2  setInterval() result stored for clearInterval",
    "innerHTML_concat_loop":"L2  No innerHTML += inside loops  [WARN]",
    # L3
    "body_animation_guard": "L3  body animation has animationend safety guard",
    # L4
    "pages_in_scope":       "L4  All DB-using pages in LIVE_PAGES scope",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPerformance Anti-Pattern Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    unbounded_issues = check_unbounded_queries()
    # Handle --update-unbounded-baseline write-op: extract raw_per_page
    # from the sentinel and persist as the new baseline. Useful when
    # closing legitimate debt and ratcheting the floor down.
    raw_findings = []
    raw_per_page = {}
    for it in unbounded_issues:
        if it.get("_skip_render"):
            raw_per_page = it.get("_raw_per_page", {})
            raw_findings = it.get("_findings", [])
            break
    unbounded_issues = [i for i in unbounded_issues if not i.get("_skip_render")]
    if "--update-unbounded-baseline" in sys.argv:
        _save_unbounded_baseline(raw_per_page)
        print(f"\n  Baseline updated: {sum(raw_per_page.values())} unbounded "
              f"queries across {len([k for k,v in raw_per_page.items() if v])} page(s).")
        sys.exit(0)
    all_issues += unbounded_issues
    all_issues += check_select_star()
    all_issues += check_db_in_loop()
    all_issues += check_sequential_awaits()
    all_issues += check_set_interval_leak()
    all_issues += check_inner_html_concat_in_loop()
    all_issues += check_body_animation_safety_guard()
    all_issues += check_pages_in_scope()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL — warnings are known technical debt\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "performance",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("performance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()

