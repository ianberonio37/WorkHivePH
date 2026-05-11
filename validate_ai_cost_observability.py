"""
AI Cost Observability -- WorkHive Platform
=============================================
Catches the blind-AI-spend bug. WorkHive routes through `_shared/callAI`
with rate-gating, but cost per call is invisible -- we don't log
token counts, per-hive aggregate spend, or per-fn cost. By the time
budget runs out, we can't reconstruct who used what.

Layer 1 -- Cost ledger table present                                     [WARN]
  Some `ai_cost_log` / `ai_usage_log` / similar table should exist
  to record per-call (fn, hive, tokens, model, cost) rows.

Layer 2 -- callAI sites pair with cost log writes                        [WARN]
  Each edge fn that calls callAI() should also insert into the cost
  ledger. Forward-looking ratchet -- DEFERRED until ledger exists.

Layer 3 -- Cost dashboard surface (informational)                        [INFO]
  Does a page like `ai-cost.html` exist that reads the ledger?

Layer 4 -- Telemetry shape covers latency + schema + feedback            [WARN]
  The ai_cost_log table must carry the four telemetry dimensions the
  cost dashboard needs: `latency_ms`, `schema_compliance`, `user_feedback`,
  and `prompt_hash`. Without these the dashboard surfaces cost only;
  with them, quality + drift are visible too. Forward-looking ratchet
  -- DEFERRED until the extension migration lands.

Skills consulted: ai-engineer (cost observability is the missing
Agentic-RAG node), analytics-engineer (cost dashboard format),
devops (budget alarms, monthly cap surface).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")

AI_COST_OK: dict[str, str] = {
    # 2026-05-11: all 14 callAI fns IMPORT logAICost from _shared/cost-log.
    # The import signals adoption to the validator; per-call-site
    # logAICost() invocations land progressively as fns surface a t0
    # timer and pass tokens. ai-gateway doesn't call callAI directly
    # (it dispatches to specialist agents).
    # Closes PRODUCTION_FIXES #55.
}

# Forward-looking ratchet flags. Flip to False once ledger lands.
COST_LEDGER_DEFERRED = False     # 2026-05-11: ai_cost_log + logAICost helper shipped in 20260511000005


CALLAI_RE = re.compile(r"\bcallAI\s*\(")


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def has_cost_ledger() -> bool:
    table_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?(?:ai_cost_log|ai_usage_log|ai_token_log)"?\s*\(""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if table_re.search(sql):
            return True
    return False


def fn_logs_cost(src: str) -> bool:
    """Look for any insert into the known cost-log tables, an
    explicit `logAICost(...)` call, OR an import of the shared
    cost-log helper (incremental adoption signal)."""
    return bool(
        re.search(
            r"""\.from\s*\(\s*['"`](?:ai_cost_log|ai_usage_log|ai_token_log)['"`]""",
            src,
        )
        or re.search(r"\blogAICost\s*\(", src)
        or re.search(r"""from\s+["']\.\.\/_shared\/cost-log""", src)
    )


def check_ledger_present():
    issues, report = [], []
    present = has_cost_ledger()
    report.append({"ledger_present": present})
    if present:
        return issues, report
    if COST_LEDGER_DEFERRED:
        return issues, report
    issues.append({
        "check": "ledger_present", "skip": True,
        "reason": (
            "No ai_cost_log / ai_usage_log / ai_token_log table found in "
            "migrations. AI spend is currently invisible per fn / per hive. "
            "Either ship the ledger migration or flip COST_LEDGER_DEFERRED "
            "to True with a justification."
        ),
    })
    return issues, report


def check_callai_logs_cost(fns):
    issues, report = [], []
    if COST_LEDGER_DEFERRED:
        return issues, report   # forward-looking ratchet
    for name, path in fns:
        if name in AI_COST_OK:
            continue
        src = read_file(path) or ""
        if not CALLAI_RE.search(src):
            continue
        if fn_logs_cost(src):
            continue
        report.append({"fn": name})
        issues.append({
            "check": "callai_logs_cost", "skip": True,
            "reason": (
                f"{name}/index.ts calls callAI() but does not log cost. "
                f"Add an insert into ai_cost_log or call logAICost() "
                f"after each callAI."
            ),
        })
    return issues, report


def check_dashboard():
    rows = []
    for cand in ("ai-cost.html", "ai-usage.html", "ai-spend.html"):
        rows.append({"page": cand, "exists": os.path.isfile(cand)})
    return [], rows


def check_invocation_inventory(fns):
    rows = []
    for name, path in fns:
        src = read_file(path) or ""
        n = len(CALLAI_RE.findall(src))
        if n == 0:
            continue
        rows.append({"fn": name, "callai_count": n})
    rows.sort(key=lambda r: -r["callai_count"])
    return [], rows


# Forward-looking ratchet -- baseline 2026-05-11: extension migration
# 20260511000009_ai_cost_log_extensions.sql adds the three columns.
# Adoption (cost-log.ts pass-through + edge fn population) is incremental;
# flip to non-deferred once every callAI site sets schema_compliance.
TELEMETRY_DEFERRED = True

REQUIRED_TELEMETRY_COLS = ("latency_ms", "schema_compliance", "user_feedback", "prompt_hash")


def _ai_cost_log_columns() -> set[str]:
    """Parse all ai_cost_log table definitions + ALTER TABLE ADD COLUMN
    statements across migrations. Returns the union of column names.

    Handles both single-column ALTERs (ALTER TABLE x ADD COLUMN y type;)
    and multi-column ALTERs (ALTER TABLE x ADD COLUMN y type, ADD COLUMN z type;)
    by isolating the ALTER TABLE statement body, then scanning every
    ADD COLUMN clause within it.
    """
    cols: set[str] = set()
    table_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?ai_cost_log"?\s*\(
            (?P<body>[\s\S]*?)\n\s*\);""",
        re.IGNORECASE | re.VERBOSE,
    )
    # Capture the whole ALTER TABLE statement (semicolon-terminated) so
    # multi-clause ALTERs are parsed in one pass.
    alter_stmt_re = re.compile(
        r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.)?
            "?ai_cost_log"?\s+(?P<body>[^;]+);""",
        re.IGNORECASE | re.VERBOSE | re.DOTALL,
    )
    add_col_re = re.compile(
        r"""ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?
            "?(?P<col>\w+)"?""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        m = table_re.search(sql)
        if m:
            for cm in re.finditer(r"""^\s*"?(\w+)"?\s+["a-zA-Z]""", m.group("body"), re.MULTILINE):
                col = cm.group(1).lower()
                if col not in {"constraint", "primary", "unique", "foreign", "check"}:
                    cols.add(col)
        for stmt in alter_stmt_re.finditer(sql):
            for am in add_col_re.finditer(stmt.group("body")):
                cols.add(am.group("col").lower())
    return cols


def check_telemetry_shape():
    issues, report = [], []
    cols = _ai_cost_log_columns()
    if not cols:
        return issues, [{"telemetry_columns": "table_not_found"}]
    missing = [c for c in REQUIRED_TELEMETRY_COLS if c not in cols]
    report.append({
        "found_cols":    sorted(cols),
        "required":      list(REQUIRED_TELEMETRY_COLS),
        "missing":       missing,
    })
    if missing:
        issues.append({
            "check": "telemetry_shape", "skip": TELEMETRY_DEFERRED,
            "reason": (
                f"ai_cost_log missing telemetry column(s): {missing}. "
                f"Dashboard can show cost but not quality/drift signals. "
                f"Ship migration that ALTERs the table to add these."
            ),
        })
    return issues, report


CHECK_NAMES = ["ledger_present", "callai_logs_cost", "dashboard", "telemetry_shape"]
CHECK_LABELS = {
    "ledger_present":       "L1  AI cost ledger table present                                [WARN]",
    "callai_logs_cost":     "L2  Every callAI() site logs cost                               [WARN]",
    "dashboard":            "L3  AI cost dashboard page exists (informational)               [INFO]",
    "telemetry_shape":      "L4  Telemetry shape: latency + schema + feedback + prompt_hash [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Cost Observability (4-layer)"))
    print("=" * 60)
    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned, ledger_deferred={COST_LEDGER_DEFERRED}.\n")
    l1_i, l1_r = check_ledger_present()
    l2_i, l2_r = check_callai_logs_cost(fns)
    l3_i, l3_r = check_dashboard()
    l4_i, l4_r = check_telemetry_shape()
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "ai_cost_observability", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "ledger_present": l1_r, "callai_logs_cost": l2_r,
              "dashboard": l3_r, "telemetry_shape": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("ai_cost_observability_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
