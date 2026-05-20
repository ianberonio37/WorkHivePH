"""validate_audit_trail_coverage.py — Walkthrough 2026-05-13 finding generalised.

Bug class found during walkthrough: a supervisor power action mutates a
status-lifecycle row (anomaly_signals ack/resolve) but never writes a
matching row to hive_audit_log. The action is invisible in the standard
audit trail. Compliance reports, insurance bridge view, and multi-
supervisor coordination all lose traceability.

This validator enumerates every lifecycle table that should be audited
when its status changes via UI, then scans every page's update handler
for the matching writeAuditLog call.

  Layer 1 — UI mutation paired with audit log
    For each LIFECYCLE_TABLE, every `.update({ status: ... }` call site
    must be in the same function body as a `writeAuditLog(` call.

  Layer 2 — Audit-log action vocabulary completeness
    hive.html's ACTION_ICON map must include an entry for every action
    string written by writeAuditLog. Unknown actions render with the
    generic dot icon — a quiet drift that makes the audit log harder
    to read.

Out of scope (intentional):
  - Server-side mutations (edge functions writing through service-role).
    Those should write audit-log entries too, but a different validator
    covers edge fn audit (validate_edge_contracts).
  - Lifecycle tables whose status changes are driven only by cron / RPC
    (failure_signature_alerts is written by the failure-signature-scan
    edge fn; ack/resolve UI is also in alert-hub but goes through this
    validator already because it's UI-layer).
"""
from __future__ import annotations
import json, re, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent

# Lifecycle tables where every UI-layer status change is a supervisor
# power action that MUST land in hive_audit_log. Add new tables here as
# the platform gains them. Each entry: (table, [valid_status_values]).
LIFECYCLE_TABLES = {
    "anomaly_signals":     ["acknowledged", "resolved"],
    "hive_members":        ["kicked"],
    "amc_briefings":       ["approved", "rejected"],
    "asset_nodes":         ["approved", "rejected"],
    "inventory_items":     ["approved", "rejected"],
    "assets":              ["approved", "rejected"],
    "drone_inspections":   ["reviewed", "archived", "cancelled"],
    "consulting_engagements": ["completed", "cancelled"],
}

# Audit log action vocabulary — every string passed as first arg to
# writeAuditLog should have an entry in hive.html's ACTION_ICON map.
# Validators surface missing entries so the audit-log viewer doesn't
# render an event as a generic dot.

LIVE_PAGES = [
    "hive.html", "logbook.html", "inventory.html", "pm-scheduler.html",
    "asset-hub.html", "alert-hub.html", "shift-brain.html",
    "audit-log.html", "project-manager.html", "marketplace.html",
    "marketplace-admin.html", "dayplanner.html",
]

ACTION_ICON_PAGE = "hive.html"

# Re-entry guard: some pages declare an UPDATE inside a generator / loop
# rather than a handler. Skip those — we only care about function-scoped
# update calls.

# L1 — "is there a writeAuditLog call at all". Accepts any first arg
# (literal, ternary, variable). The presence of the call is enough for
# audit-coverage; the action vocabulary check is separate.
WRITE_AUDIT_ANY_RE = re.compile(r"\bwriteAuditLog\s*\(")
# L2 — extract literal action names. Also recognises the ternary form
# `cond ? 'name_a' : 'name_b'` by collecting BOTH names so the ACTION_ICON
# completeness check covers conditional dispatch.
# Action names follow snake_case verb_noun. Requiring at least one
# underscore filters out comparison literals like 'acknowledge', 'approved',
# 'pending' that appear in `cond === 'X' ? ...` first-arg ternaries.
WRITE_AUDIT_NAMES_RE = re.compile(r"['\"]([a-z][a-z0-9_]*_[a-z0-9_]{1,40})['\"]")
WRITE_AUDIT_CALL_RE  = re.compile(r"\bwriteAuditLog\s*\(([^)]{0,400})")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _enclosing_function_body(content: str, position: int, window: int = 4000) -> str:
    """Return ~window chars of the enclosing function body around `position`.
    Walks backward to find `function`/`async function`/arrow function open;
    if none found within `window`, returns a fixed-size slice instead.
    """
    start = max(0, position - window)
    return content[start:position + window]


def check_lifecycle_audit_coverage() -> list[dict]:
    issues = []
    for page in LIVE_PAGES:
        p = ROOT / page
        if not p.exists():
            continue
        content = _read(p)
        if not content:
            continue
        for table, statuses in LIFECYCLE_TABLES.items():
            # Match: .from('TABLE')...update({ status:
            patt = re.compile(
                rf"\.from\(\s*['\"]{re.escape(table)}['\"]\s*\)[\s\S]{{0,200}}\.update\s*\(\s*\{{[^}}]*status\s*:",
                re.IGNORECASE,
            )
            for m in patt.finditer(content):
                line = content[:m.start()].count("\n") + 1
                # Within ~30 lines of this update, is there a writeAuditLog
                # call? That's the audit-trail pairing the validator demands.
                lookahead = content[m.start():m.start() + 3000]
                lookbehind = content[max(0, m.start() - 1500):m.start()]
                window_blob = lookbehind + lookahead
                if not WRITE_AUDIT_ANY_RE.search(window_blob):
                    issues.append({
                        "check": "lifecycle_audit_missing",
                        "page": page,
                        "table": table,
                        "line": line,
                        "reason": (
                            f"{page}:{line} — `{table}` status update has no "
                            f"writeAuditLog call in scope. Supervisor power "
                            f"actions on lifecycle tables MUST land in "
                            f"hive_audit_log so compliance audits and the "
                            f"insurance bridge view can read the trail."
                        ),
                    })
    return issues


def _harvest_actions_from_js(src: str) -> set:
    """Pull action names from writeAuditLog(FIRST_ARG, ...) calls in JS."""
    out = set()
    for call_m in WRITE_AUDIT_CALL_RE.finditer(src):
        args_window = call_m.group(1)
        first_arg = ''
        depth = 0
        for i, ch in enumerate(args_window):
            if ch in '([{': depth += 1
            elif ch in ')]}': depth -= 1
            elif ch == ',' and depth == 0:
                first_arg = args_window[:i]
                break
        else:
            first_arg = args_window
        for n in WRITE_AUDIT_NAMES_RE.findall(first_arg):
            out.add(n)
    return out


# SQL: INSERT INTO hive_audit_log (..., action, ...) VALUES (..., 'action_name', ...)
# OR  : INSERT INTO hive_audit_log (..., action, ...) SELECT ..., 'action_name', ...
# OR  : INSERT INTO hive_audit_log (..., action, ...) SELECT (ARRAY['a','b'])[floor(...)]
# We walk the column list, find the position of `action`, then harvest
# every literal string at that position across VALUES tuples + ARRAY[...]
# constructs. False-positive risk is low because we lock to the action
# column index.
SQL_INSERT_AUDIT_RE = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?hive_audit_log\s*\(([^)]+)\)([\s\S]{0,4000}?);",
    re.IGNORECASE,
)
PY_AUDIT_INSERT_RE = re.compile(
    # client.table('hive_audit_log').insert({...})  OR  table("hive_audit_log").upsert({...})
    r"\.table\(\s*['\"]hive_audit_log['\"]\s*\)[\s\S]{0,400}?(?:insert|upsert)\s*\(\s*(\{[\s\S]{0,1500}?\})",
    re.IGNORECASE,
)
PY_AUDIT_ACTION_RE = re.compile(
    r"['\"]action['\"]\s*:\s*['\"]([a-z][a-z0-9_]*_[a-z0-9_]{1,40}|[a-z][a-z0-9_]{2,40})['\"]",
)


def _harvest_actions_from_sql(src: str) -> set:
    out = set()
    for m in SQL_INSERT_AUDIT_RE.finditer(src):
        col_list = [c.strip() for c in m.group(1).split(',')]
        try:
            action_idx = col_list.index('action')
        except ValueError:
            continue
        body = m.group(2)
        # ARRAY['a','b','c'] picker: harvest every literal inside ARRAY[...]
        for arr in re.finditer(r"ARRAY\s*\[([^\]]+)\]", body, re.IGNORECASE):
            for lit in re.findall(r"'([a-z][a-z0-9_]*)'", arr.group(1)):
                out.add(lit)
        # Plain VALUES (... 'action_name' ...): pick column at action_idx.
        # Crude positional scan: split VALUES rows on `(...)` and walk each.
        for row_m in re.finditer(r"\(([^)]{1,2000})\)", body):
            row = row_m.group(1)
            # Tokenise on commas at depth 0 (won't split inside nested parens)
            parts, depth, buf = [], 0, []
            for ch in row:
                if ch in '([': depth += 1
                elif ch in ')]': depth -= 1
                if ch == ',' and depth == 0:
                    parts.append(''.join(buf).strip()); buf = []
                else:
                    buf.append(ch)
            parts.append(''.join(buf).strip())
            if action_idx < len(parts):
                tok = parts[action_idx]
                lit = re.search(r"^'([a-z][a-z0-9_]*)'$", tok)
                if lit:
                    out.add(lit.group(1))
    return out


def _harvest_actions_from_py(src: str) -> set:
    out = set()
    for m in PY_AUDIT_INSERT_RE.finditer(src):
        payload = m.group(1)
        for am in PY_AUDIT_ACTION_RE.finditer(payload):
            out.add(am.group(1))
    return out


def check_action_icon_completeness() -> list[dict]:
    """Every action string written to hive_audit_log — whether by JS
    writeAuditLog, SQL INSERT in a migration, or Python seeder — should
    have an ACTION_ICON entry in hive.html so the audit log renders the
    action with a meaningful icon + label, not the generic dot.

    The original validator only scanned JS writeAuditLog calls. Walkthrough
    2026-05-13 surfaced an `assign` row rendered as a generic dot — the
    row was inserted by a seed SQL statement that bypassed the JS helper.
    This extension scans migration SQL + seeder Python so seed-side action
    names are also covered.
    """
    issues = []
    actions_written = set()
    # JS surface (HTML pages)
    for page in LIVE_PAGES:
        p = ROOT / page
        if p.exists():
            actions_written |= _harvest_actions_from_js(_read(p))
    # SQL migrations
    migrations_dir = ROOT / "supabase" / "migrations"
    if migrations_dir.exists():
        for sql_path in sorted(migrations_dir.glob("*.sql")):
            actions_written |= _harvest_actions_from_sql(_read(sql_path))
    # Python seeders
    seeders_dir = ROOT / "test-data-seeder" / "seeders"
    if seeders_dir.exists():
        for py_path in sorted(seeders_dir.glob("*.py")):
            actions_written |= _harvest_actions_from_py(_read(py_path))

    hive_src = _read(ROOT / ACTION_ICON_PAGE)
    # ACTION_ICON entries look like:  member_joined: { icon: '+', ... }
    icon_re = re.compile(r"^\s*([\w_]+)\s*:\s*\{[^}]*icon\s*:", re.MULTILINE)
    icon_keys = set(icon_re.findall(hive_src))

    for action in sorted(actions_written - icon_keys):
        issues.append({
            "check": "action_icon_missing",
            "page": ACTION_ICON_PAGE,
            "action": action,
            "reason": (
                f"writeAuditLog('{action}', ...) is used across the platform "
                f"but {ACTION_ICON_PAGE}'s ACTION_ICON map has no entry. "
                f"The audit log will render this event as a generic dot. "
                f"Add a row: `{action}: {{ icon: '...', color: '...', "
                f"label: '...' }}`."
            ),
        })
    return issues


LAYERS = [
    {"layer": "L1", "label": "UI status updates on lifecycle tables write to hive_audit_log"},
    {"layer": "L2", "label": "Every writeAuditLog action has an ACTION_ICON entry"},
]


def run() -> dict:
    issues = []
    issues.extend(check_lifecycle_audit_coverage())
    issues.extend(check_action_icon_completeness())
    failed = 1 if issues else 0
    passed = len(LAYERS) - failed
    return {
        "validator": "audit_trail_coverage",
        "total_checks": len(LAYERS),
        "passed": passed, "failed": failed, "warned": 0,
        "layers": LAYERS,
        "issues": issues,
        "warnings": [],
        "tracked_tables": sorted(LIFECYCLE_TABLES.keys()),
    }


def main() -> int:
    out = run()
    print(f"\nAudit Trail Coverage Validator ({len(out['layers'])}-layer)")
    print("=" * 60)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"][:20]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
        if len(out["issues"]) > 20:
            print(f"  ...and {len(out['issues']) - 20} more")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "audit_trail_coverage_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
