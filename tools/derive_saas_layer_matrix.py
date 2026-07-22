#!/usr/bin/env python3
"""
derive_saas_layer_matrix.py - per-page × 13-SaaS-layer applicability grid (2026-07-22).
=======================================================================================
The scoreboard skeleton for PER_PAGE_SAAS_LAYER_BUGHUNT_ROADMAP.md. For each page's substrate card
(substrate/page/<page>.md) it resolves which of the 13 full-stack production layers
(COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §2: F A D AU H C CI S RL CA LB L AV) are LIVE for that page vs
N/A, from the page's real footprint (Edge invokes / DB writes / RPC / Truth views) — so the SaaS-layer
scoreboard is derived deterministically, not guessed (mirrors derive_page_matrix.py for the v3 arc).

A layer is LIVE only if the page's stack actually touches it:
  F  Frontend       always (every page renders)
  A  APIs           iff the page invokes an edge fn
  D  Database       iff the page writes a table OR reads a truth view
  AU Auth           iff the page touches tenant data (writes OR truth-view reads)
  H  Hosting        always-light (ships in the bundle; per-page slice = CSP/headers apply)
  C  Cloud/LLM      iff the page invokes an LLM edge fn (ai-gateway/orchestrator/assist/semantic/voice)
  CI CI-CD          always-light (per-page slice = gate + journey-spec coverage)
  S  Security       iff the page writes (XSS/RLS/injection surface)
  RL Rate-Limit     iff the page invokes an AI edge fn OR writes (per-hive/per-user buckets)
  CA Caching        iff the page reads a truth view (heavy read to cache) OR invokes an edge fn (ai_cache)
  LB Load-Balance   iff the page uses realtime (channel/connection use) — heuristic: has a truth-view feed
  L  Logs           always (every page should capture its errors)
  AV Availability   iff the page depends on the backend (writes OR edge invokes) — degraded path matters

Output: a JSON/markdown per-page grid of LIVE|N/A(reason) cells + a COVERED/NEW tag per LIVE cell
(F/D/AU/S inherit the completed 8-phase/v3 gates = COVERED; C/RL/CA/L/AV = the NEW operational hunt).
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
CARDS = REPO / "substrate" / "page"
_PLACEHOLDER = re.compile(r"^\(?\s*(none|n/?a|nil|-)\b", re.I)
# LLM-bearing edge fns (the C layer trigger) — matches the substrate `Edge invokes:` tokens
LLM_FN = re.compile(r"(ai-gateway|ai-orchestrator|agentic-rag|analytics-orchestrator|shift-planner|"
                    r"asset-brain|project-orchestrator|semantic-search|voice-|listing-assist|-assist|"
                    r"benchmark-compute|embed-entry|grounding|rag-)", re.I)

LAYERS = ["F", "A", "D", "AU", "H", "C", "CI", "S", "RL", "CA", "LB", "L", "AV"]
# which layers the completed 8-phase/v3 bug-hunt already GATES per page (re-confirm, don't re-hunt)
COVERED = {"F", "D", "AU", "S"}
# the genuine NEW operational hunting surface this arc opens
NEW_OPS = {"C", "RL", "CA", "L", "AV"}
# light platform layers with only a thin per-page slice
PLATFORM_LIGHT = {"H", "CI", "LB"}


def _clean(items: list[str]) -> list[str]:
    return [x for x in items if x and not _PLACEHOLDER.match(x)]


def footprint(md: str) -> dict:
    def grab(label):
        m = re.search(rf"\*\*{re.escape(label)}\*\*[^:]*:\s*(.+)", md)
        if not m:
            return []
        return _clean([x.strip(" `") for x in re.split(r"[,·]", m.group(1)) if x.strip(" `")])
    return {
        "edge":   grab("Edge invokes"),
        "writes": grab("DB writes"),
        "rpc":    grab("RPC calls"),
        "views":  grab("Truth views read"),
    }


def live_layers(fp: dict) -> dict:
    edge, writes, views = fp["edge"], fp["writes"], fp["views"]
    has_edge = bool(edge)
    has_write = bool(writes)
    has_view = bool(views)
    has_llm = any(LLM_FN.search(e) for e in edge)
    backend = has_write or has_edge
    def cell(live, reason):
        return {"live": live, "reason": None if live else reason}
    return {
        "F":  cell(True, None),
        "A":  cell(has_edge, "no edge invoke"),
        "D":  cell(has_write or has_view, "no db read/write"),
        "AU": cell(has_write or has_view, "no tenant data"),
        "H":  cell(True, None),                       # ships in bundle (light per-page: CSP/headers)
        "C":  cell(has_llm, "no LLM edge call"),
        "CI": cell(True, None),                       # gate + journey coverage (light)
        "S":  cell(has_write, "no write surface"),
        "RL": cell(has_llm or has_write, "no rate-limited call"),
        "CA": cell(has_view or has_edge, "nothing heavy to cache"),
        "LB": cell(has_view, "no realtime/feed"),
        "L":  cell(True, None),
        "AV": cell(backend, "no backend dependency"),
    }


def tag(layer: str) -> str:
    if layer in COVERED:
        return "COVERED"
    if layer in NEW_OPS:
        return "NEW"
    return "LIGHT"


def main() -> int:
    if not CARDS.is_dir():
        print(f"no substrate cards at {CARDS}", file=sys.stderr)
        return 1
    pages = {}
    for card in sorted(CARDS.glob("*.md")):
        name = card.stem
        if name.startswith("_"):
            continue
        fp = footprint(card.read_text(encoding="utf-8", errors="replace"))
        cells = live_layers(fp)
        live = [L for L in LAYERS if cells[L]["live"]]
        pages[name] = {
            "footprint": {k: len(v) for k, v in fp.items()},
            "live_layers": live,
            "cells": cells,
            "new_ops_live": [L for L in live if L in NEW_OPS],
        }
    # rollup
    total_live = sum(len(p["live_layers"]) for p in pages.values())
    new_ops_cells = sum(len(p["new_ops_live"]) for p in pages.values())
    out = {
        "generated": "derive_saas_layer_matrix.py",
        "layers": LAYERS,
        "covered": sorted(COVERED), "new_ops": sorted(NEW_OPS), "platform_light": sorted(PLATFORM_LIGHT),
        "pages": pages,
        "summary": {"pages": len(pages), "live_cells": total_live, "new_ops_cells_to_hunt": new_ops_cells},
    }
    dest = REPO / "saas_layer_matrix.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{len(pages)} pages · {total_live} live layer-cells · {new_ops_cells} NEW operational cells to hunt (C/RL/CA/L/AV)")
    # top operational-density pages (the execution order)
    ranked = sorted(pages.items(), key=lambda kv: len(kv[1]["new_ops_live"]), reverse=True)
    print("Top operational-density pages (drive first):")
    for name, p in ranked[:12]:
        print(f"  {name:24} NEW-ops: {','.join(p['new_ops_live']) or '-':22} live: {','.join(p['live_layers'])}")
    print(f"wrote {dest.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
