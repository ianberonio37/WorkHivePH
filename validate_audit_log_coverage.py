"""
Audit Log Coverage Monitor -- WorkHive Platform
================================================
Enterprise-readiness gate. The platform has 3 audit tables (hive_audit_log,
cmms_audit_log, automation_log) but most state-changing writes don't trace
to them. Regulatory customers (especially industrial / pharmaceutical) need
"who did what when" for every meaningful state transition.

Layer 1 -- Critical writers without audit hooks                           [WARN]
  For each file that writes to a critical table (assets, inventory_items,
  marketplace_orders, etc.), check whether the same file ALSO writes to
  any audit log. Files that touch sensitive state but never audit are the
  highest-priority compliance gap.

Layer 2 -- Dead audit columns                                             [WARN]
  Columns defined on audit tables that no consumer reads. Audit is
  write-only by definition for SOME columns (the row IS the trail), but
  audit-VIEWER pages should be reading common columns (action, actor,
  target, created_at). If the viewer doesn't read a column, the column
  serves no review purpose.

Layer 3 -- Critical tables with zero audit anywhere                       [WARN]
  Tables identified as high-stakes that have no audit-log writer in the
  entire platform. Either the table doesn't need audit (allowlist) or
  the audit hooks were never wired.

Layer 4 -- Audit writer matrix                                            [INFO]
  Per audit table, who writes to it (html / edge / python_api)? Single-
  layer audit writers are documented exceptions (automation_log is
  edge-fn-only by design); this layer surfaces silent gaps.

Skills consulted: architect (audit pattern), security (every state change
needs a trail for incident-response), enterprise-compliance (regulatory
customers won't sign without an audit story), platform-guardian
(non-blocking informational tier).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# ── Paths ─────────────────────────────────────────────────────────────────────

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")
EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)

# The audit tables we recognize. Writes to ANY of these from a writer file
# satisfy the audit-coverage check for that file.
AUDIT_LOG_TABLES = {
    "hive_audit_log",      # user-driven actions on entities
    "cmms_audit_log",      # CMMS sync batches
    "automation_log",      # cron / async / AI job runs
}

# Tables we treat as "critical" — state changes here have compliance,
# financial, or regulatory impact and should leave an audit trail.
CRITICAL_TABLES = {
    # Master data (CRUD by users)
    "assets":            "Asset master — supervisor approve/reject is regulatory",
    "asset_nodes":       "Asset graph master — same",
    "pm_assets":         "PM asset master — scope changes affect compliance reports",
    "inventory_items":   "Parts master — approval gates have compliance impact",
    # Financial / commerce
    "inventory_transactions": "Stock movement is the audit trail itself, but adjustments need explicit log",
    "marketplace_orders":     "Money movement — every status change is reportable",
    "marketplace_disputes":   "Buyer/seller disputes — admin actions must be audited",
    "marketplace_listings":   "Listing publish/remove affects buyer trust",
    "marketplace_sellers":    "Seller verification + Stripe Connect changes",
    # Access / identity
    "hive_members":      "Membership + role changes (kick / promote)",
    "worker_profiles":   "Identity changes",
    # Engineering decisions (auditor cares — design intent record)
    "rcm_fmea_modes":    "Engineer-validated failure modes — approval gate is regulatory",
    "rcm_strategies":    "RCM decisions per JA1011 — design intent",
    # PM lifecycle
    "pm_scope_items":    "PM scope authoring — compliance audit",
    "pm_completions":    "PM execution record — already an audit trail itself, but supervisor overrides need logging",
    # Project change orders are already audited by their own state machine
}

# Tables where state changes are themselves the audit trail and a separate
# audit log entry is redundant (the row IS the record).
SELF_AUDITING_WRITERS = {
    "logbook":           "Each row IS a maintenance action audit; no double-logging needed",
    "pm_completions":    "Each completion row IS the audit; supervisor override could log separately",
    "skill_exam_attempts": "Attempt rows are the audit",
    "automation_log":    "Audit table itself",
    "hive_audit_log":    "Audit table itself",
    "cmms_audit_log":    "Audit table itself",
}

# Files that are LEGITIMATELY exempt from audit hooks. Either pure read,
# pure compute, or the writes are already audited elsewhere.
AUDIT_WRITER_EXEMPT_FILES = {
    # Edge fns whose writes ARE the audit (they write to *_log directly)
    "supabase\\functions\\batch-risk-scoring\\index.ts": "Writes to automation_log on every run",
    "supabase\\functions\\benchmark-compute\\index.ts":  "Writes to automation_log on every run",
    "supabase\\functions\\failure-signature-scan\\index.ts": "Writes to automation_log on every run",
    "supabase\\functions\\intelligence-report\\index.ts":  "Writes to automation_log on every run",
    "supabase\\functions\\parts-staging-recommender\\index.ts": "Writes to automation_log on every run",
    "supabase\\functions\\scheduled-agents\\index.ts":     "Writes to automation_log; cron orchestrator",
    "supabase\\functions\\send-report-email\\index.ts":   "Writes to automation_log; transactional email",
    "supabase\\functions\\trigger-ml-retrain\\index.ts":  "Writes to automation_log; weekly cron",
    # Edge fns that compute results not state changes
    "supabase\\functions\\weibull-fitter\\index.ts":      "Writes weibull_fits which IS the result-record audit",
    "supabase\\functions\\pf-calculator\\index.ts":       "Writes pf_intervals which IS the result-record audit",
    "supabase\\functions\\fmea-populator\\index.ts":      "Writes pending FMEA rows that supervisor still has to approve",
    "supabase\\functions\\shift-planner-orchestrator\\index.ts": "Writes shift_plans (DRAFT) which is reviewable; supervisor publish IS the audit moment",
    # Edge fns that write to /sync system tables
    "supabase\\functions\\cmms-sync\\index.ts":           "Writes cmms_audit_log directly",
    "supabase\\functions\\cmms-push-completion\\index.ts": "Writes automation_log on every push",
    "supabase\\functions\\cmms-webhook-receiver\\index.ts": "Writes external_sync (sync trail) + automation_log on each event",
    # Marketplace edge fns that write to marketplace_orders themselves —
    # the orders.status state machine + escrow_release_at IS the trail
    "supabase\\functions\\marketplace-checkout\\index.ts":         "Order state machine is the audit; release timer is the verifiable record",
    "supabase\\functions\\marketplace-release\\index.ts":          "Same",
    "supabase\\functions\\marketplace-webhook\\index.ts":          "Same — Stripe webhook is the upstream record",
    "supabase\\functions\\marketplace-connect-onboard\\index.ts":  "Stripe Connect events are the upstream record",
    "supabase\\functions\\marketplace-connect-status\\index.ts":   "Read-mostly; status check, no critical writes",
    # AI / project orchestrators that write to project tables but the project
    # state machine itself is the audit
    "supabase\\functions\\project-orchestrator\\index.ts": "Writes to projects/items but each row's status transition is the audit",
    "supabase\\functions\\project-progress\\index.ts":     "Writes project_progress_logs which IS the audit",
    # Analytics fns are read-only or write to result tables
    "supabase\\functions\\analytics-orchestrator\\index.ts": "Writes ai_reports (insert-only result audit)",
    "supabase\\functions\\ai-orchestrator\\index.ts":        "Writes ai_reports + automation_log",
    "supabase\\functions\\embed-entry\\index.ts":            "Writes asset_embeddings (vector pipeline output)",
    "supabase\\functions\\semantic-search\\index.ts":        "Read-only RAG endpoint",
    # Voice fns log via the receiving page's downstream write
    "supabase\\functions\\voice-action-router\\index.ts":     "Routes intents — receiver page logs the actual write",
    "supabase\\functions\\voice-logbook-entry\\index.ts":     "Returns parsed logbook entry; the page does the insert + its audit",
    "supabase\\functions\\voice-report-intent\\index.ts":     "Returns parsed intent; page does write",
    "supabase\\functions\\voice-transcribe\\index.ts":        "STT only, no DB writes",
    "supabase\\functions\\engineering-bom-sow\\index.ts":     "Returns BOM/SOW; page persists",
    "supabase\\functions\\engineering-calc-agent\\index.ts":  "Returns calc results; page persists with audit",
    "supabase\\functions\\asset-brain-query\\index.ts":       "Read-only RAG endpoint",
    "supabase\\functions\\voice-action-router\\index.ts":     "Routes intents (duplicate exempt for safety)",
    # Retired pages — kept in tree for reference but not in nav-hub TOOLS array
    # (see project_retired_pages memory note). No live writers.
    "parts-tracker.html": "Retired page — superseded by Logbook; kept for git history only",
    # index.html only INSERTs worker_profiles during sign-up, before any
    # HIVE_ID exists. hive_audit_log requires hive_id NOT NULL, so there is
    # nowhere appropriate to log to. Supabase Auth's own auth.users table
    # IS the account-creation audit trail (auth_uid + created_at per row),
    # consultable via the Supabase dashboard. The hive_members.member_joined
    # event is audited from hive.html when the user actually joins a hive.
    "index.html": "worker_profiles inserted only on sign-up before HIVE_ID exists; Supabase auth.users is the account-creation audit; hive join is audited from hive.html",
}


# ── Discovery: writer files + tables ──────────────────────────────────────────

WRITE_OP_RE_JSTS = re.compile(
    r"""\.from\s*\(\s*['"`]([a-z_][a-z0-9_]*)['"`]\s*\)\s*\.\s*(insert|upsert|update|delete)""",
    re.IGNORECASE,
)
WRITE_OP_RE_PY = re.compile(
    r"""\.table\s*\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)\s*\.\s*(insert|upsert|update|delete)""",
    re.IGNORECASE,
)


def _path_excluded(path: str) -> bool:
    return any(part in path for part in EXCLUDED_PATH_PARTS)


def list_writer_files() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS): continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"): continue
        out.append((path, "shared_js"))
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path or _path_excluded(path): continue
        out.append((path, "python_api"))
    return out


def file_writes(path: str) -> set[str]:
    """Return set of tables this file writes to (insert/upsert/update/delete)."""
    content = read_file(path) or ""
    rx = WRITE_OP_RE_PY if path.endswith(".py") else WRITE_OP_RE_JSTS
    return {m.group(1).lower() for m in rx.finditer(content)}


# ── Layer 1: Critical writers without audit hooks ────────────────────────────

def check_unaudited_critical_writers(
    files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    """A file that writes to a CRITICAL_TABLES entry but does not also write
    to any AUDIT_LOG_TABLES entry is missing audit hooks."""
    issues: list[dict] = []
    report: list[dict] = []
    for path, layer in files:
        writes = file_writes(path)
        critical_writes = sorted(writes & CRITICAL_TABLES.keys())
        if not critical_writes:
            continue
        if path in AUDIT_WRITER_EXEMPT_FILES:
            continue
        audited = bool(writes & AUDIT_LOG_TABLES)
        if audited:
            continue
        report.append({
            "path":            path,
            "layer":           layer,
            "critical_tables": critical_writes,
        })
        issues.append({
            "check": "unaudited_critical_writers", "skip": True,
            "reason": (
                f"{path} writes to critical table(s) {critical_writes} but never "
                f"inserts to any audit log ({sorted(AUDIT_LOG_TABLES)}). Add a "
                f"hive_audit_log insert (or appropriate audit table) at each "
                f"state-change site, or add the file to AUDIT_WRITER_EXEMPT_FILES "
                f"with a justification."
            ),
        })
    return issues, report


# ── Layer 2: Dead audit columns ──────────────────────────────────────────────

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\((?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
COL_LINE_RE = re.compile(
    r"""^\s*"?(?P<col>\w+)"?\s+["a-zA-Z]""",
    re.MULTILINE,
)
SELECT_RE_JSTS = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?:\s*\.\s*[a-zA-Z_]\w*\s*\([^)]*\))*?
        \s*\.\s*select\s*\(\s*['"`](?P<sel>[^'"`]+)['"`]""",
    re.IGNORECASE | re.VERBOSE,
)


def load_audit_columns() -> dict[str, set[str]]:
    """Return {audit_table: {column_names}} across migrations."""
    out: dict[str, set[str]] = defaultdict(set)
    COL_KEYWORDS = {"constraint", "primary", "unique", "foreign", "check", "exclude", "like"}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in CREATE_TABLE_RE.finditer(sql):
            name = m.group("name").lower()
            if name not in AUDIT_LOG_TABLES:
                continue
            for cm in COL_LINE_RE.finditer(m.group("body")):
                col = cm.group("col").lower()
                if col in COL_KEYWORDS: continue
                out[name].add(col)
    return dict(out)


def selected_columns_per_audit_table(
    files: list[tuple[str, str]],
) -> dict[str, set[str]]:
    """Track which audit-table columns are SELECTed by any consumer."""
    out: dict[str, set[str]] = defaultdict(set)
    for path, _layer in files:
        if path.endswith(".py"): continue   # Python rarely SELECTs audit logs
        content = read_file(path) or ""
        for m in SELECT_RE_JSTS.finditer(content):
            t = m.group("table").lower()
            if t not in AUDIT_LOG_TABLES:
                continue
            sel = m.group("sel")
            for piece in sel.split(","):
                piece = piece.strip()
                if not piece: continue
                # Bare identifier or alias:underlying — extract the underlying
                if ":" in piece:
                    piece = piece.split(":", 1)[1].strip()
                # Strip embed shapes
                if "(" in piece:
                    piece = piece.split("(", 1)[0].strip()
                if piece and piece != "*":
                    out[t].add(piece.lower())
                if piece == "*":
                    out[t] = out.get(t, set()) | set()  # mark covered
                    # Wildcard covers everything; no need to enumerate
    return dict(out)


def check_dead_audit_columns(
    audit_cols: dict[str, set[str]],
    selected: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    dead: list[dict] = []
    SILENT = {"id", "hive_id", "created_at", "updated_at", "auth_uid"}
    for table, cols in audit_cols.items():
        consumed = selected.get(table, set())
        # If anyone SELECTs '*' from this table, mark as fully covered
        # (we lose specificity but accept it)
        unused = sorted((cols - consumed) - SILENT)
        if not unused:
            continue
        # Need 4+ unused columns before we WARN
        if len(unused) < 4:
            continue
        dead.append({"audit_table": table, "unused_cols": unused})
        issues.append({
            "check": "dead_audit_columns", "skip": True,
            "reason": (
                f"Audit table '{table}' has {len(unused)} column(s) that no consumer "
                f"selects: {unused[:6]}. Either add a viewer (audit log review page) "
                f"that displays these or remove the columns from the schema. "
                f"Audit-without-review is regulatory theatre."
            ),
        })
    return issues, dead


# ── Layer 3: Critical tables with zero audit anywhere ────────────────────────

def check_critical_tables_with_no_audit(
    files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    """For each critical table, check if ANY writer file (or any other file)
    correlates writes to that table with audit-log writes. If the table is
    written somewhere but NO file that touches it also touches audit_log, the
    table has zero audit coverage."""
    # Build {critical_table: bool(any_audited_writer)}
    audited: dict[str, bool] = {t: False for t in CRITICAL_TABLES}
    writers_per_table: dict[str, list[str]] = defaultdict(list)
    for path, _layer in files:
        if path in AUDIT_WRITER_EXEMPT_FILES:
            # Exempt files don't count for table-level coverage either
            continue
        writes = file_writes(path)
        critical_hits = writes & CRITICAL_TABLES.keys()
        if not critical_hits:
            continue
        is_audited = bool(writes & AUDIT_LOG_TABLES)
        for t in critical_hits:
            writers_per_table[t].append(path)
            if is_audited:
                audited[t] = True
    issues: list[dict] = []
    no_coverage: list[dict] = []
    for table, has_audit in audited.items():
        # Skip tables with no writers at all (nothing to audit)
        if not writers_per_table.get(table):
            continue
        if has_audit:
            continue
        no_coverage.append({
            "table":   table,
            "purpose": CRITICAL_TABLES[table],
            "writers": sorted(writers_per_table[table])[:5],
        })
        issues.append({
            "check": "critical_table_no_audit", "skip": True,
            "reason": (
                f"Critical table '{table}' ({CRITICAL_TABLES[table]}) has writers "
                f"({sorted(writers_per_table[table])[:3]}) but NO writer file in the "
                f"platform also inserts to an audit log. The state-change trail is "
                f"completely silent for compliance review. Either wire audit on at "
                f"least one writer or remove from CRITICAL_TABLES with justification."
            ),
        })
    return issues, no_coverage


# ── Layer 4: Audit writer matrix (informational) ─────────────────────────────

def build_audit_writer_matrix(
    files: list[tuple[str, str]],
) -> list[dict]:
    """For each audit table, count writers per platform layer."""
    matrix: dict[str, dict[str, list[str]]] = {t: defaultdict(list) for t in AUDIT_LOG_TABLES}
    for path, layer in files:
        writes = file_writes(path)
        for t in writes & AUDIT_LOG_TABLES:
            matrix[t][layer].append(path)
    out: list[dict] = []
    for t, by_layer in matrix.items():
        out.append({
            "audit_table": t,
            "by_layer":    {k: len(v) for k, v in by_layer.items()},
            "total":       sum(len(v) for v in by_layer.values()),
        })
    out.sort(key=lambda m: -m["total"])
    return out


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "unaudited_critical_writers",
    "dead_audit_columns",
    "critical_table_no_audit",
    "audit_writer_matrix",
]
CHECK_LABELS = {
    "unaudited_critical_writers": "L1  Every critical-table writer also writes to an audit log         [WARN]",
    "dead_audit_columns":         "L2  No audit table column is unread (audit-without-review)          [WARN]",
    "critical_table_no_audit":    "L3  Every critical table has at least one audited writer            [WARN]",
    "audit_writer_matrix":        "L4  Audit writers spread across platform layers (informational)     [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAudit Log Coverage (4-layer)"))
    print("=" * 60)

    files       = list_writer_files()
    audit_cols  = load_audit_columns()
    selected    = selected_columns_per_audit_table(files)

    print(f"  {len(AUDIT_LOG_TABLES)} audit tables, {len(CRITICAL_TABLES)} critical tables, "
          f"{len(files)} writer files scanned, {len(AUDIT_WRITER_EXEMPT_FILES)} exempt.\n")

    l1_issues, l1_report = check_unaudited_critical_writers(files)
    l2_issues, l2_report = check_dead_audit_columns(audit_cols, selected)
    l3_issues, l3_report = check_critical_tables_with_no_audit(files)
    l4_matrix            = build_audit_writer_matrix(files)

    all_issues = l1_issues + l2_issues + l3_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    print(f"\n{bold('AUDIT WRITER MATRIX')}")
    print("  " + "-" * 56)
    for entry in l4_matrix:
        ls = ", ".join(f"{k}={v}" for k, v in sorted(entry["by_layer"].items())) or "-"
        print(f"  {entry['audit_table']:<22}  total={entry['total']:<3}  {ls}")

    if l3_report:
        print(f"\n{bold('CRITICAL TABLES WITH NO AUDIT COVERAGE')}")
        print("  " + "-" * 56)
        for d in l3_report:
            print(f"  {d['table']:<24}  {d['purpose'][:60]}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":           "audit_log_coverage",
        "total_checks":        total,
        "passed":              n_pass,
        "warned":              n_warn,
        "failed":              n_fail,
        "audit_tables":        sorted(AUDIT_LOG_TABLES),
        "critical_tables":     sorted(CRITICAL_TABLES.keys()),
        "n_exempt_files":      len(AUDIT_WRITER_EXEMPT_FILES),
        "unaudited_writers":   l1_report,
        "dead_audit_columns":  l2_report,
        "tables_no_coverage":  l3_report,
        "audit_writer_matrix": l4_matrix,
        "issues":              [i for i in all_issues if not i.get("skip")],
        "warnings":            [i for i in all_issues if i.get("skip")],
    }
    with open("audit_log_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
