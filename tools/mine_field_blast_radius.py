#!/usr/bin/env python3
"""
mine_field_blast_radius.py  --  Phase A of the INTERACTIVE_LINEAGE_ROADMAP.

Answers Ian's Q1: "when I edit/select a field, how many levels of downstream
effect does it produce, and which surfaces display that effect?"

Composes two EXISTING artifacts (reuse-first, no new capture parsing):
  - column_terminus.json   : hop 1  (field -> table.column)   [tools/mine_column_terminus.py]
  - canonical_registry.json: adjacency (table/view -> reading surfaces + edge fns)

Two honest notions of "downstream", both reported per field:
  * DISPLAY FAN-OUT  (auto, complete) -- every surface/edge-fn that READS the
        field's terminus table, directly or via a canonical view over it.
        This is "how many places show the effect of editing this field."
        depth: 0 field -> 1 table -> (2 view) -> page.
  * CAUSAL CASCADE   (curated overlay) -- editing the field TRIGGERS a write to
        another table (the 5-8 confirmed cross-page cascades). Registry adjacency
        cannot prove causality, so these are a curated seed (like lineage_edges.json)
        to be expanded; counted separately, never conflated with display fan-out.

Outputs: field_blast_radius.json  +  field_blast_radius.md
Run:     python tools/mine_field_blast_radius.py   [--check]
"""
import json
import re
import sys
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERMINUS = os.path.join(ROOT, "column_terminus.json")
REGISTRY = os.path.join(ROOT, "canonical_registry.json")
OUT_JSON = os.path.join(ROOT, "field_blast_radius.json")
OUT_MD = os.path.join(ROOT, "field_blast_radius.md")

# Canonical view -> base table where the NAME does not encode it (v_risk_truth !-> risk).
# Name-matched views (v_<table>_truth -> <table>) are resolved automatically; this map
# only covers the mismatches. Extend as canonical views are added.
VIEW_BASE_OVERRIDE = {
    "v_risk_truth": "asset_risk_scores",
    "v_pm_compliance_truth": "pm_completions",
    "v_anomaly_truth": "anomaly_signals",
    "v_sensor_truth": "sensor_readings",
    "v_sensor_recent": "sensor_readings",
    "v_asset_truth": "asset_nodes",
    "v_fmea_truth": "rcm_fmea_modes",
    "v_rcm_truth": "rcm_strategies",
    "v_weibull_truth": "weibull_fits",
    "v_pf_truth": "pf_intervals",
    "v_worker_truth": "hive_members",
    "v_worker_skill_truth": "skill_profiles",
}

# Curated causal cross-page cascades (a field write TRIGGERS another table write).
# Seeded from the 4-agent sweep's confirmed cascades. Each: terminus table that, when
# written by `trigger_page`, causes downstream table writes. Expand as detected.
KNOWN_CASCADES = {
    "logbook": [
        {"to_table": "pm_completions", "via": "logbook.html save w/ PM tasks checked", "downstream_pages": ["pm-scheduler", "analytics"]},
        {"to_table": "inventory_transactions", "via": "logbook 'Parts Used' -> inventory_deduct RPC", "downstream_pages": ["inventory", "analytics"]},
        {"to_table": "inventory_items", "via": "inventory_deduct decrement qty_on_hand", "downstream_pages": ["inventory", "alert-hub", "hive"]},
    ],
    "rcm_fmea_modes": [
        {"to_table": "asset_risk_scores", "via": "FMEA top-RPN factor (weight 0.10) in batch-risk-scoring", "downstream_pages": ["predictive", "alert-hub", "asset-hub", "shift-brain", "analytics", "index"]},
    ],
    "sensor_readings": [
        {"to_table": "anomaly_signals", "via": "compute_anomaly_signals 3-sigma", "downstream_pages": ["alert-hub", "analytics"]},
    ],
}


def load_cascade_overlay():
    """Merge the in-code seed with the evidence-mapped causal_cascades.json overlay
    (44 triggers + 60+ edge fns swept 2026-06-29). Graceful if the file is absent
    (falls back to the seed). Keyed from_table -> [{to_table, via, downstream_pages, evidence}]."""
    merged = {k: [dict(c) for c in v] for k, v in KNOWN_CASCADES.items()}
    path = os.path.join(ROOT, "causal_cascades.json")
    if os.path.exists(path):
        try:
            for c in json.load(open(path, encoding="utf-8")).get("cascades", []):
                ft = c.get("from_table")
                if not ft:
                    continue
                row = {"to_table": c.get("to_table"), "via": c.get("via"),
                       "downstream_pages": c.get("downstream_pages", []), "evidence": c.get("evidence")}
                bucket = merged.setdefault(ft, [])
                # de-dup on (to_table, via) so re-running is idempotent
                if not any(e.get("to_table") == row["to_table"] and e.get("via") == row["via"] for e in bucket):
                    bucket.append(row)
        except Exception:
            pass
    return merged


def normalize_view_base(name, tables):
    """If `name` is a view, return its base table; else return name unchanged."""
    if name in VIEW_BASE_OVERRIDE:
        return VIEW_BASE_OVERRIDE[name]
    m = re.match(r"^v_(.+?)(_truth)?$", name)
    if m and m.group(1) in tables:
        return m.group(1)
    return name  # base table, or a view whose base we can't resolve by name


def build_graph(reg):
    tables = reg["tables"]
    views = reg["views"]
    surfaces = reg["surfaces"]

    # node (table OR view) -> set of reader pages / writer pages / reader fns
    page_readers_of_node = defaultdict(set)
    page_writers_of_node = defaultdict(set)
    for page, s in surfaces.items():
        pid = page[:-5] if page.endswith(".html") else page
        for node in s.get("tables_read", []):
            page_readers_of_node[node].add(pid)
        for node in s.get("tables_written", []):
            page_writers_of_node[node].add(pid)

    fn_readers_of_table = {t: set(meta.get("read_by_edge_fns", [])) for t, meta in tables.items()}
    fn_readers_of_view = {v: set(meta.get("read_by_edge_fns", [])) for v, meta in views.items()}

    # For each BASE table T: which pages display it (direct read of T, or read of a view over T)?
    table_display_pages = defaultdict(set)
    table_display_fns = defaultdict(set)
    table_via_views = defaultdict(set)  # T -> {views over T that are actually read}
    for node, readers in page_readers_of_node.items():
        base = normalize_view_base(node, tables)
        table_display_pages[base] |= readers
        if node != base:
            table_via_views[base].add(node)
    # edge fns
    for t, fns in fn_readers_of_table.items():
        table_display_fns[t] |= fns
    for v, fns in fn_readers_of_view.items():
        base = normalize_view_base(v, tables)
        table_display_fns[base] |= fns
        if fns and v != base:
            table_via_views[base].add(v)
    return table_display_pages, table_display_fns, table_via_views


def compute(terminus, reg):
    tables = reg["tables"]
    table_display_pages, table_display_fns, table_via_views = build_graph(reg)
    cascade_overlay = load_cascade_overlay()

    fields_out = []
    per_page = defaultdict(lambda: {"fields": 0, "persisted": 0, "dead_end": 0,
                                    "fanout_sum": 0, "max_depth": 0})
    for rec in terminus["fields"]:
        surface = rec.get("surface")
        field = rec.get("field")
        bucket = rec.get("bucket")
        table = rec.get("table")
        col = rec.get("column")
        per_page[surface]["fields"] += 1
        if bucket not in ("PERSISTED", "PERSISTED?") or not table:
            continue
        per_page[surface]["persisted"] += 1

        reader_pages = set(table_display_pages.get(table, set()))
        reader_pages.discard(surface)  # the writer page itself isn't "downstream"
        reader_fns = set(table_display_fns.get(table, set()))
        via_views = sorted(table_via_views.get(table, set()))

        # depth: 0=field, 1=terminus table, +1 if any OTHER page displays it,
        # +1 again if that display goes through a canonical view (the deepest path).
        if reader_pages or reader_fns:
            depth = 3 if via_views else 2
        else:
            depth = 1
        fanout = len(reader_pages)

        cascades = cascade_overlay.get(table, [])
        cascade_pages = set()
        for c in cascades:
            cascade_pages |= set(c["downstream_pages"])

        if fanout == 0 and not reader_fns and not cascades:
            per_page[surface]["dead_end"] += 1
        per_page[surface]["fanout_sum"] += fanout
        per_page[surface]["max_depth"] = max(per_page[surface]["max_depth"], depth)

        fields_out.append({
            "surface": surface,
            "field": field,
            "terminus": f"{table}.{col}" if col else table,
            "display_fanout": fanout,
            "display_depth": depth,
            "displayed_on_pages": sorted(reader_pages),
            "displayed_via_views": via_views,
            "read_by_edge_fns": sorted(reader_fns),
            "causal_cascades": cascades,
            "cascade_pages": sorted(cascade_pages),
        })

    return fields_out, per_page


def main():
    check = "--check" in sys.argv
    terminus = json.load(open(TERMINUS, encoding="utf-8"))
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    fields_out, per_page = compute(terminus, reg)

    persisted = [f for f in fields_out]
    n = len(persisted)
    dead_end = [f for f in persisted if f["display_fanout"] == 0 and not f["read_by_edge_fns"] and not f["causal_cascades"]]
    high_blast = sorted(persisted, key=lambda f: f["display_fanout"], reverse=True)[:15]
    cascade_fields = [f for f in persisted if f["causal_cascades"]]

    out = {
        "_doc": "Per-field downstream blast radius (Phase A of INTERACTIVE_LINEAGE_ROADMAP). "
                "display_fanout = surfaces that DISPLAY the field's terminus table (auto, complete). "
                "causal_cascades = curated cross-page write-cascades (seed, expand).",
        "totals": {
            "persisted_fields_analyzed": n,
            "dead_end_fields": len(dead_end),
            "fields_with_causal_cascade": len(cascade_fields),
            "avg_display_fanout": round(sum(f["display_fanout"] for f in persisted) / n, 2) if n else 0,
            "max_display_fanout": max((f["display_fanout"] for f in persisted), default=0),
        },
        "per_page": {p: v for p, v in sorted(per_page.items())},
        "fields": fields_out,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    # Markdown scoreboard
    lines = []
    lines.append("# Field Blast Radius — Phase A (per-field downstream topology)\n")
    lines.append(f"_Generated by `tools/mine_field_blast_radius.py`. Persisted fields analyzed: **{n}**._\n")
    lines.append("> `display_fanout` = how many OTHER surfaces display this field's terminus table "
                 "(via direct read or a canonical view). `causal_cascades` = curated cross-page write-cascades.\n")
    lines.append("## Totals\n")
    lines.append(f"- Persisted fields: **{n}**")
    lines.append(f"- Dead-end fields (fanout 0, no fn reader, no cascade): **{len(dead_end)}** — cut/justify candidates")
    lines.append(f"- Fields with a causal cross-page cascade: **{len(cascade_fields)}**")
    lines.append(f"- Avg display fan-out: **{out['totals']['avg_display_fanout']}**  ·  Max: **{out['totals']['max_display_fanout']}**\n")
    lines.append("## Highest blast-radius fields (deserve a Phase-D impact preview)\n")
    lines.append("| Field | Terminus | Fan-out | Depth | Displayed on |")
    lines.append("|---|---|---:|---:|---|")
    for f in high_blast:
        pages = ", ".join(f["displayed_on_pages"][:6]) + ("…" if len(f["displayed_on_pages"]) > 6 else "")
        lines.append(f"| {f['surface']}:{f['field']} | {f['terminus']} | {f['display_fanout']} | {f['display_depth']} | {pages} |")
    lines.append("\n## Per input page\n")
    lines.append("| Page | Fields | Persisted | Dead-end | Avg fan-out | Max depth |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for p, v in sorted(per_page.items(), key=lambda kv: -kv[1]["persisted"]):
        if v["persisted"] == 0:
            continue
        avg = round(v["fanout_sum"] / v["persisted"], 1) if v["persisted"] else 0
        lines.append(f"| {p} | {v['fields']} | {v['persisted']} | {v['dead_end']} | {avg} | {v['max_depth']} |")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"[mine_field_blast_radius] {n} persisted fields | "
          f"{len(dead_end)} dead-end | {len(cascade_fields)} cascade | "
          f"avg fan-out {out['totals']['avg_display_fanout']} | max {out['totals']['max_display_fanout']}")
    print(f"  -> {os.path.relpath(OUT_JSON, ROOT)} , {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
