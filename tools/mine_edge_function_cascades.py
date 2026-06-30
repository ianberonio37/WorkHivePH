#!/usr/bin/env python3
"""
mine_edge_function_cascades.py  --  Phase A residual-closer for INTERACTIVE_LINEAGE_ROADMAP.

Closes the "edge-fn source-attribution is statically undecidable" gap that left
Phase A at 98%. The undecidable part is *which user FIELD* triggers a given edge
function. But the part that actually completes the cascade graph -- *which TABLE an
edge fn WRITES, and which pages DISPLAY that table* -- IS fully statically decidable
by parsing `db.from("<table>").insert/upsert/update/delete(...)` in each function's
source. This miner does that deterministically (ground truth, file:line cited), then
dispositions every write into exactly one bucket:

  * DATA cascade   -- writes a table some page displays  -> must be in causal_cascades.json
  * OPERATIONAL    -- job/audit logs (automation_log, *_audit_log): surfaced on a log
                      page but not an "edit-here-see-there" data cascade (the edge-fn
                      analogue of the trigger gate's IGNORE_TARGETS)
  * SELF/CONFIG    -- a fn updating its own config/state row (not cross-page)
  * INFRA          -- writes a table no surface displays (rate limits, embeddings,
                      job queues): honest, counted, downstream_pages=[]

The DATA-cascade bucket is what `validate_causal_cascade_coverage.py` enforces (every
one must be mapped) -- making the edge-fn half of the discovery gate PROVEN COMPLETE,
exactly as the trigger half already is.

Reuse-first: composes canonical_registry adjacency via mine_field_blast_radius.build_graph
(table -> display pages, incl. canonical views) and reads causal_cascades.json for the
already-mapped set. No new capture parsing.

Outputs: edge_function_cascades.json + edge_function_cascades.md
Run:     python tools/mine_edge_function_cascades.py   [--check]
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = ROOT / "supabase" / "functions"
REGISTRY = ROOT / "canonical_registry.json"
CASC = ROOT / "causal_cascades.json"
OUT_JSON = ROOT / "edge_function_cascades.json"
OUT_MD = ROOT / "edge_function_cascades.md"

# Operational / audit logs: a row appears on a log page when a job runs, but it is NOT a
# user-data "edit-here-see-there" cascade. The edge-fn analogue of the trigger gate's
# IGNORE_TARGETS. (logbook->automation_log / pm_completions->automation_log via the
# hive-quota trigger ARE in the overlay; these are the SCHEDULED-JOB writers of the log.)
OPERATIONAL_LOG_TABLES = {
    "automation_log",      # scheduled-job run log -> alert-hub automation panel
    "hive_audit_log",      # security/audit trail -> audit-log
    "gateway_audit_log",   # API gateway request log -> plant-connections
    "cmms_audit_log",      # CMMS reconciliation log -> integrations (mapped as data via cmms-sync)
    "api_audit_log",
}

# Self / config writes: a fn updating the very config/state row that drives it (last_synced,
# Stripe-connect status, key rotation). Not a cross-page DATA cascade.
SELF_CONFIG_WRITES = {
    ("cmms-sync", "integration_configs"),          # updates its own last_synced/status
    ("cmms-webhook-receiver", "integration_configs"),
    ("intelligence-api", "api_keys"),              # API key issuance/rotation (admin config)
}

FROM_RE = re.compile(r"\.from\(\s*[\"']([a-z_][a-z0-9_]*)[\"']\s*\)", re.IGNORECASE)
METH_RE = re.compile(r"\.(insert|upsert|update|delete|select)\b")
WRITE_METHODS = {"insert", "upsert", "update", "delete"}


def parse_table_ops(src):
    """For each `.from("T")`, find the first chained query method (write or select) within
    the window up to the next `.from(`. Returns lists of (table, line) for writes and reads."""
    writes, reads = [], []
    matches = list(FROM_RE.finditer(src))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(src), m.end() + 300)
        mm = METH_RE.search(src[m.end():end])
        if not mm:
            continue
        table = m.group(1)
        line = src.count("\n", 0, m.start()) + 1
        if mm.group(1) in WRITE_METHODS:
            writes.append((table, line))
        else:
            reads.append((table, line))
    return writes, reads


def mapped_fn_edges():
    """(fn, to_table) pairs already represented in causal_cascades.json (evidence cites
    functions/<fn>/). Independent of from_table (edge-fn ingest may have no internal source)."""
    edges = set()
    try:
        for c in json.load(open(CASC, encoding="utf-8")).get("cascades", []):
            ev = c.get("evidence", "") or ""
            tt = c.get("to_table")
            for fnm in re.findall(r"functions/([a-z0-9-]+)/", ev):
                if tt:
                    edges.add((fnm, tt))
    except Exception:
        pass
    return edges


def disposition(fn, table, display_pages, mapped):
    """Bucket a (fn, table) write. Order matters: explicit ledgers first."""
    if table in OPERATIONAL_LOG_TABLES:
        return "operational"
    if (fn, table) in SELF_CONFIG_WRITES:
        return "self_config"
    if not display_pages:
        return "infra"
    return "data_mapped" if (fn, table) in mapped else "data_unmapped"


def main():
    check = "--check" in sys.argv
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tools"))
    import mine_field_blast_radius as M  # noqa
    table_display_pages, _table_display_fns, _vv = M.build_graph(reg)
    mapped = mapped_fn_edges()

    fns = sorted(d for d in FUNCTIONS.iterdir()
                 if d.is_dir() and d.name != "_shared" and (d / "index.ts").exists())

    per_fn = {}
    buckets = {"data_mapped": [], "data_unmapped": [], "operational": [], "self_config": [], "infra": []}
    for d in fns:
        src = (d / "index.ts").read_text(encoding="utf-8")
        writes, reads = parse_table_ops(src)
        write_tables = {}
        for t, ln in writes:
            write_tables.setdefault(t, ln)  # first occurrence line
        read_tables = sorted({t for t, _ in reads})
        callers = sorted(p[:-5] if p.endswith(".html") else p
                         for p, s in reg["surfaces"].items()
                         if d.name in s.get("edge_fns_invoked", []))
        wlist = []
        for t, ln in sorted(write_tables.items()):
            pages = sorted(table_display_pages.get(t, set()))
            disp = disposition(d.name, t, pages, mapped)
            row = {"fn": d.name, "to_table": t, "line": ln,
                   "evidence": f"functions/{d.name}/index.ts:{ln}",
                   "downstream_pages": pages, "disposition": disp}
            wlist.append(row)
            buckets[disp].append(row)
        if wlist:
            per_fn[d.name] = {"writes": wlist, "reads": read_tables, "invoked_by_pages": callers}

    out = {
        "_doc": "Deterministic edge-function cross-table WRITE map (Phase A residual-closer of "
                "INTERACTIVE_LINEAGE_ROADMAP). Parsed from each function's index.ts "
                "`.from(T).insert/upsert/update/delete`. disposition: data_mapped/data_unmapped "
                "(displayed table -> must be in causal_cascades.json) | operational (job/audit log) "
                "| self_config | infra (no display page).",
        "totals": {
            "edge_fns_with_writes": len(per_fn),
            "data_cascades_mapped": len(buckets["data_mapped"]),
            "data_cascades_UNMAPPED": len(buckets["data_unmapped"]),
            "operational_log_writes": len(buckets["operational"]),
            "self_config_writes": len(buckets["self_config"]),
            "infra_writes": len(buckets["infra"]),
        },
        "data_cascades_unmapped": buckets["data_unmapped"],
        "by_fn": per_fn,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    # Markdown
    lines = ["# Edge-Function Cascade Map — Phase A residual-closer\n",
             f"_Generated by `tools/mine_edge_function_cascades.py`. "
             f"{len(per_fn)} edge fns write tables._\n",
             "> Every write is parsed from source (`functions/<fn>/index.ts`) and dispositioned. "
             "DATA cascades (a written table some page displays) must be mapped in "
             "`causal_cascades.json` — enforced by `validate_causal_cascade_coverage.py`.\n",
             "## Totals\n"]
    for k, v in out["totals"].items():
        lines.append(f"- {k.replace('_', ' ')}: **{v}**")
    if buckets["data_unmapped"]:
        lines.append("\n## ⚠ UNMAPPED data cascades (add to causal_cascades.json)\n")
        lines.append("| Edge fn | Writes | Evidence | Displayed on |")
        lines.append("|---|---|---|---|")
        for r in buckets["data_unmapped"]:
            lines.append(f"| {r['fn']} | {r['to_table']} | {r['evidence']} | {', '.join(r['downstream_pages'][:6])} |")
    lines.append("\n## Mapped data cascades\n")
    lines.append("| Edge fn | Writes | Displayed on |")
    lines.append("|---|---|---|")
    for r in buckets["data_mapped"]:
        lines.append(f"| {r['fn']} | {r['to_table']} | {', '.join(r['downstream_pages'][:6])} |")
    lines.append("\n## Operational / audit-log writes (not data cascades)\n")
    for r in buckets["operational"]:
        lines.append(f"- {r['fn']} -> {r['to_table']} ({r['evidence']})")
    lines.append("\n## Self / config writes\n")
    for r in buckets["self_config"]:
        lines.append(f"- {r['fn']} -> {r['to_table']} ({r['evidence']})")
    lines.append("\n## Infra writes (no display page)\n")
    for r in buckets["infra"]:
        lines.append(f"- {r['fn']} -> {r['to_table']} ({r['evidence']})")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    t = out["totals"]
    print(f"[mine_edge_function_cascades] {t['edge_fns_with_writes']} fns write tables | "
          f"data mapped {t['data_cascades_mapped']} | UNMAPPED {t['data_cascades_UNMAPPED']} | "
          f"operational {t['operational_log_writes']} | self/config {t['self_config_writes']} | "
          f"infra {t['infra_writes']}")
    print(f"  -> {OUT_JSON.relative_to(ROOT)} , {OUT_MD.relative_to(ROOT)}")
    if check and buckets["data_unmapped"]:
        print(f"  CHECK: {len(buckets['data_unmapped'])} unmapped data cascade(s) -- add to causal_cascades.json")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
