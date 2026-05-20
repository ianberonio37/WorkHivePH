"""validate_enterprise_unlock.py — Phase 5 of STRATEGIC_ROADMAP.

The three Phase 5 tracks land schema + edge-fn scaffolding in one migration.
This validator catches regressions that would silently break compliance
posture before the audits even begin.

Layers:
  L1  hive_retention_config table + hard_delete_expired_soft_deletes RPC + cron schedule
  L2  export_hive_data(uuid) RPC + export-hive-data edge fn (PDPA right-to-access)
  L3  auth_session_events table with the documented event_type CHECK
  L4  mfa_enrollments table + sso_configs table
  L5  plant-connections.html exists + supervisor gate + 4 panels (CMMS / sync /
      sensor topics / gateway audit)
  L6  canonical_sources registrations for the 6 new domains

Skills consulted:
  enterprise-compliance (PDPA Article 16 export + 30-day soft-delete window
    + audit retention)
  security (MFA secret never on this side; recovery codes hashed; SSO config
    locked to service-role + supervisor read)
  multitenant-engineer (every new table hive-scoped; auth_session_events
    supervisor-or-owner read pattern)
  architect (one validator per phase batch; each layer corresponds to one
    contract the phase promised)
"""
from __future__ import annotations
import json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent
MIGRATIONS = ROOT / "supabase" / "migrations"
EDGE_FN    = ROOT / "supabase" / "functions" / "export-hive-data" / "index.ts"
PLANT_HTML = ROOT / "plant-connections.html"

LAYERS = [
    {"layer": "L1", "label": "hive_retention_config + hard_delete RPC + daily cron schedule"},
    {"layer": "L2", "label": "export_hive_data RPC + export-hive-data edge fn (PDPA)"},
    {"layer": "L3", "label": "auth_session_events table with documented event_type set"},
    {"layer": "L4", "label": "mfa_enrollments + sso_configs scaffolding"},
    {"layer": "L5", "label": "plant-connections.html supervisor surface with 4 panels"},
    {"layer": "L6", "label": "canonical_sources registrations for Phase 5 domains"},
]

REQUIRED_EVENT_TYPES = [
    "login_success", "login_failed", "logout", "session_expired",
    "mfa_challenge_sent", "mfa_pass", "mfa_fail",
    "password_reset_requested", "password_changed", "new_device_detected",
]

REQUIRED_DOMAINS = [
    "hive_retention_config_table",
    "hard_delete_cron_rpc",
    "export_hive_data_rpc",
    "auth_session_events_table",
    "mfa_enrollments_table",
    "sso_configs_table",
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _all_migrations() -> str:
    if not MIGRATIONS.exists():
        return ""
    return "\n".join(_read(p) for p in sorted(MIGRATIONS.glob("*.sql")))


def run() -> dict:
    issues: list[dict] = []
    blob = _all_migrations()
    edge = _read(EDGE_FN)
    plant = _read(PLANT_HTML)

    # L1
    if "CREATE TABLE" not in blob or "hive_retention_config" not in blob:
        issues.append({"check": "l1_table", "layer": "L1",
                       "reason": "hive_retention_config CREATE TABLE not in any migration."})
    if "hard_delete_expired_soft_deletes" not in blob:
        issues.append({"check": "l1_rpc", "layer": "L1",
                       "reason": "hard_delete_expired_soft_deletes RPC not found."})
    if "hard-delete-soft-expired" not in blob:
        issues.append({"check": "l1_cron", "layer": "L1",
                       "reason": "pg_cron schedule 'hard-delete-soft-expired' not registered. PDPA evidence relies on the daily purge."})

    # L2
    if "export_hive_data" not in blob:
        issues.append({"check": "l2_rpc", "layer": "L2",
                       "reason": "export_hive_data RPC not found in any migration."})
    if not edge:
        issues.append({"check": "l2_edge", "layer": "L2",
                       "reason": "supabase/functions/export-hive-data/index.ts not present."})
    else:
        if "checkSupervisor" not in edge:
            issues.append({"check": "l2_edge_auth", "layer": "L2",
                           "reason": "export-hive-data edge fn missing checkSupervisor() — PDPA exports must be supervisor-gated."})
        if "export_hive_data" not in edge:
            issues.append({"check": "l2_edge_rpc_call", "layer": "L2",
                           "reason": "export-hive-data edge fn does not call db.rpc('export_hive_data', ...)."})

    # L3
    if "auth_session_events" not in blob:
        issues.append({"check": "l3_table", "layer": "L3",
                       "reason": "auth_session_events CREATE TABLE not found."})
    else:
        for evt in REQUIRED_EVENT_TYPES:
            if f"'{evt}'" not in blob:
                issues.append({"check": f"l3_event_{evt}", "layer": "L3",
                               "reason": f"auth_session_events.event_type CHECK is missing '{evt}'. Event coverage is incomplete; downstream dashboards will silently skip these events."})

    # L4
    if "mfa_enrollments" not in blob:
        issues.append({"check": "l4_mfa", "layer": "L4",
                       "reason": "mfa_enrollments CREATE TABLE not found."})
    if "sso_configs" not in blob:
        issues.append({"check": "l4_sso", "layer": "L4",
                       "reason": "sso_configs CREATE TABLE not found."})
    # Light guard: the TOTP secret must NOT live in mfa_enrollments. Detect a
    # column declaration (`totp_secret <type>`) rather than just the word in
    # a comment block.
    import re as _re
    if _re.search(r"^\s*totp_secret\s+\w", blob, _re.MULTILINE):
        issues.append({"check": "l4_secret_storage", "layer": "L4",
                       "reason": "totp_secret column found in a migration. TOTP secrets MUST live in Supabase Auth, not in mfa_enrollments. Remove the column."})

    # L5
    if not plant:
        issues.append({"check": "l5_page", "layer": "L5",
                       "reason": "plant-connections.html not found."})
    else:
        for needle in ("integration_configs", "external_sync", "sensor_topic_map", "gateway_audit_log"):
            if needle not in plant:
                issues.append({"check": f"l5_panel_{needle}", "layer": "L5",
                               "reason": f"plant-connections.html does not read from {needle}."})
        if "HIVE_ROLE !== 'supervisor'" not in plant:
            issues.append({"check": "l5_gate", "layer": "L5",
                           "reason": "plant-connections.html does not gate on HIVE_ROLE === 'supervisor'."})

    # L6
    for d in REQUIRED_DOMAINS:
        if f"'{d}'" not in blob:
            issues.append({"check": f"l6_{d}", "layer": "L6",
                           "reason": f"canonical_sources missing the '{d}' registration."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "enterprise_unlock",
            "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nEnterprise Unlock Validator ({len(out['layers'])}-layer)")
    print("=" * 60)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "enterprise_unlock_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
