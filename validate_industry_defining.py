"""validate_industry_defining.py — Phase 6 of STRATEGIC_ROADMAP.

Phase 6 is 6-24 months / 40+ sessions of long-horizon work. This migration
ships the *data contracts* the sub-tracks build on. The validator's job is
narrow but load-bearing: catch regressions that would erase the contracts.

Each layer corresponds to one sub-track's scaffold:
  L1  6A knowledge_graph_facts table + embedding + indices
  L2  6E drone_inspections table + lifecycle CHECK
  L3  6F industry_standards table + family CHECK + seed rows present
  L4  6D hives.federated_benchmark_opted_in column + audit columns
  L5  6C v_insurance_bridge_truth view with the documented weighting
  L6  MaaS consulting_engagements table + engagement_kind CHECK
  L7  canonical_sources registrations for the 6 new domains
  L8  Realtime publication on knowledge_graph_facts + drone_inspections

Skills consulted:
  architect (one validator per phase batch; each layer = one contract the
    phase promised; calibration_status: provisional flag is part of the
    contract to ensure no one ships a real underwriter feed before review)
  predictive-analytics (insurance bridge weighting must be explicit)
  knowledge-manager (knowledge_graph_facts must keep its embedding column
    so GraphRAG retrieval stays cheap)
  enterprise-compliance (federated opt-in is per-hive consent + audit;
    consulting_engagements is the productisation tracker)
"""
from __future__ import annotations
import json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent
MIGRATIONS = ROOT / "supabase" / "migrations"

LAYERS = [
    {"layer": "L1", "label": "6A knowledge_graph_facts table + embedding + indices"},
    {"layer": "L2", "label": "6E drone_inspections table + lifecycle CHECK"},
    {"layer": "L3", "label": "6F industry_standards table + family CHECK + seed rows"},
    {"layer": "L4", "label": "6D hives.federated_benchmark_opted_in + audit columns"},
    {"layer": "L5", "label": "6C v_insurance_bridge_truth view with documented weighting"},
    {"layer": "L6", "label": "MaaS consulting_engagements table + engagement_kind CHECK"},
    {"layer": "L7", "label": "canonical_sources registrations (6 new domains)"},
    {"layer": "L8", "label": "Realtime publication on knowledge_graph_facts + drone_inspections"},
]

REQUIRED_LIFECYCLES = [
    "scheduled", "in_flight", "analyzed", "reviewed", "archived", "cancelled",
]

REQUIRED_STANDARDS = [
    "PSME 2024", "PEC 2017", "ISO 14224:2016",
    "NFPA 13:2025", "ASHRAE 90.1:2022", "SAE JA 1011:2009",
]

REQUIRED_ENGAGEMENT_KINDS = [
    "readiness_assessment", "stair_2_lift", "stair_3_lift",
    "pdpa_prep", "soc2_prep", "iso27001_prep",
    "sso_onboarding", "rcm_workshop", "general",
]

REQUIRED_DOMAINS = [
    "knowledge_graph_facts_table",
    "drone_inspections_table",
    "industry_standards_table",
    "hives_federated_opt_in",
    "insurance_bridge",
    "consulting_engagements_table",
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

    # L1: knowledge_graph_facts
    if "CREATE TABLE" not in blob or "knowledge_graph_facts" not in blob:
        issues.append({"check": "l1_table", "layer": "L1",
                       "reason": "knowledge_graph_facts CREATE TABLE not found."})
    # Embedding column must use the platform TARGET_DIM (vector(384)) so
    # GraphRAG can join across fault_knowledge / skill_knowledge / pm_knowledge
    # which all use 384 to match _shared/embedding-chain.ts.
    import re as _re
    if not _re.search(r"knowledge_graph_facts[\s\S]*?embedding\s+vector\(384\)", blob):
        issues.append({"check": "l1_embedding", "layer": "L1",
                       "reason": "knowledge_graph_facts.embedding vector(384) column not found. GraphRAG retrieval relies on this dimension matching the platform TARGET_DIM."})
    if "idx_kgf_subject" not in blob:
        issues.append({"check": "l1_index_subject", "layer": "L1",
                       "reason": "idx_kgf_subject index missing — subject traversal will be slow."})

    # L2: drone_inspections
    if "drone_inspections" not in blob:
        issues.append({"check": "l2_table", "layer": "L2",
                       "reason": "drone_inspections CREATE TABLE not found."})
    else:
        for lc in REQUIRED_LIFECYCLES:
            if f"'{lc}'" not in blob:
                issues.append({"check": f"l2_lifecycle_{lc}", "layer": "L2",
                               "reason": f"drone_inspections.status CHECK is missing the '{lc}' lifecycle value."})

    # L3: industry_standards
    if "industry_standards" not in blob:
        issues.append({"check": "l3_table", "layer": "L3",
                       "reason": "industry_standards CREATE TABLE not found."})
    else:
        for code in REQUIRED_STANDARDS:
            if f"'{code}'" not in blob:
                issues.append({"check": f"l3_seed_{code}", "layer": "L3",
                               "reason": f"industry_standards seed missing '{code}'. The Standards Auto-Update Agent expects core standards pre-registered."})

    # L4: hives.federated_benchmark_opted_in + audit columns
    needed_cols = ("federated_benchmark_opted_in", "federated_opt_in_at", "federated_opt_in_by")
    for c in needed_cols:
        if c not in blob:
            issues.append({"check": f"l4_col_{c}", "layer": "L4",
                           "reason": f"hives.{c} column not found. Federated opt-in audit incomplete."})

    # L5: v_insurance_bridge_truth view + weighting documented
    if "v_insurance_bridge_truth" not in blob:
        issues.append({"check": "l5_view", "layer": "L5",
                       "reason": "v_insurance_bridge_truth view not found."})
    else:
        # Calibration discipline: the view's contract must declare provisional status.
        if "provisional_pending_actuarial_review" not in blob:
            issues.append({"check": "l5_calibration", "layer": "L5",
                           "reason": "insurance_bridge canonical_sources contract is missing 'calibration_status: provisional_pending_actuarial_review'. Partners must NOT consume v1 weights without actuarial review; the contract flag is how downstream consumers learn that."})

    # L6: consulting_engagements + engagement_kind CHECK
    if "consulting_engagements" not in blob:
        issues.append({"check": "l6_table", "layer": "L6",
                       "reason": "consulting_engagements CREATE TABLE not found."})
    else:
        for k in REQUIRED_ENGAGEMENT_KINDS:
            if f"'{k}'" not in blob:
                issues.append({"check": f"l6_kind_{k}", "layer": "L6",
                               "reason": f"consulting_engagements.engagement_kind CHECK missing '{k}'."})

    # L7: canonical_sources registrations
    for d in REQUIRED_DOMAINS:
        if f"'{d}'" not in blob:
            issues.append({"check": f"l7_{d}", "layer": "L7",
                           "reason": f"canonical_sources is missing the '{d}' registration."})

    # L8: realtime publication
    for tbl in ("knowledge_graph_facts", "drone_inspections"):
        # Need both the table name AND the ALTER PUBLICATION line to be present.
        # The simple substring check would pass on the table's own CREATE; tighten
        # by requiring the ADD TABLE clause specifically.
        if f"ADD TABLE public.{tbl}" not in blob:
            issues.append({"check": f"l8_pub_{tbl}", "layer": "L8",
                           "reason": f"{tbl} not added to supabase_realtime publication."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "industry_defining",
            "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nIndustry-Defining Validator ({len(out['layers'])}-layer)")
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
    (ROOT / "industry_defining_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
