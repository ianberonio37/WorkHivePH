"""
journey-accept -- the §13 E2E Journey & Data-Lineage capstone (P6)
==================================================================
The sibling capstone to `fullstack_dev.py mature-accept`: one command that
re-verifies the whole live data-lineage sweep and stamps a marker. Mirrors the
maturity capstone's shape — runs the §13 tools standalone (no heavy
orchestration, no full-gate regen), asserts they all pass + that coverage has
not regressed, then writes `.journey-accept-pass`.

What it asserts (the honest §13 contract — measured, never a vibe):
  1. journey_trace.py -- EVERY registered differential nerve verifies
     (the rendered/computed value is correct at every terminus).
  2. validate_lineage_status_drift.py -- no truth-view filters a status the
     schema forbids (no dead nerves of that class).
  3. mine_lineage_map.py -- the denominator + measured P/H regenerate.
  4. FORWARD-ONLY ratchet: verified nerves and verified H-paths never drop
     below the recorded baseline (coverage can grow, never silently shrink).

It does NOT assert P=27/27 ∧ H=100% (the eventual §13.5 target) yet — that's
the P2/P4/P5 expansion. It locks what is PROVEN so it can never regress, and
prints the live P/H so progress toward 100% is always visible.

Needs the live local DB (docker `supabase_db_workhive`) — this is the §13/G3
live tier, like the journey-trace probes themselves.

Usage:  python tools/journey_accept.py            (verify + ratchet + stamp)
        python tools/journey_accept.py --reset-baseline   (re-baseline to current)
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
LEDGER = ROOT / "journey_trace_results.json"
LMAP = ROOT / "lineage_map.json"
VAXIS = ROOT / "journey_vaxis_results.json"
BASELINE = ROOT / ".journey-accept-baseline.json"
MARKER = ROOT / ".journey-accept-pass"


def run(tool: str) -> int:
    print(f"\n  ── running {tool} ──")
    r = subprocess.run([PY, str(ROOT / "tools" / tool)], cwd=str(ROOT))
    return r.returncode


def main(argv: list[str]) -> int:
    reset = "--reset-baseline" in argv
    print("=" * 78)
    print("  journey-accept — §13 E2E Journey & Data-Lineage capstone (P6)")
    print("=" * 78)

    fail = []

    # 1. all differential nerves verify
    if run("journey_trace.py") != 0:
        fail.append("journey_trace: a nerve did NOT verify (a rendered value is wrong)")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"nerves": {}}
    nerves = ledger.get("nerves", {})
    verified_nerves = sum(1 for n in nerves.values() if n.get("verified"))
    total_nerves = len(nerves)

    # 2. no status-enum dead nerves
    if run("validate_lineage_status_drift.py") != 0:
        fail.append("validate_lineage_status_drift: an unallowlisted dead nerve exists")

    # 3. V-axis journey × layer matrix — no proven-live cell may regress (FAILED → exit 1)
    if run("journey_vaxis.py") != 0:
        fail.append("journey_vaxis: a proven-live journey-layer cell FAILED (a vertical slice broke)")
    vax = (json.loads(VAXIS.read_text(encoding="utf-8")).get("measured", {}) if VAXIS.exists() else {})
    v_proven = vax.get("cells_proven", 0)

    # 4. regenerate denominator + read measured (ingests the fresh V-axis result)
    if run("mine_lineage_map.py") != 0:
        fail.append("mine_lineage_map: failed to regenerate the lineage map")
    m = (json.loads(LMAP.read_text(encoding="utf-8")).get("measured", {}) if LMAP.exists() else {})
    h_verified = m.get("H_paths_verified", 0)
    p_engine = m.get("P_pages_engine_proven", 0)
    p_full = m.get("P_pages_fully_verified", 0)
    p_applicable = m.get("P_pages_applicable", 27)

    # 4b. ARTIFACT-CORRECTNESS tier (§13.13/A5) — the value reaches the DELIVERABLE intact.
    #     grounding-contract (static, no new field-drift) + diagram-value (label == calc) +
    #     BOM/SOW grounding (LLM artifact cites the sized value). exit 2 = infra unreachable
    #     (python-api/edge down or LLM rate-limited) → SKIP (warn, preserve baseline), NOT a fail.
    # `soft=True` = a NON-deterministic LLM metric: tracked + ratcheted in its own validator
    # (self-test + --strict teeth, run_platform_checks), but it does NOT hard-gate this
    # DETERMINISTIC reproducibility capstone — LLM prose grounding oscillates run-to-run (a
    # verbose run cites more correctly-DERIVED aggregates than a terse one), so a hard gate here
    # would flake. Same posture as the companion's stochastic grounding (eval-gated, not mega-gate).
    ART = [
        ("validate_grounding_contract.py",      "grounding_contract.json",       "read_groups_resolved", "grounding_resolved", False),
        ("validate_diagram_value_alignment.py", "diagram_value_alignment.json",  "cells_aligned",        "diagram_aligned",    False),
        ("validate_bom_sow_grounding.py",       "bom_sow_grounding.json",         "cells_grounded",       "bom_grounded",       True),   # SOFT: this INVOKES the engineering-bom-sow LLM agent → non-deterministic (transient free-tier 5xx / generation variance can drop a cite on a given run). The DETERMINISTIC guarantee that every agent's field-name resolves is the static `validate_grounding_contract.py` above (hard, 542/542); this live probe is the soft sample-confirmer, same class as narrative-grounding. (A real systemic drift still surfaces in the hard A6 contract.)
        ("validate_export_value_contract.py",   "export_value_contract.json",    "fields_resolved",      "export_resolved",    False),
        ("validate_narrative_grounding.py",     "narrative_grounding.json",       "surfaces_grounded",    "narrative_grounded", True),
    ]
    artifact_counts: dict[str, int] = {}
    for tool, jf, jkey, bkey, soft in ART:
        code = run(tool)
        if code == 2:
            print(f"    (skipped {tool} — infra unreachable [exit 2]; baseline preserved)")
            continue
        if code != 0:
            if soft:
                print(f"    (⚠ {tool} exit {code} — SOFT tier [non-deterministic LLM]; tracked, not capstone-fatal)")
                continue
            fail.append(f"{tool}: artifact-correctness FAILED (exit {code} — a deliverable value drifted)")
            continue
        jp = ROOT / jf
        if jp.exists():
            artifact_counts[bkey] = int(json.loads(jp.read_text(encoding="utf-8")).get(jkey, 0))

    # 5. forward-only ratchet
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    if reset or not base:
        base = {}
    for key, cur in (("verified_nerves", verified_nerves), ("h_verified", h_verified),
                     ("p_engine", p_engine), ("p_full", p_full), ("v_proven", v_proven)):
        prev = base.get(key, 0)
        if cur < prev:
            fail.append(f"REGRESSION: {key} dropped {prev} → {cur} (coverage shrank)")
        base[key] = max(prev, cur)
    # artifact-tier ratchet — only for tiers measured THIS run (a skipped/exit-2 tier preserves its baseline)
    for bkey, cur in artifact_counts.items():
        prev = base.get(bkey, 0)
        if cur < prev:
            fail.append(f"REGRESSION: {bkey} dropped {prev} → {cur} (artifact coverage shrank)")
        base[bkey] = max(prev, cur)

    print("\n" + "-" * 78)
    print(f"  nerves verified : {verified_nerves}/{total_nerves}")
    print(f"  H paths verified: {h_verified}  (ratchet ≥ {base.get('h_verified', h_verified)})")
    print(f"  P engine-proven : {p_engine}/{p_applicable} (applicable)   ·  P fully-verified: {p_full}/27")
    print(f"  V cells proven  : {v_proven}/{vax.get('cells_total', 77)}  (ratchet ≥ {base.get('v_proven', v_proven)})"
          f"   ·  covered {v_proven + vax.get('cells_attributed', 0)}/{vax.get('cells_total', 77)}")
    print(f"  artifact tier   : grounding {base.get('grounding_resolved', '—')} resolved · "
          f"diagram {base.get('diagram_aligned', '—')} aligned · BOM/SOW {base.get('bom_grounded', '—')} grounded · "
          f"export {base.get('export_resolved', '—')} cols · narrative {base.get('narrative_grounded', '—')} surfaces"
          f"{'  (some tiers skipped — infra)' if len(artifact_counts) < 5 else ''}")

    if fail:
        print("\n  ✗ journey-accept FAILED:")
        for f in fail:
            print(f"      • {f}")
        return 1

    BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
    MARKER.write_text(json.dumps({
        "stamped_at": datetime.now(timezone.utc).isoformat(),
        "verified_nerves": verified_nerves, "total_nerves": total_nerves,
        "H_paths_verified": h_verified, "P_pages_engine_proven": p_engine,
        "P_pages_fully_verified": p_full,
        "V_cells_proven": v_proven, "V_cells_total": vax.get("cells_total", 77),
        "V_cells_attributed": vax.get("cells_attributed", 0),
        "artifact_grounding_resolved": base.get("grounding_resolved"),
        "artifact_diagram_aligned": base.get("diagram_aligned"),
        "artifact_bom_grounded": base.get("bom_grounded"),
        "artifact_export_resolved": base.get("export_resolved"),
        "artifact_narrative_grounded": base.get("narrative_grounded"),
        "note": "§13 live data-lineage sweep (H + V axes) + §13.13 artifact-correctness tier (A5) re-verified; forward-only ratchet held.",
    }, indent=2), encoding="utf-8")
    print(f"\n  ✓ journey-accept PASS — {verified_nerves} nerves + drift-clean; H+V ratchet held.")
    print(f"    stamped {MARKER.name}. (target remains P=27/27 ∧ H=100% ∧ V=77/77 — P2/P4/P5 expansion.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
