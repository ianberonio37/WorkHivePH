#!/usr/bin/env python3
"""
ufai_pillar_map.py — the COMPREHENSIVE UFAI per-page deepwalk %-board (PDDA §11).

WHY: UFAI = 4 PILLARS (Usability / Functionality / Adaptability / Internal-control), decomposed into
25 canonical sub-layers (COMPREHENSIVE_STUDY_FULLSTACK_GATE §13.20, from ISO 25010:2023 / WCAG 2.2 /
Nielsen 10 / OWASP). The 89-dim A-Z rubric lens (family_rubric_scoreboard.json) already MEASURES most
of the U + A sub-layers per page; the F + I behavioural sub-layers are measured by registered gates.
This tool AGGREGATES the existing lens evidence onto the 25 sub-layers PER PAGE (retrieve-first, no
re-survey) → the baseline UFAI %-board → and FLAGS the shallow cells (a sub-layer with no lens
instrument on a page = a depth gap to deepen: build a detector / live-probe, or confirm a gate owns it).

USAGE: python tools/ufai_pillar_map.py [--json] [--shallow]
OUTPUT: ufai_pillar_map.json — {pages:{page:{pillar:{sublayer:{pct,dims}}}}, summary, shallow[]}
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "family_rubric_scoreboard.json"
OUT = ROOT / "ufai_pillar_map.json"

# The 25 canonical UFAI sub-layers -> the LENS dims that measure each (family_rubric_scoreboard).
# A sub-layer with an empty dim list is GATE-owned (measured by a registered validator, not the lens) —
# noted, not a gap. A sub-layer that SHOULD have lens coverage but a page lacks the dim = shallow cell.
SUBLAYERS = {
    "U1_recognizability":   ["A1", "A2"],
    "U2_operability":       ["Z3", "T3", "T8"],
    "U3_status_feedback":   ["E2", "PP1", "D2", "PP2"],
    "U4_error_protection":  ["J3", "Y2"],
    "U5_inclusivity_a11y":  ["C2", "C4", "N1", "B5"],
    "U6_consistency":       ["S1", "S2", "S3", "D3", "G4", "R1", "R3", "C1", "V1"],
    "U7_mobile_field":      ["Z1", "Z2", "T1", "T2", "T4", "T5", "T6", "T7", "F1", "K2"],
    "F1_completeness":      ["D1"],            # + DOM-ref-integrity gate
    "F2_correctness":       [],                # gate: render_sweep / calc validators (Arc A/B/C credit)
    "F3_appropriateness":   ["X1", "E4"],
    "F4_nav_flow":          ["W1", "X3"],      # + cross-page-flow / deeplink gates
    "F5_round_trip":        [],                # gate: capture_roundtrip + write gates
    "F6_degraded_states":   ["E2", "Y1", "X1"],
    "A1_responsive":        ["Z2", "I1"],
    "A2_component_ds":      ["S2", "S3", "R1"],
    "A3_configurability":   ["G5"],            # G5 measured by journey-ux gate
    "A4_state_mgmt":        ["G5"],            # G5a filter-persist + OC-guard gates
    "A5_extensibility":     [],                # gate: nav-registry / component-registry
    "A6_offline_pwa":       ["Y1", "RE1"],     # + Y1b queue (journey gate) + PWA gate
    "I1_auth_gating":       [],                # gate: per-page auth-gate
    "I2_role_permission":   [],                # gate: ui-only-gate + edge-fn-auth
    "I3_tenancy_isolation": [],                # gate: hive-write-isolation + xhive
    "I4_client_validation": ["Z1"],            # + input-guards + D5 gates
    "I5_auditability":      [],                # gate: audit-log surfacing + leave-audit
    "I6_safe_by_default":   ["J3", "S4", "AI4"],  # + secret-scanner + no-bypass gates
}
PILLAR_OF = lambda sl: sl[0]  # 'U','F','A','I'
GATE_OWNED = {k for k, v in SUBLAYERS.items() if not v}


def main() -> int:
    if not BOARD.exists():
        print("no family_rubric_scoreboard.json — run tools/family_rubric_sweep.mjs first"); return 1
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    pages = board.get("pages", {})
    out_pages = {}
    shallow = []
    pillar_tot = {"U": [], "F": [], "A": [], "I": []}
    for page, pg in pages.items():
        dim_pct = {d["dim"]: d.get("pct") for d in pg.get("dims", []) if d.get("kind") == "MEASURED" and d.get("pct") is not None}
        dim_na = {d["dim"] for d in pg.get("dims", []) if d.get("kind") == "N/A"}
        page_map = {}
        for sl, dims in SUBLAYERS.items():
            present = [d for d in dims if d in dim_pct]
            na_only = dims and all((d in dim_na or d not in dim_pct) for d in dims) and not present
            if present:
                pct = round(sum(dim_pct[d] for d in present) / len(present))
                page_map[sl] = {"pct": pct, "dims": present}
                pillar_tot[PILLAR_OF(sl)].append(pct)
            elif sl in GATE_OWNED:
                page_map[sl] = {"pct": None, "dims": [], "owner": "gate"}
            elif na_only:
                page_map[sl] = {"pct": None, "dims": [], "owner": "na-on-page"}
            else:
                page_map[sl] = {"pct": None, "dims": [], "owner": "SHALLOW"}
                shallow.append(f"{page}:{sl}")
        out_pages[page] = page_map
    def avg(xs): return round(sum(xs) / len(xs)) if xs else None
    summary = {"pillars": {p: avg(v) for p, v in pillar_tot.items()},
               "shallow_cells": len(shallow), "pages": len(out_pages),
               "gate_owned_sublayers": sorted(GATE_OWNED)}
    OUT.write_text(json.dumps({"summary": summary, "shallow": sorted(set(shallow)), "pages": out_pages}, indent=1), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(summary, indent=2)); return 0
    print("UFAI pillar %-board (lens evidence aggregated onto the 25 sub-layers):")
    for p in ("U", "F", "A", "I"):
        print(f"  {p}: {summary['pillars'][p]}%  ({len([s for s in SUBLAYERS if s[0]==p])} sub-layers)")
    print(f"  gate-owned sub-layers (F/I behavioural, measured by validators not the lens): {len(GATE_OWNED)}")
    print(f"  SHALLOW cells (a lens sub-layer with no dim on a page): {len(set(shallow))}")
    print("  ⚠ this is the COARSE baseline (lens slice). The DEEP verification — live keyboard/focus/44px")
    print("    (U2), axe a11y (U5), resize 360-1920 (A1), CRUD round-trip (F5), multi-role/hive (I2/I3) —")
    print("    is the §11 per-page live deepwalk; coarse-100 does NOT mean deep-100 (§11 drive).")
    if "--shallow" in sys.argv and shallow:
        from collections import Counter
        by_sl = Counter(s.split(":", 1)[1] for s in shallow)
        print("  shallow by sub-layer:", dict(by_sl.most_common()))
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
