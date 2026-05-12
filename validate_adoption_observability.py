"""validate_adoption_observability.py — Phase 3.6 of STRATEGIC_ROADMAP.

The Adoption Observability layer is the platform's *self-measurement*. If
it silently regresses (table renamed, RPC dropped, supervisor card removed,
intent column lost) the supervisor loses the smoke alarm AND we lose the
change-management story that distinguishes WorkHive from imported CMMS.

Layers:
  L1  hive_adoption_score table + 2 RPCs (compute + get_current) + v_adoption_truth view + hives.intent column
  L2  Supervisor Engagement Card: #adoption-card element + loadAdoptionCard() call
  L3  Onboarding stepper: #onboarding-card element + loadOnboardingCard() + onboarding.js loaded
  L4  Intent capture: #intent-capture modal + maybeShowIntentCapture() call
  L5  hive_adoption_score in supabase_realtime publication
  L6  canonical_sources registrations (v_adoption_truth + RPCs + intent column)

Skills consulted:
  architect (canonical-anchor symmetry: every new table → registered)
  analytics-engineer (every new view → canonical entry → consumed by UI)
  multitenant-engineer (RLS lockdown verified by other gates; this one
    checks the surface bindings)
  qa-tester (the supervisor card is the change-management product surface;
    a missing element is a regression that wipes out Phase 3's reason to exist)
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent
MIGRATIONS = ROOT / "supabase" / "migrations"
HIVE_HTML  = ROOT / "hive.html"
ONBOARDING_JS = ROOT / "onboarding.js"

LAYERS = [
    {"layer": "L1", "label": "hive_adoption_score + 2 RPCs + v_adoption_truth + hives.intent migration"},
    {"layer": "L2", "label": "Supervisor Engagement Card on hive.html"},
    {"layer": "L3", "label": "Onboarding stepper on hive.html (+ onboarding.js loaded)"},
    {"layer": "L4", "label": "Intent capture modal on hive.html"},
    {"layer": "L5", "label": "hive_adoption_score in supabase_realtime publication"},
    {"layer": "L6", "label": "canonical_sources registrations (view + RPCs + intent column)"},
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
    hive_src = _read(HIVE_HTML)
    onboard_src = _read(ONBOARDING_JS)

    # L1: schema + RPCs + view + intent column
    if "CREATE TABLE" not in blob or "hive_adoption_score" not in blob:
        issues.append({"check": "l1_table", "layer": "L1",
                       "reason": "hive_adoption_score CREATE TABLE not found in any migration."})
    if "compute_adoption_risk" not in blob:
        issues.append({"check": "l1_rpc_compute", "layer": "L1",
                       "reason": "compute_adoption_risk RPC not found."})
    if "get_adoption_risk_current" not in blob:
        issues.append({"check": "l1_rpc_get", "layer": "L1",
                       "reason": "get_adoption_risk_current RPC not found."})
    if "v_adoption_truth" not in blob:
        issues.append({"check": "l1_view", "layer": "L1",
                       "reason": "v_adoption_truth view not found."})
    if "hives" not in blob or "intent" not in blob:
        issues.append({"check": "l1_intent", "layer": "L1",
                       "reason": "hives.intent column not found in any migration."})

    # L2: supervisor card
    if "id=\"adoption-card\"" not in hive_src and "id='adoption-card'" not in hive_src:
        issues.append({"check": "l2_card_element", "layer": "L2",
                       "reason": "hive.html does not contain #adoption-card element."})
    if "loadAdoptionCard(" not in hive_src:
        issues.append({"check": "l2_card_load", "layer": "L2",
                       "reason": "hive.html does not call loadAdoptionCard() in init."})

    # L3: onboarding stepper
    if "id=\"onboarding-card\"" not in hive_src and "id='onboarding-card'" not in hive_src:
        issues.append({"check": "l3_card_element", "layer": "L3",
                       "reason": "hive.html does not contain #onboarding-card element."})
    if "loadOnboardingCard(" not in hive_src:
        issues.append({"check": "l3_card_load", "layer": "L3",
                       "reason": "hive.html does not call loadOnboardingCard() in init."})
    if "onboarding.js" not in hive_src:
        issues.append({"check": "l3_script", "layer": "L3",
                       "reason": "hive.html does not load <script src=\"onboarding.js\">."})
    if not onboard_src or "whOnboardingProgress" not in onboard_src or "whRenderOnboardingCard" not in onboard_src:
        issues.append({"check": "l3_helper", "layer": "L3",
                       "reason": "onboarding.js missing or does not expose whOnboardingProgress + whRenderOnboardingCard."})

    # L4: intent capture
    if "id=\"intent-capture\"" not in hive_src and "id='intent-capture'" not in hive_src:
        issues.append({"check": "l4_modal", "layer": "L4",
                       "reason": "hive.html does not contain #intent-capture modal."})
    if "maybeShowIntentCapture(" not in hive_src:
        issues.append({"check": "l4_invoke", "layer": "L4",
                       "reason": "hive.html does not call maybeShowIntentCapture() in init."})

    # L5: realtime publication
    if "ALTER PUBLICATION supabase_realtime" not in blob or "hive_adoption_score" not in blob:
        issues.append({"check": "l5", "layer": "L5",
                       "reason": "hive_adoption_score is not added to supabase_realtime publication."})

    # L6: canonical_sources registrations
    needed_domains = [
        "hive_adoption_score",
        "hive_adoption_score_table",
        "compute_adoption_risk_rpc",
        "get_adoption_risk_current_rpc",
        "hives_intent",
    ]
    for d in needed_domains:
        if f"'{d}'" not in blob:
            issues.append({"check": f"l6_{d}", "layer": "L6",
                           "reason": f"canonical_sources is missing the '{d}' registration."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "adoption_observability",
            "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nAdoption Observability Validator ({len(out['layers'])}-layer)")
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
    (ROOT / "adoption_observability_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
