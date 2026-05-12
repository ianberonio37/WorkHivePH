"""validate_amc.py - Phase 1.9 of STRATEGIC_ROADMAP.md.

Architectural contract gate for the Autonomous Maintenance Crew (AMC). The
AMC writes one briefing per (hive, shift_date) at 06:00 PHT. If any of its
moving parts drift (schema, realtime, canonical anchor, cost logging) the
daily brief silently stops appearing in alert-hub.html without raising a
runtime error.

Layers:
  L1  amc_briefings table migration exists + UNIQUE(hive_id, shift_date) clause
  L2  amc-orchestrator edge fn calls callAI AND logAICost
  L3  amc_briefings is in supabase_realtime publication
  L4  alert-hub.html subscribes to amc_briefings via postgres_changes
  L5  amc_briefings is registered in canonical_sources

Skills consulted:
  architect (single-row-per-shift contract, canonical anchor pattern)
  ai-engineer (every callAI must log cost - PRODUCTION_FIXES #54)
  realtime-engineer (subscription requires publication)
  notifications (alert-hub.html is the supervisor surface; without the
    subscription the supervisor never sees today's brief)
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent
MIGRATION_GLOB = "supabase/migrations/*_amc_briefings.sql"
EDGE_FN        = ROOT / "supabase" / "functions" / "amc-orchestrator" / "index.ts"
ALERT_HUB      = ROOT / "alert-hub.html"

LAYERS = [
    {"layer": "L1", "label": "amc_briefings migration with UNIQUE(hive_id, shift_date)"},
    {"layer": "L2", "label": "amc-orchestrator calls callAI AND logAICost"},
    {"layer": "L3", "label": "amc_briefings in supabase_realtime publication"},
    {"layer": "L4", "label": "alert-hub.html subscribes to amc_briefings"},
    {"layer": "L5", "label": "amc_briefings registered in canonical_sources"},
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _find_migration() -> Path | None:
    matches = sorted(ROOT.glob(MIGRATION_GLOB))
    return matches[-1] if matches else None


def check_migration() -> list[dict]:
    m = _find_migration()
    if not m:
        return [{"check": "migration_exists",
                 "reason": "No supabase/migrations/*_amc_briefings.sql found."}]
    src = _read(m)
    issues: list[dict] = []
    if "CREATE TABLE" not in src or "amc_briefings" not in src:
        issues.append({"check": "table_create",
                       "reason": f"{m.name} does not CREATE TABLE amc_briefings."})
    if "UNIQUE" not in src or "shift_date" not in src:
        issues.append({"check": "unique_per_shift",
                       "reason": f"{m.name} is missing UNIQUE(hive_id, shift_date). "
                                 f"Without it, cron retries duplicate the brief."})
    return issues


def check_cost_logging() -> list[dict]:
    if not EDGE_FN.exists():
        return [{"check": "edge_fn_exists",
                 "reason": "supabase/functions/amc-orchestrator/index.ts not found."}]
    src = _read(EDGE_FN)
    issues: list[dict] = []
    if "callAI(" not in src:
        issues.append({"check": "callAI_present",
                       "reason": "amc-orchestrator does not call callAI(). The brief "
                                 "is then deterministic-only and the LLM enrichment "
                                 "step is broken."})
    if "logAICost(" not in src:
        issues.append({"check": "logAICost_present",
                       "reason": "amc-orchestrator calls callAI without logAICost. "
                                 "Cost observability is mandatory (PRODUCTION_FIXES #54)."})
    return issues


def check_realtime_publication() -> list[dict]:
    m = _find_migration()
    if not m:
        return []  # already flagged by L1
    src = _read(m)
    if "ALTER PUBLICATION supabase_realtime" not in src or "amc_briefings" not in src:
        return [{"check": "publication_add",
                 "reason": "amc_briefings is not added to supabase_realtime. "
                           "alert-hub.html will subscribe and silently never fire."}]
    return []


def check_alert_hub_subscription() -> list[dict]:
    if not ALERT_HUB.exists():
        return [{"check": "alert_hub_exists",
                 "reason": "alert-hub.html not found."}]
    src = _read(ALERT_HUB)
    if "amc_briefings" not in src or "postgres_changes" not in src:
        return [{"check": "subscription_present",
                 "reason": "alert-hub.html does not subscribe to amc_briefings via "
                           "postgres_changes. Supervisor will not see the brief flip "
                           "from pending to approved without a manual refresh."}]
    return []


def check_canonical_anchor() -> list[dict]:
    m = _find_migration()
    if not m:
        return []
    src = _read(m)
    if "canonical_sources" not in src or "amc_brief" not in src:
        return [{"check": "canonical_anchor",
                 "reason": "amc_briefings is not registered in canonical_sources. "
                           "Other agents asking 'where do daily briefs live?' will get "
                           "no answer."}]
    return []


def run() -> dict:
    issues: list[dict] = []
    issues.extend(check_migration())
    issues.extend(check_cost_logging())
    issues.extend(check_realtime_publication())
    issues.extend(check_alert_hub_subscription())
    issues.extend(check_canonical_anchor())

    failed = 0
    issue_checks = {i["check"] for i in issues}
    check_to_layer = {
        "migration_exists": 0, "table_create": 0, "unique_per_shift": 0,
        "edge_fn_exists": 1, "callAI_present": 1, "logAICost_present": 1,
        "publication_add": 2,
        "alert_hub_exists": 3, "subscription_present": 3,
        "canonical_anchor": 4,
    }
    fail_layers = {check_to_layer[c] for c in issue_checks if c in check_to_layer}
    failed = len(fail_layers)
    passed = len(LAYERS) - failed

    return {
        "validator": "amc",
        "total_checks": len(LAYERS),
        "passed": passed,
        "failed": failed,
        "warned": 0,
        "layers": LAYERS,
        "issues": issues,
        "warnings": [],
    }


def main() -> int:
    out = run()
    print(f"\nAMC Validator ({len(out['layers'])}-layer)")
    print("=" * 55)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "amc_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
