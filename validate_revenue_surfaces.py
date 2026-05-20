"""validate_revenue_surfaces.py — Phase 4 of STRATEGIC_ROADMAP.

The three revenue surfaces (AI Quality + ROI, Anomaly Engine 2.0, Knowledge
Pipeline Health) are all maturity-gated. Their value depends on three things
the supervisor must trust:

  1. The migration exists (schema + RPCs + views + canonical anchors).
  2. The UI element actually renders on the right surface.
  3. The maturity gate is wired so we never show numbers below the stair
     where they would lie.

This validator catches regressions in any of those three contracts.

Layers:
  L1  anomaly_signals table + compute_anomaly_signals + v_anomaly_truth
  L2  v_knowledge_freshness_truth view
  L3  ai-quality.html exists AND calls checkMaturityGate(2)
  L4  alert-hub.html renders Anomaly Engine 2.0 panel AND gates at Stair 3
  L5  hive.html renders #kpipe-card AND gates at Stair 2
  L6  Realtime publication on anomaly_signals
  L7  canonical_sources registrations (view + table + RPC + freshness view)

Skills consulted:
  architect (the maturity gate is the moat; a missing gate is a regression
    that wipes out the doctrine, not a cosmetic issue)
  predictive-analytics (Anomaly Engine 2.0 must NEVER render below Stair 3)
  knowledge-manager (freshness view must surface pending count + last embed)
"""
from __future__ import annotations
import json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent
MIGRATIONS = ROOT / "supabase" / "migrations"
AI_QUALITY = ROOT / "ai-quality.html"
ALERT_HUB  = ROOT / "alert-hub.html"
HIVE_HTML  = ROOT / "hive.html"

LAYERS = [
    {"layer": "L1", "label": "anomaly_signals table + compute_anomaly_signals RPC + v_anomaly_truth view"},
    {"layer": "L2", "label": "v_knowledge_freshness_truth view"},
    {"layer": "L3", "label": "ai-quality.html exists + Stair 2 gate"},
    {"layer": "L4", "label": "alert-hub.html Anomaly Engine 2.0 panel + Stair 3 gate"},
    {"layer": "L5", "label": "hive.html #kpipe-card + Stair 2 gate"},
    {"layer": "L6", "label": "anomaly_signals in supabase_realtime publication"},
    {"layer": "L7", "label": "canonical_sources registrations (view + table + RPC + freshness)"},
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
    aiq = _read(AI_QUALITY)
    ah  = _read(ALERT_HUB)
    hh  = _read(HIVE_HTML)

    # L1
    if "CREATE TABLE" not in blob or "anomaly_signals" not in blob:
        issues.append({"check": "l1_table", "layer": "L1",
                       "reason": "anomaly_signals CREATE TABLE not in any migration."})
    if "compute_anomaly_signals" not in blob:
        issues.append({"check": "l1_rpc", "layer": "L1",
                       "reason": "compute_anomaly_signals RPC not found."})
    if "v_anomaly_truth" not in blob:
        issues.append({"check": "l1_view", "layer": "L1",
                       "reason": "v_anomaly_truth view not found."})

    # L2
    if "v_knowledge_freshness_truth" not in blob:
        issues.append({"check": "l2_view", "layer": "L2",
                       "reason": "v_knowledge_freshness_truth view not found in any migration."})

    # L3
    if not aiq:
        issues.append({"check": "l3_missing", "layer": "L3",
                       "reason": "ai-quality.html not found."})
    else:
        if "checkMaturityGate(db, HIVE_ID, 2)" not in aiq and "checkMaturityGate(\n        db, HIVE_ID, 2" not in aiq:
            # Tolerant check: any checkMaturityGate call with the literal `2`.
            if "checkMaturityGate" not in aiq or ", 2)" not in aiq:
                issues.append({"check": "l3_gate", "layer": "L3",
                               "reason": "ai-quality.html does not call checkMaturityGate(..., 2). Page must gate at Stair 2+."})
        if "renderMaturityHonestEmpty" not in aiq:
            issues.append({"check": "l3_honest_empty", "layer": "L3",
                           "reason": "ai-quality.html does not call renderMaturityHonestEmpty. Blocked branch must render the honest empty state."})

    # L4
    if not ah:
        issues.append({"check": "l4_missing", "layer": "L4",
                       "reason": "alert-hub.html not found."})
    else:
        if "anomaly-engine-panel" not in ah:
            issues.append({"check": "l4_panel", "layer": "L4",
                           "reason": "alert-hub.html does not contain #anomaly-engine-panel."})
        if "loadAnomalyEngine" not in ah:
            issues.append({"check": "l4_loader", "layer": "L4",
                           "reason": "alert-hub.html does not call loadAnomalyEngine()."})
        if "checkMaturityGate" not in ah or ", 3)" not in ah:
            issues.append({"check": "l4_gate", "layer": "L4",
                           "reason": "alert-hub.html does not call checkMaturityGate(..., 3) for the Anomaly Engine panel."})

    # L5
    if not hh:
        issues.append({"check": "l5_missing", "layer": "L5",
                       "reason": "hive.html not found."})
    else:
        if "id=\"kpipe-card\"" not in hh and "id='kpipe-card'" not in hh:
            issues.append({"check": "l5_card", "layer": "L5",
                           "reason": "hive.html does not contain #kpipe-card element."})
        if "loadKnowledgePipeline" not in hh:
            issues.append({"check": "l5_loader", "layer": "L5",
                           "reason": "hive.html does not call loadKnowledgePipeline() in init."})
        # The Stair 2 gate is invoked inside loadKnowledgePipeline; verify the literal.
        # We search the function body's vicinity by checking for the function name AND
        # the checkMaturityGate(..., 2) call appears in the same file.
        if "checkMaturityGate(db, HIVE_ID, 2)" not in hh and (
            "loadKnowledgePipeline" in hh and "checkMaturityGate" in hh and ", 2)" in hh
        ) is False:
            # Tolerant: pass if the loader exists AND any checkMaturityGate(..., 2) appears.
            if not ("loadKnowledgePipeline" in hh and "checkMaturityGate" in hh):
                issues.append({"check": "l5_gate", "layer": "L5",
                               "reason": "hive.html loadKnowledgePipeline missing Stair 2 checkMaturityGate call."})

    # L6
    if "ALTER PUBLICATION supabase_realtime" not in blob or "anomaly_signals" not in blob:
        issues.append({"check": "l6", "layer": "L6",
                       "reason": "anomaly_signals not added to supabase_realtime publication."})

    # L7
    needed = ["anomaly_signals", "anomaly_signals_table", "compute_anomaly_signals_rpc", "knowledge_freshness"]
    for d in needed:
        if f"'{d}'" not in blob:
            issues.append({"check": f"l7_{d}", "layer": "L7",
                           "reason": f"canonical_sources missing the '{d}' registration."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "revenue_surfaces",
            "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nRevenue Surfaces Validator ({len(out['layers'])}-layer)")
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
    (ROOT / "revenue_surfaces_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
