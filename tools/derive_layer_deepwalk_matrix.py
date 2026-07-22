#!/usr/bin/env python3
"""
derive_layer_deepwalk_matrix.py - organize the D1-D26 deepwalk grid by the 13 ARCHITECTURAL LAYERS and
compute MEASURED % completion per page per layer (Ian 2026-07-22: "organize your dimensions according to
the architectural layers of my platform ... update the roadmap with percentage completion each dimension
per page").
=====================================================================================================
Reads deepwalk_grid.json (the flywheel's page x D-dim cells: ✅/🟡/⬜/n-a) and re-projects it onto the
13 full-stack SaaS production layers (COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 / FULLSTACK_COMPONENT_
LIBRARY): F A D AU H C CI S RL CA LB L AV. Deterministic + re-runnable (anti-drift: no hand-counts).
Cell score: ✅=1.0, 🟡=0.5, ⬜=0.0, n/a=excluded from the denominator.

Emits: (1) the DIM->LAYER map + which layers are grid-covered vs thin (the depth gaps); (2) per-layer
platform-wide %; (3) a per-page x per-layer % matrix. Prints markdown for the roadmap.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "deepwalk_grid.json"

# The 13 architectural layers (rows), canonical order + label.
LAYERS = [
    ("F",  "Frontend"), ("A",  "APIs/Edge"), ("D",  "Database"), ("AU", "Auth"),
    ("H",  "Hosting/Multitenancy"), ("C", "Cloud/LLM"), ("CI", "CI-CD"), ("S", "Security"),
    ("RL", "Rate-Limit"), ("CA", "Caching/CDN"), ("LB", "Load/Perf"), ("L", "Logs/Observability"),
    ("AV", "Availability/Recovery"),
]
LAYER_ORDER = [k for k, _ in LAYERS]

# D1-D26 deepwalk dimension -> its PRIMARY architectural layer. (A dim can touch several layers; it is
# filed under the layer whose CONCERN it primarily verifies, so each page x layer % is well-defined.)
DIM_LAYER = {
    "D1":  "F",   # render-parity (rendered == truth)
    "D2":  "D",   # data-integrity (the 11 DI classes)
    "D3":  "F",   # cross-surface receipt (write-on-A flips KPI-on-B) — a reactivity/display concern
    "D4":  "F",   # accessibility (axe/WCAG/keyboard/aria/contrast)
    "D5":  "F",   # mobile/touch/safe-area
    "D6":  "LB",  # Core Web Vitals (LCP/CLS/INP) — performance
    "D7":  "S",   # XSS/escHtml — security
    "D8":  "H",   # RLS/tenant-isolation + BOLA — multitenancy
    "D9":  "H",   # BFLA — multitenancy/authz
    "D10": "C",   # grounding/retrieval-quality — AI
    "D11": "C",   # prompt-injection — AI security
    "D12": "RL",  # cost/quota — rate-limit
    "D13": "C",   # fabrication — AI
    "D15": "F",   # empty/error/loading states
    "D17": "F",   # smoke (0 console errors)
    "D18": "AV",  # destructive-safety (confirm + no orphan cascade)
    "D19": "AU",  # idle-session (token-refresh, no stale 401)
    "D20": "AV",  # resilience (timeout-bounded fetch, 503 graceful, offline-queue)
    "D21": "L",   # observability/SLO
    "D22": "F",   # deep-interaction (modals/tabs/filters/wizards)
    "D23": "F",   # plain-language (rendered copy)
    "D24": "C",   # AI cross-hive isolation
    "D25": "C",   # PII-egress/redaction (AI memory) [also S]
    "D26": "C",   # memory/multi-turn recall
}
# Layers that the D1-D26 grid does NOT currently carry a dim for (the depth gaps to name):
#   A  (API-transport auth/resilience as a distinct walked dim), CI (the gate suite as a walked cell),
#   CA (caching/SW-cache freshness). These get a note, not a false 100%.
SCORE = {"✅": 1.0, "🟡": 0.5, "⬜": 0.0}


def main() -> int:
    if not GRID.exists():
        print("deepwalk_grid.json not found"); return 1
    g = json.loads(GRID.read_text(encoding="utf-8"))
    cells = g.get("cells", {})
    # A "page" surface is one that carries a FRONTEND-only dim (D17 smoke / D4 a11y / D1 render); AI-fn
    # (edge fn) surfaces only carry the AI dims. Derive the page set that way (grid's surfaces field is a
    # count, not a name list).
    FRONTEND_ONLY = {"D1", "D4", "D5", "D15", "D17", "D22", "D23"}
    page_surfaces = set()
    for key, cell in cells.items():
        if "|" in key:
            s, d = key.rsplit("|", 1)
            if d in FRONTEND_ONLY:
                page_surfaces.add(s)
    per_page_layer = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))  # page -> layer -> [score_sum, n]
    layer_tot = defaultdict(lambda: [0.0, 0])
    pages = set()
    for key, cell in cells.items():
        if "|" not in key:
            continue
        surface, dim = key.rsplit("|", 1)
        if surface not in page_surfaces:
            continue  # AI-fn (edge) surface — its AI dims roll into the C layer platform-wide separately
        layer = DIM_LAYER.get(dim)
        if not layer:
            continue
        state = cell.get("state") if isinstance(cell, dict) else cell
        if state not in SCORE:      # n/a or unknown -> excluded from the denominator
            continue
        pages.add(surface)
        per_page_layer[surface][layer][0] += SCORE[state]
        per_page_layer[surface][layer][1] += 1
        layer_tot[layer][0] += SCORE[state]
        layer_tot[layer][1] += 1

    print("## DIM -> LAYER map")
    by_layer = defaultdict(list)
    for d, l in sorted(DIM_LAYER.items(), key=lambda x: int(x[0][1:])):
        by_layer[l].append(d)
    for k, name in LAYERS:
        dims = ", ".join(by_layer.get(k, [])) or "(no grid dim — DEPTH GAP: add a walked cell)"
        print(f"- **{k} {name}**: {dims}")

    print("\n## Per-LAYER platform-wide % (avg across pages, grid-measured)")
    for k, name in LAYERS:
        s, n = layer_tot.get(k, [0.0, 0])
        pct = (100.0 * s / n) if n else None
        print(f"- {k} {name}: {'%.1f%%' % pct if pct is not None else 'n/a (no grid dim)'}  ({n} cells)")

    print(f"\n## Per-PAGE x per-LAYER % ({len(pages)} pages)")
    hdr = "| Page | " + " | ".join(LAYER_ORDER) + " |"
    print(hdr); print("|" + "---|" * (len(LAYER_ORDER) + 1))
    for page in sorted(pages):
        row = [page]
        for k in LAYER_ORDER:
            s, n = per_page_layer[page].get(k, [0.0, 0])
            row.append(("%d" % round(100.0 * s / n)) if n else "·")
        print("| " + " | ".join(row) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
