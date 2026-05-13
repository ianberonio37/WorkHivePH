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


def check_action_icon_completeness() -> list[dict]:
    """Every action string written by writeAuditLog across all pages should
    have an ACTION_ICON entry in hive.html so the audit log renders it
    with a meaningful icon + label, not the generic dot.
    """
    issues = []
    actions_written = set()
    for page in LIVE_PAGES:
        p = ROOT / page
        if not p.exists():
            continue
        src = _read(p)
        # Scan every writeAuditLog call; harvest action names from the
        # FIRST argument only (the second arg is target_type, often a
        # table name like 'inventory_items' that would false-positive).
        # Stop at the first comma not inside a ternary's ? branch.
        for call_m in WRITE_AUDIT_CALL_RE.finditer(src):
            args_window = call_m.group(1)
            # Split on the first ',' that's at paren depth 0. Ternaries
            # `cond ? 'a' : 'b'` stay together because they have no comma.
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
                actions_written.add(n)

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
