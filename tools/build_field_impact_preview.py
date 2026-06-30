#!/usr/bin/env python3
"""
build_field_impact_preview.py  --  Phase D2 of the INTERACTIVE_LINEAGE_ROADMAP.

Powers the "this will update N tiles on M pages" PRE-COMMIT preview (Nielsen #5
error-prevention + Gulf of Execution). Reuse-first: aggregates Phase A's
field_blast_radius.json into a per-WRITE-SURFACE impact summary the client can
show before a high-blast save.

For each write surface, unions its fields' downstream reach:
  - pages the saved data is DISPLAYED on (display fan-out)
  - pages reached via a CAUSAL cascade (e.g. logbook save -> pm_completions ->
    pm-scheduler + analytics)
  - downstream recompute edge functions (risk/analytics/etc.)
Only surfaces whose max field fan-out clears HIGH_BLAST_MIN get a preview (the
roadmap's "only for fields Phase-A flags high-blast").

OUT: field_impact_preview.json  { "<surface>": {pages[], page_count, tiles,
        cascades[], recompute_fns[], headline} }
Run: python tools/build_field_impact_preview.py
"""
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "field_blast_radius.json")
OUT = os.path.join(ROOT, "field_impact_preview.json")
OUT_MD = os.path.join(ROOT, "field_impact_preview.md")

HIGH_BLAST_MIN = 4  # a surface needs at least one field touching >=4 pages to warrant a preview

# Page slug -> readable name (mirrors impact-preview.js prettyPage so the headline tooltip
# and the popover list agree). Known acronyms stay upper-case.
_ACR = {"pm": "PM", "ph": "PH", "ai": "AI", "amc": "AMC", "rfq": "RFQ", "cmms": "CMMS", "oee": "OEE"}
def pretty_page(slug):
    return " ".join(_ACR.get(w, w[:1].upper() + w[1:]) for w in str(slug or "").split("-"))

# USER-VOICE translation of cascade TABLE names -> plain words a worker reads
# (feedback_provenance_user_voice_not_internals). The popover must never show a raw
# table name like `pm_completions`, nor over-show internal/scaffolding tables a worker
# doesn't care about (RAG knowledge stores, audit logs, embeddings). Map user-MEANINGFUL
# effects to plain phrases; map internal ones to "" (skipped from the list). Unmapped
# tables are also SKIPPED (never shown raw) — a future table just won't appear until
# someone gives it a plain name here.
CASCADE_PLAIN = {
    # user-meaningful effects
    "pm_completions": "PM compliance", "inventory_transactions": "inventory usage",
    "inventory_items": "stock levels", "asset_risk_scores": "risk scores",
    "anomaly_signals": "anomaly alerts", "worker_achievements": "achievements",
    "community_xp": "community points", "skill_badges": "skill badges",
    "marketplace_sellers": "seller ratings", "fault_knowledge": "the knowledge base",
    "weibull_fits": "reliability analysis", "pf_intervals": "reliability analysis",
    "rcm_fmea_modes": "failure-mode analysis", "failure_signature_alerts": "early-warning alerts",
    "ai_reports": "AI reports", "analytics_snapshots": "analytics",
    "hive_benchmarks": "benchmarks", "ph_intelligence_reports": "the regional report",
    "external_sync": "your connected systems", "integration_configs": "your connected systems",
    "shift_plans": "shift plans", "amc_briefings": "the daily briefing",
    "parts_staging_recommendations": "parts staging", "community_posts": "community posts",
    "hive_members": "your team", "logbook": "the logbook",
    # internal / scaffolding — NOT shown to the user
    "achievement_xp_log": "", "automation_log": "", "knowledge_graph_facts": "",
    "network_benchmarks": "", "pm_knowledge": "", "skill_knowledge": "",
    "agentic_rag_traces": "", "cmms_audit_log": "", "worker_profiles": "",
    "platform_feedback": "", "platform_feedback_votes": "", "unified_events": "",
    "canonical_period_summaries": "", "agent_episodic_memory": "", "ai_quality_log": "",
}


def main():
    fields = json.load(open(IN, encoding="utf-8"))["fields"]
    by_surface = defaultdict(list)
    for f in fields:
        by_surface[f.get("surface") or "(none)"].append(f)

    out = {}
    for surface, fs in by_surface.items():
        max_fanout = max((f.get("display_fanout") or 0) for f in fs)
        if max_fanout < HIGH_BLAST_MIN:
            continue
        pages = set()
        tiles = 0
        cascades = []
        recompute = set()
        for f in fs:
            for p in (f.get("displayed_on_pages") or []):
                pages.add(p)
            for p in (f.get("cascade_pages") or []):
                pages.add(p)
            tiles = max(tiles, f.get("display_fanout") or 0)
            for c in (f.get("causal_cascades") or []):
                desc = c.get("to_table") or c.get("via")
                if desc and desc not in cascades:
                    cascades.append(desc)
            for fn in (f.get("read_by_edge_fns") or []):
                recompute.add(fn)
        pages = sorted(pages)
        page_count = len(pages)
        # USER-VOICE: translate the raw cascade TABLE names to plain words a worker
        # reads (feedback_provenance_user_voice_not_internals). The raw `cascades` stays
        # for traceability; `cascades_plain` is what the hint/popover render.
        cascades_plain = []
        for c in cascades:
            p = CASCADE_PLAIN.get(c, "")  # unmapped/internal -> "" -> skipped (never raw)
            if p and p not in cascades_plain:
                cascades_plain.append(p)
        casc = (" · also updates " + ", ".join(cascades_plain[:3])) if cascades_plain else ""
        out[surface] = {
            "page_count": page_count,
            "max_field_fanout": max_fanout,
            "pages": pages,
            "cascades": cascades,                 # canonical (raw table names) — NOT rendered
            "cascades_plain": cascades_plain,     # user-voice — rendered in the popover
            "recompute_fns": sorted(recompute),
            "headline": f"This update reaches {page_count} page{'s' if page_count != 1 else ''}"
                        + (f" ({', '.join(pretty_page(p) for p in pages[:4])}{'…' if page_count > 4 else ''})" if pages else "")
                        + casc + ".",
        }

    payload = {
        "_doc": "Per-write-surface PRE-COMMIT impact preview (Phase D2). Powers a 'this will "
                "update N tiles on M pages' confirmation on high-blast saves. Reuse of Phase A "
                "field_blast_radius.json — pages = display fan-out + causal cascade reach. Built "
                "by tools/build_field_impact_preview.py.",
        "high_blast_min": HIGH_BLAST_MIN,
        "surfaces": out,
    }
    json.dump(payload, open(OUT, "w", encoding="utf-8"), indent=2)

    lines = ["# Field Impact Preview — Phase D2 (pre-commit 'updates N tiles on M pages')\n",
             "_Generated by `tools/build_field_impact_preview.py` from Phase A blast radius._\n",
             f"- High-blast write surfaces (≥{HIGH_BLAST_MIN}-page fan-out): **{len(out)}**\n",
             "| Surface | Pages | Headline |", "|---|--:|---|"]
    for s in sorted(out, key=lambda k: -out[k]["page_count"]):
        d = out[s]
        lines.append(f"| {s} | {d['page_count']} | {d['headline']} |")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"[field_impact_preview] {len(out)} high-blast surfaces -> {OUT}")
    for s in sorted(out, key=lambda k: -out[k]["page_count"]):
        print(f"  {s}: {out[s]['page_count']} pages, fanout {out[s]['max_field_fanout']}")


if __name__ == "__main__":
    main()
