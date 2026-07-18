#!/usr/bin/env python3
"""
detect_redundant_displays.py  --  Phase C of the INTERACTIVE_LINEAGE_ROADMAP.

Answers Ian's Q3: "is it redundant to display these?" -- machine-confirms which
surfaces render the SAME underlying value, then attaches an opinionated verdict
(engine proposes; Ian disposes -- no UI collapsed without sign-off).

Reliable value-identity signal (NOT loose token matching): two surfaces are
"showing the same value" when they read the same TERMINUS TABLE (direct or via a
canonical view). Built from canonical_registry adjacency -- the same graph Phase A
uses -- so it cannot drift from the lineage map.

Layers:
  1. TABLE value-identity   : table displayed on >= MIN_PAGES surfaces.
  2. KPI metric redundancy  : kpi_source_registry metric -> its consumer surfaces.
  3. SEMANTIC clusters      : ia_inventory_corpus.json info-units (the survey's map).
Each cluster carries a VERDICT (KEEP / RELABEL / CONSOLIDATE / FEDERATE) + canonical
home + UX-law cite + reason, from the roadmap's section-3 synthesis.

Outputs: redundant_displays.json + redundant_displays.md
Run:     python tools/detect_redundant_displays.py
"""
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "canonical_registry.json")
KPI = os.path.join(ROOT, "kpi_source_registry.json")
CORPUS = os.path.join(ROOT, "ia_inventory_corpus.json")
OUT_JSON = os.path.join(ROOT, "redundant_displays.json")
OUT_MD = os.path.join(ROOT, "redundant_displays.md")

MIN_PAGES = 4

VIEW_BASE_OVERRIDE = {
    "v_risk_truth": "asset_risk_scores", "v_pm_compliance_truth": "pm_completions",
    "v_anomaly_truth": "anomaly_signals", "v_sensor_truth": "sensor_readings",
    "v_sensor_recent": "sensor_readings", "v_asset_truth": "asset_nodes",
    "v_fmea_truth": "rcm_fmea_modes", "v_rcm_truth": "rcm_strategies",
    "v_pm_scope_items_truth": "pm_scope_items", "v_inventory_items_truth": "inventory_items",
    "v_logbook_truth": "logbook", "v_worker_truth": "hive_members",
}

# Infra/context tables: read widely for CONTEXT or audit, not redundant KPI restatement.
INFRA_TABLES = {"hive_audit_log", "hive_members", "automation_log", "v_worker_truth"}

# Opinionated verdicts from the roadmap section-3 synthesis. Keyed by terminus table.
VERDICTS = {
    "asset_risk_scores": {"verdict": "RELABEL", "canonical_home": "predictive.html",
        "ux_law": "DRY (one source) + NN/g #4 Consistency",
        "why": "Same v_risk_truth shown 4+ ways (predictive=plan, asset-hub=badge, shift-brain=today, alert-hub=triage). DRY-correct; relabel by JOB + cross-link. Enforce top_risk_band everywhere."},
    "pm_scope_items": {"verdict": "KEEP+DEEPLINK", "canonical_home": "pm-scheduler.html",
        "ux_law": "NN/g #6 Recognition-over-Recall",
        "why": "PM due/overdue on 5 surfaces, all v_pm_scope_items_truth. Reinforcement is fine; deep-link all to pm-scheduler; enforce is_overdue/is_due_soon."},
    "pm_completions": {"verdict": "KEEP", "canonical_home": "pm-scheduler.html",
        "ux_law": "NN/g #6 Recognition-over-Recall",
        "why": "PM compliance ledger read on 6 pages for context; one canonical RPC get_pm_compliance_smrp. Keep, ensure single derivation."},
    "inventory_items": {"verdict": "KEEP", "canonical_home": "inventory.html",
        "ux_law": "NN/g #6 + DRY",
        "why": "Stock shown on 7 surfaces (alert-hub stock alert, logbook parts picker, hive low-stock) = legitimate context; all read v_inventory_items_truth.is_low_stock. Keep."},
    "asset_nodes": {"verdict": "KEEP", "canonical_home": "asset-hub.html",
        "ux_law": "Jakob's Law (consistency)",
        "why": "Asset registry referenced on 7 pages (pickers, links) = necessary context, one v_asset_truth. Keep."},
    "logbook": {"verdict": "KEEP+RELABEL", "canonical_home": "logbook.html",
        "ux_law": "NN/g #6 + Norman Gulf of Evaluation",
        "why": "Fault history on 9 surfaces (timeline, context panels) = the platform's spine; highest blast radius. Keep, but Phase-D should make its cross-page effect VISIBLE."},
    "hive_audit_log": {"verdict": "KEEP-INFRA", "canonical_home": "audit-log.html",
        "ux_law": "n/a (audit trail)",
        "why": "Append-only compliance trail written by 12 surfaces; audit-log.html is the canonical viewer. Not a KPI redundancy."},
    # --- 8 clusters disposed KEEP-context by Ian (2026-06-29): legitimate context reads
    #     (pickers / cross-links / membership / status), reversible if a restatement surfaces. ---
    "hive_members": {"verdict": "KEEP-context", "canonical_home": "hive.html", "ux_law": "context read",
        "why": "Membership/role read for gating + display across pages; one v_worker_truth. KEEP (Ian 2026-06-29)."},
    "pm_assets": {"verdict": "KEEP-context", "canonical_home": "pm-scheduler.html", "ux_law": "context read",
        "why": "PM asset list referenced by pickers; KEEP (Ian 2026-06-29)."},
    "external_sync": {"verdict": "KEEP-context", "canonical_home": "plant-connections.html", "ux_law": "context read",
        "why": "CMMS/sensor sync status shown where relevant; KEEP (Ian 2026-06-29)."},
    "skill_badges": {"verdict": "KEEP-context", "canonical_home": "skillmatrix.html", "ux_law": "context read",
        "why": "Skill badges read by resume/assistant/hive for context; KEEP (Ian 2026-06-29)."},
    "marketplace_disputes": {"verdict": "KEEP-context", "canonical_home": "marketplace-admin.html", "ux_law": "context read",
        "why": "Marketplace-family context; candidate for a unified admin surface later. KEEP (Ian 2026-06-29)."},
    "marketplace_orders": {"verdict": "KEEP-context", "canonical_home": "marketplace.html", "ux_law": "context read",
        "why": "Order state across marketplace-family pages; KEEP (Ian 2026-06-29)."},
    "marketplace_sellers": {"verdict": "KEEP-context", "canonical_home": "marketplace-seller.html", "ux_law": "context read",
        "why": "Seller profile/tier read across marketplace-family; KEEP (Ian 2026-06-29)."},
    "project_links": {"verdict": "KEEP-context", "canonical_home": "project-manager.html", "ux_law": "context read",
        "why": "Project↔entity links read where projects surface; KEEP (Ian 2026-06-29)."},
    "projects": {"verdict": "KEEP-context", "canonical_home": "project-manager.html", "ux_law": "context read",
        "why": "Project name/status read as FK context on child-entity pages (a WO's / part's / PM's parent project on logbook/inventory/pm-scheduler); project-manager.html is the authoritative home. Same class as project_links above — legitimate context, not a restatement. KEEP-context (bug-hunt 2026-07-18; reversible if a true restatement surfaces)."},
    "marketplace_listings": {"verdict": "KEEP", "canonical_home": "marketplace.html",
        "ux_law": "DRY",
        "why": "Listings surfaced on 6 marketplace-family pages + asset-hub spares; one v_marketplace_listings_truth. Keep."},
}


def base(n, tables):
    if n in VIEW_BASE_OVERRIDE:
        return VIEW_BASE_OVERRIDE[n]
    m = re.match(r"^v_(.+?)(_truth)?$", n)
    return m.group(1) if m and m.group(1) in tables else n


def main():
    reg = json.load(open(REG, encoding="utf-8"))
    tables, surfaces = reg["tables"], reg["surfaces"]
    kpi = json.load(open(KPI, encoding="utf-8")).get("metrics", {})

    disp = defaultdict(set)
    via_view = defaultdict(set)
    for page, s in surfaces.items():
        pid = page[:-5] if page.endswith(".html") else page
        for node in s.get("tables_read", []):
            b = base(node, tables)
            disp[b].add(pid)
            if node != b:
                via_view[b].add(node)

    clusters = []
    for t, pages in disp.items():
        if len(pages) < MIN_PAGES:
            continue
        v = VERDICTS.get(t, {"verdict": "REVIEW", "canonical_home": "?",
                             "ux_law": "—",
                             "why": "Displayed on %d surfaces; no curated verdict yet — review whether each read is context (KEEP) or restatement (CONSOLIDATE)." % len(pages)})
        clusters.append({
            "terminus_table": t,
            "is_infra": t in INFRA_TABLES,
            "display_pages": sorted(pages),
            "page_count": len(pages),
            "via_canonical_views": sorted(via_view.get(t, set())),
            **v,
        })
    clusters.sort(key=lambda c: (-c["page_count"]))

    # KPI-metric redundancy layer
    kpi_clusters = []
    for metric, meta in kpi.items():
        consumers = [c for c in meta.get("consumers", []) if c.endswith(".html")]
        if len(consumers) >= 2:
            kpi_clusters.append({
                "metric": metric, "canonical_source": meta.get("allowed_sources"),
                "signal": meta.get("required_signal"), "consumer_pages": consumers,
                "verdict": "KEEP (single-source enforced)",
                "why": "kpi_source_registry already pins one derivation + forbids drift patterns. Redundancy is safe."})

    semantic_n = None
    if os.path.exists(CORPUS):
        try:
            corpus = json.load(open(CORPUS, encoding="utf-8"))
            semantic_n = len(corpus) if isinstance(corpus, list) else len(corpus.get("units", corpus))
        except Exception:
            semantic_n = None

    out = {
        "_doc": "Redundant-display detector (Phase C). Value-identity = shared terminus table "
                "(reliable, from registry adjacency). Verdicts are proposals; Ian disposes.",
        "totals": {
            "value_identity_clusters": len(clusters),
            "kpi_metric_clusters": len(kpi_clusters),
            "semantic_units_in_corpus": semantic_n,
            "verdicts_curated": sum(1 for c in clusters if c["verdict"] != "REVIEW"),
            "verdicts_pending_review": sum(1 for c in clusters if c["verdict"] == "REVIEW"),
        },
        "value_identity_clusters": clusters,
        "kpi_metric_clusters": kpi_clusters,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    lines = ["# Redundant Displays — Phase C (value-identity + verdicts)\n"]
    lines.append("_Generated by `tools/detect_redundant_displays.py`. Engine proposes; **Ian disposes** — no UI collapsed without sign-off._\n")
    lines.append(f"- Value-identity clusters (table on ≥{MIN_PAGES} surfaces): **{len(clusters)}**")
    lines.append(f"- KPI-metric clusters (single-source enforced): **{len(kpi_clusters)}**")
    if semantic_n is not None:
        lines.append(f"- Semantic info-units in corpus (survey): **{semantic_n}**")
    lines.append("")
    lines.append("## Value-identity clusters → verdict\n")
    lines.append("| Terminus table | Pages | Verdict | Canonical home | UX law | Why |")
    lines.append("|---|---:|---|---|---|---|")
    for c in clusters:
        lines.append(f"| {c['terminus_table']} | {c['page_count']} | **{c['verdict']}** | {c['canonical_home']} | {c['ux_law']} | {c['why']} |")
    lines.append("\n## KPI-metric clusters (already single-source enforced)\n")
    lines.append("| Metric | Source | Consumers | Verdict |")
    lines.append("|---|---|---:|---|")
    for k in kpi_clusters:
        lines.append(f"| {k['metric']} | {', '.join(k['canonical_source'])} | {len(k['consumer_pages'])} | {k['verdict']} |")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"[detect_redundant_displays] {len(clusters)} value-identity clusters | "
          f"{out['totals']['verdicts_curated']} curated / {out['totals']['verdicts_pending_review']} pending review | "
          f"{len(kpi_clusters)} kpi clusters | corpus units {semantic_n}")
    print(f"  -> {os.path.relpath(OUT_JSON, ROOT)} , {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
