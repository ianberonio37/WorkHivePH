#!/usr/bin/env python3
"""
mine_render_surfaces.py — Arc C / Phase C0: mine the WHOLE-PLATFORM render denominator.

WHY THIS EXISTS (the anti-false-sense rule)
-------------------------------------------
Arc B proved the browser-render tier for the richest page (engineering-design, 53
calc types). But EVERY feature page that renders a computed/canonical value has the
same gap: the JS render layer between the source (a v_*_truth view, an edge fn, the
calc engine, an ML model) and the worker's eye is a surface that DB/API/hermetic
validators structurally cannot see. The §13 V-axis proves ONE render cell per page;
a page renders MANY values.

C0's job is the DENOMINATOR, mined not sampled: the cell set is
    (feature page  ×  rendered-canonical-value tile).
The page authors already DECLARED those tiles — every canonical value the RAG/
companion layer is allowed to read is marked `data-rag-tile="<page>:<id>"` wrapping
a `.sc-hero` value element. That marker IS the principled denominator (not a
heuristic scrape of every number on the page): a tile is, by construction, "a value
this page renders from a canonical source."

This tool:
  1. enumerates every `data-rag-tile` cell across all feature pages (the registry),
  2. classifies each as a single-VALUE tile (wraps a `.sc-hero`) or a PANEL/list/chart
     surface (detail/grid/heatmap — a richer render proven differently),
  3. CREDITS the cells already proven by the §13 V-axis (vaxis_render_proofs.json:
     J1-J6 + T_*) and this session's asset-hub proof, by exact tile-id join, so they
     are not re-proven,
  4. emits the total N + the proven/unproven split + a per-page C1 spec scaffold
     (tile_id -> sc-hero element id -> source-query placeholder).

From C1 on, every "done" is verified/total against THIS denominator.

Outputs: render_surfaces.json (machine ledger, feeds render_sweep.mjs) + render_surfaces.md.
"""
# audit-scope-allow: render surfaces are the first-class TOOL pages (root *.html ∩ LIVE_TOOL_PAGES /
# nav registry) — the data-rendering dashboards. Subdir pages (/learn/*.html) are content articles with
# no tile/source-view render contract, so a subdirectory rglob is out of scope by design, not an omission.

import json
import re
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAXIS_PROOFS = ROOT / "vaxis_render_proofs.json"
NAV_HUB = ROOT / "nav-hub.js"
OUT_JSON = ROOT / "render_surfaces.json"
OUT_MD = ROOT / "render_surfaces.md"

# Pages that are render-tier feature pages but whose canonical render is NOT a
# data-rag-tile sc-hero (proven by the V-axis through a different mechanism). We
# credit these as page-level proofs so they count toward "already proven" without
# being mistaken for tile cells.
NON_TILE_PROVEN_PAGES = {
    "voice-journal.html": "J4 — 'Your journal: N entries' == HISTORY_LIMIT, auth-scoped (vaxis J4)",
    "status.html": "J6 — /health SLO grid renders live == /health probes (vaxis J6)",
    "ai-quality.html": "T_ai_quality — page aggregate() value-derivation proven 10/10 vs hand oracle",
    "project-report.html": "T_project_report — wbs/owner/status == v_project_truth (PM print-flow)",
    "engineering-design.html": "Arc B — 53 calc types render==validated-Python (browser_calc_sweep B1)",
}

# Tile kinds we treat as PANEL (a richer surface — detail view, list grid, chart),
# matched on the tile-id suffix. These are proven by a different assertion than a
# single sc-hero number (asset-hub:detail_panel == v_risk_truth is the template).
PANEL_SUFFIXES = (
    "detail_panel", "listing_grid", "project_cards", "project_list", "risk_ranking",
    "risk_heatmap", "mtbf_trend", "results_panel", "api_config", "sync_log",
    "amc_assets", "amc_pms", "amc_parts", "amc_crew", "active_domains_stat",
    "top_domain", "listing_grid",
)
# NB: a suffix here is only a HINT — classify() reclassifies to 'panel' anyway if
# the tile has no nested .sc-hero. saved_contacts WAS listed but is a real value
# tile (#rs-contacts-hero = count of report_contacts), so it was removed.


def load_nav_registry():
    """The LIVE_TOOL_PAGES set — which pages are first-class feature pages."""
    if not NAV_HUB.exists():
        return set()
    txt = NAV_HUB.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r"['\"]([a-z0-9-]+\.html)['\"]", txt))


def load_credit_index():
    """Tile-ids (and page-level proofs) already verified render==source.

    Join key is the data-rag-tile id (e.g. 'pm-scheduler:overdue'). We collect
    every explicitly-verified tile from vaxis_render_proofs.json + this session's
    asset-hub proof. ONLY tiles a proof asserted render==DB are credited; tiles
    that 'render live but derivation pending' (analytics oee/mtbf) are NOT.
    """
    credited = {}  # tile_id -> credit source label
    page_proven = {}  # page.html -> label (non-tile proven pages)

    if VAXIS_PROOFS.exists():
        proofs = json.loads(VAXIS_PROOFS.read_text(encoding="utf-8")).get("proofs", {})
        for jid, entry in proofs.items():
            if not entry.get("ok"):
                continue
            label = f"{jid} ({entry.get('page', '?')})"
            # single-tile proofs
            t = entry.get("tile")
            if t:
                credited[t] = label
            # multi-tile proofs
            for tinfo in entry.get("tiles", []):
                tid = tinfo.get("tile")
                if not tid or not tinfo.get("ok"):
                    continue
                # the proof labels can be "tile + extra" (e.g. 'pm-scheduler:on_track + SMRP compliance')
                tid_clean = tid.split(" + ")[0].split(" (")[0].strip()
                credited[tid_clean] = label
            # composite-component proofs (J1 hive:open_issues already set via .tile)
            # page-level proofs (J4/J5/J6) recorded against their page
            pg = entry.get("page")
            if pg and not t and not entry.get("tiles"):
                page_proven[pg] = label

    # this session's asset-hub render proof (handoff: card == criticality 30/30 +
    # detail == v_risk_truth). Credited by tile-id join.
    credited.setdefault("asset-hub:critical_assets",
                        "Arc-B/session (card band == asset_nodes.criticality, 30/30)")
    credited.setdefault("asset-hub:detail_panel",
                        "Arc-B/session (detail risk == v_risk_truth, AC-003 faithful)")

    # NON_TILE proven pages
    for pg, lbl in NON_TILE_PROVEN_PAGES.items():
        page_proven.setdefault(pg, lbl)

    return credited, page_proven


# match an opening tag that carries data-rag-tile, capture its full attr string
TILE_TAG_RE = re.compile(r"<(\w+)\b([^>]*\bdata-rag-tile=\"[^\"]+\"[^>]*)>")
ATTR_RE = lambda name: re.compile(rf'\b{name}="([^"]*)"')
SC_HERO_RE = re.compile(r'class="[^"]*\bsc-hero\b[^"]*"[^>]*\bid="([^"]+)"|id="([^"]+)"[^>]*class="[^"]*\bsc-hero\b[^"]*"')


def classify(tile_id):
    suffix = tile_id.split(":", 1)[-1]
    for ps in PANEL_SUFFIXES:
        if suffix == ps:
            return "panel"
    return "value"


def mine_page(path: Path):
    html = path.read_text(encoding="utf-8", errors="ignore")
    tiles = []
    # find each data-rag-tile opening tag and the window up to the next one
    marks = [m for m in TILE_TAG_RE.finditer(html)]
    for i, m in enumerate(marks):
        attrs = m.group(2)
        tid_m = ATTR_RE("data-rag-tile").search(attrs)
        if not tid_m:
            continue
        tid = tid_m.group(1)
        label_m = ATTR_RE("data-rag-label").search(attrs)
        cont_id_m = ATTR_RE("id").search(attrs)
        cell_type = classify(tid)
        # bounded window: from this tag to the next tile tag (or +1200 chars)
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else min(len(html), start + 1200)
        window = html[start:end]
        hero_id = None
        if cell_type == "value":
            hm = SC_HERO_RE.search(window)
            if hm:
                hero_id = hm.group(1) or hm.group(2)
            else:
                # no sc-hero in window -> reclassify as panel (honest)
                cell_type = "panel"
        tiles.append({
            "tile_id": tid,
            "label": label_m.group(1) if label_m else None,
            "container_id": cont_id_m.group(1) if cont_id_m else None,
            "sc_hero_id": hero_id,
            "cell_type": cell_type,
        })
    return tiles


def main():
    nav = load_nav_registry()
    credited, page_proven = load_credit_index()

    pages = {}
    for path in sorted(ROOT.glob("*.html")):   # scope rationale in the audit-scope-allow header note
        name = path.name
        if name in ("index.html",):
            # index has 1 marketing activity tile; keep it but flag not-a-feature
            pass
        tiles = mine_page(path)
        if not tiles:
            continue
        for t in tiles:
            cid = t["tile_id"]
            t["credited"] = cid in credited
            t["credit_source"] = credited.get(cid)
            # a C1 spec scaffold: where to read + placeholder for the source query
            t["source_query"] = "<TODO C1>" if not t["credited"] else "credited"
        pages[name] = {
            "in_nav_registry": name in nav,
            "n_tiles": len(tiles),
            "n_value": sum(1 for t in tiles if t["cell_type"] == "value"),
            "n_panel": sum(1 for t in tiles if t["cell_type"] == "panel"),
            "n_credited": sum(1 for t in tiles if t["credited"]),
            "tiles": tiles,
        }

    # totals
    all_tiles = [t for p in pages.values() for t in p["tiles"]]
    N = len(all_tiles)
    N_value = sum(1 for t in all_tiles if t["cell_type"] == "value")
    N_panel = sum(1 for t in all_tiles if t["cell_type"] == "panel")
    credited_n = sum(1 for t in all_tiles if t["credited"])
    value_credited = sum(1 for t in all_tiles if t["credited"] and t["cell_type"] == "value")

    ledger = {
        "_meta": {
            "doc": "Arc C / C0 render-tier DENOMINATOR. N = (feature page × data-rag-tile cell). "
                   "Each tile = a canonical value the page renders, page-author-declared via data-rag-tile. "
                   "credited=true means a §13 V-axis or asset-hub proof already asserted render==source for "
                   "that exact tile-id (not re-proven in Arc C). value cells get a single sc-hero number; "
                   "panel cells are detail/list/chart surfaces proven by a richer assertion (asset-hub:detail_panel "
                   "== v_risk_truth is the template). source_query '<TODO C1>' = the per-page C1 spec to fill.",
            "generator": "tools/mine_render_surfaces.py",
            "credit_inputs": ["vaxis_render_proofs.json (J1-J6, T_*)", "asset-hub session proof"],
        },
        "totals": {
            "pages_with_tiles": len(pages),
            "N_total_cells": N,
            "N_value_cells": N_value,
            "N_panel_cells": N_panel,
            "credited_cells": credited_n,
            "value_cells_credited": value_credited,
            "value_cells_uncredited": N_value - value_credited,
            "credited_pct": round(100 * credited_n / N, 1) if N else 0,
            "value_credited_pct": round(100 * value_credited / N_value, 1) if N_value else 0,
        },
        "non_tile_proven_pages": page_proven,
        "pages": pages,
    }
    OUT_JSON.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    # ── markdown ─────────────────────────────────────────────────────────────
    lines = []
    lines.append("# Arc C · C0 — Whole-Platform Render-Tier Denominator\n")
    lines.append(f"_Mined by `tools/mine_render_surfaces.py`. The denominator is **(feature page × `data-rag-tile` cell)** — "
                 f"page-author-declared canonical-value tiles, not a heuristic scrape._\n")
    t = ledger["totals"]
    lines.append("## Totals\n")
    lines.append(f"- **N = {t['N_total_cells']} render cells** across {t['pages_with_tiles']} pages "
                 f"({t['N_value_cells']} single-value tiles · {t['N_panel_cells']} panel/list/chart surfaces)")
    lines.append(f"- **Already proven (credited): {t['credited_cells']}/{t['N_total_cells']} = {t['credited_pct']}%** "
                 f"(§13 V-axis + asset-hub)")
    lines.append(f"- **Value tiles proven: {t['value_cells_credited']}/{t['N_value_cells']} = {t['value_credited_pct']}%** "
                 f"→ C1 target = the **{t['value_cells_uncredited']} uncredited value tiles** first\n")
    lines.append("## Per page\n")
    lines.append("| Page | nav | tiles | value | panel | credited |")
    lines.append("|---|---|--:|--:|--:|--:|")
    for name in sorted(pages):
        p = pages[name]
        lines.append(f"| {name} | {'✓' if p['in_nav_registry'] else '–'} | {p['n_tiles']} "
                     f"| {p['n_value']} | {p['n_panel']} | {p['n_credited']} |")
    lines.append("\n## Non-tile proven pages (credited page-level, outside the tile denominator)\n")
    for pg, lbl in sorted(page_proven.items()):
        lines.append(f"- **{pg}** — {lbl}")
    lines.append("\n## C1 worklist — uncredited VALUE tiles (read sc-hero, compare to source)\n")
    lines.append("| Page | tile_id | label | sc-hero id |")
    lines.append("|---|---|---|---|")
    for name in sorted(pages):
        for tile in pages[name]["tiles"]:
            if tile["cell_type"] == "value" and not tile["credited"]:
                lines.append(f"| {name} | `{tile['tile_id']}` | {tile['label'] or ''} | `{tile['sc_hero_id'] or '?'}` |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # console
    print("=" * 68)
    print("Arc C · C0 — render-tier denominator MINED")
    print(f"  N total cells          {N}  ({N_value} value · {N_panel} panel)")
    print(f"  credited (proven)      {credited_n}/{N} = {ledger['totals']['credited_pct']}%")
    print(f"  value tiles proven     {value_credited}/{N_value} = {ledger['totals']['value_credited_pct']}%")
    print(f"  C1 target (uncredited value tiles)  {N_value - value_credited}")
    print(f"  -> {OUT_JSON.name} + {OUT_MD.name}")


if __name__ == "__main__":
    main()
