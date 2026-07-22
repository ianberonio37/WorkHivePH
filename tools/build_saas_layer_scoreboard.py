#!/usr/bin/env python3
"""
build_saas_layer_scoreboard.py - the anti-drift compass for PER_PAGE_SAAS_LAYER_BUGHUNT_ROADMAP.md.
====================================================================================================
Regenerates PER_PAGE_SAAS_LAYER_SCOREBOARD.md — every (page × 13-SaaS-layer) LIVE cell tagged
COVERED (a registered gate locks it) · OPEN (to hunt) · N/A (no footprint) — and holds the OPEN
OPERATIONAL-cell count as a FORWARD-ONLY CEILING so the long multi-session hunt can't drift.

Mirrors build_bughunt_scoreboard.py (which carried the 8-phase hunt to 100% with 0 drift). Two modes:
  (default)   regenerate the scoreboard .md + saas_layer_open_baseline.json (first run seeds it).
  --check     CI gate `saas-layer-scoreboard`: FAIL if the OPEN operational-cell count ROSE above the
              baseline (a new page / edge-fn / regressed gate escaped coverage) — drift caught by CI.
  --accept    ratchet the baseline DOWN to the current OPEN count (after gating cells).

COVERAGE REGISTRY (below): which layer is COVERED by which registered gate. F/D/AU/S + the light
platform layers (H/CI/LB) inherit the COMPLETED 8-phase/platform gates. The operational layers
(C/RL/CA/L/AV) start OPEN and flip COVERED as this arc registers their per-page probes — EDIT THIS DICT
when a new operational gate lands (that is how a cell ratchets to COVERED).
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from derive_saas_layer_matrix import footprint, live_layers, LAYERS, NEW_OPS, CARDS  # reuse the deriver

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["build_saas_layer_scoreboard"]
REPO = Path(__file__).resolve().parent.parent
SCOREBOARD = REPO / "PER_PAGE_SAAS_LAYER_SCOREBOARD.md"
BASELINE = REPO / "saas_layer_open_baseline.json"

# layer -> the registered gate(s) that COVER it (a cell is COVERED iff its layer has an entry here).
# F/D/AU/S + H/CI/LB inherit the completed 8-phase/platform gates. C/RL/CA/L/AV start EMPTY (OPEN) and
# gain a gate id as this arc builds each operational probe — appending here ratchets those cells COVERED.
COVERAGE = {
    "F":  ["page-battery", "arc-w-visual"],
    "A":  ["edge-fn-auth-gate"],                       # caller-gate done; per-page contract/trace-id = a sub-open (tracked in the ledger)
    "D":  ["crud-rollback", "read-battery", "truth-view-read-isolation"],
    "AU": ["role-gate-server-backstop", "hive-isolation", "attribution-pinned"],
    "H":  ["csp", "seo-technical"],                    # platform-light: CSP/headers present
    "C":  ["no_ai_gateway_bypass", "rate-limit-handling", "perf_l5_llm_resilience"],  # REUSE: no page bypasses the central ai-gateway front-door (whose edge fns use the shared free-tier fallback chain) + whAiError client 503 msg + server resilience
    "CI": ["bughunt-scoreboard", "auto-discovery"],   # platform-light: gate + journey coverage
    "S":  ["innerhtml-eschtml", "dom-xss-fields", "role-gate-server-backstop"],
    "RL": ["rate-limit-handling", "perf_l5_llm_resilience"],  # central whAiError 429 mapper + server 429-graceful gate
    "CA": ["mine-cache-name-drift", "read-battery", "no_ai_gateway_bypass"],  # REUSE: central ai_cache (LLM repeat cache in ai-gateway) + cache-bust discipline (CACHE_NAME drift) + read-battery proves dynamic reads render FRESH==DB (no stale); SW shell cache = report-sender PWA surface
    "LB": ["realtime-subscription-consistency"],      # platform-light: channel cleanup
    "L":  ["error-capture"],                           # forward-ratchet gate (baseline 24 swallow backlog, driving → 0)
    "AV": ["degraded-state-central", "error-capture", "page-battery"],  # central offline-banner adoption + L-backbone + P12
}
SYM = {"COVERED": "✓", "OPEN": "○", "N/A": "·"}


def cell_status(layer: str, live: bool) -> str:
    if not live:
        return "N/A"
    return "COVERED" if COVERAGE.get(layer) else "OPEN"


def build() -> dict:
    pages = {}
    for card in sorted(CARDS.glob("*.md")):
        if card.stem.startswith("_"):
            continue
        cells = live_layers(footprint(card.read_text(encoding="utf-8", errors="replace")))
        row = {L: cell_status(L, cells[L]["live"]) for L in LAYERS}
        pages[card.stem] = row
    # OPEN operational cells (only C/RL/CA/L/AV count toward the ratchet — the genuine hunt)
    open_ops = sum(1 for r in pages.values() for L in NEW_OPS if r[L] == "OPEN")
    covered = sum(1 for r in pages.values() for L in LAYERS if r[L] == "COVERED")
    na = sum(1 for r in pages.values() for L in LAYERS if r[L] == "N/A")
    return {"pages": pages, "open_ops": open_ops, "covered": covered, "na": na}


def render_md(data: dict) -> str:
    lines = [
        "# Per-Page SaaS-Layer-Stack Bug-Hunt Scoreboard — anti-drift compass",
        "",
        f"_Generated by `tools/build_saas_layer_scoreboard.py`. {len(data['pages'])} pages · "
        f"**{data['open_ops']} OPEN operational cells** (C/RL/CA/L/AV, the hunt) · {data['covered']} COVERED · "
        f"{data['na']} N/A. The OPEN count is a FORWARD-ONLY ceiling (gate `saas-layer-scoreboard`)._",
        "",
        "Cell: `✓`=COVERED (registered gate) · `○`=OPEN (to hunt) · `·`=N/A (no footprint). "
        "Operational layers **C RL CA L AV** are the new work; **F A D AU H CI S LB** inherit the completed "
        "8-phase/platform gates.",
        "",
        "| Page | F | A | D | AU | H | C | CI | S | RL | CA | LB | L | AV | OPEN-ops |",
        "|---|" + "|".join([":-:"] * 13) + "|--:|",
    ]
    for name, row in sorted(data["pages"].items(), key=lambda kv: -sum(1 for L in NEW_OPS if kv[1][L] == "OPEN")):
        cells = " | ".join(SYM[row[L]] for L in LAYERS)
        openn = sum(1 for L in NEW_OPS if row[L] == "OPEN")
        lines.append(f"| {name} | {cells} | {openn or ''} |")
    lines += [
        "",
        f"**OPEN operational cells = {data['open_ops']}** (the drive target → 0). Each flips `○→✓` when its "
        "per-page operational probe is built + registered (edit `COVERAGE` in the builder). "
        "`saas-layer-scoreboard --check` FAILs if this count rises.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    data = build()
    if "--check" in sys.argv:
        if not BASELINE.exists():
            print(f"{R}FAIL: no baseline — run build_saas_layer_scoreboard.py (no flag) to seed it.{X}")
            return 1
        base = json.loads(BASELINE.read_text()).get("open_ops", 10**9)
        if data["open_ops"] > base:
            print(f"{R}FAIL: SaaS-layer OPEN operational cells ROSE {base}→{data['open_ops']} — a new page/"
                  f"edge-fn or a regressed gate escaped coverage (drift). Cover it or re-accept intentionally.{X}")
            return 1
        print(f"{G}PASS: SaaS-layer scoreboard — OPEN operational cells {data['open_ops']} ≤ baseline {base} "
              f"(forward ratchet held).{X}")
        return 0
    if "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"open_ops": data["open_ops"]}, indent=2), encoding="utf-8")
        print(f"{G}ratcheted baseline → OPEN operational cells = {data['open_ops']}.{X}")
    SCOREBOARD.write_text(render_md(data), encoding="utf-8")
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"open_ops": data["open_ops"]}, indent=2), encoding="utf-8")
        print(f"seeded baseline → OPEN operational cells = {data['open_ops']}.")
    print(f"wrote {SCOREBOARD.name}: {len(data['pages'])} pages · {data['open_ops']} OPEN ops · "
          f"{data['covered']} COVERED · {data['na']} N/A")
    return 0


if __name__ == "__main__":
    sys.exit(main())
