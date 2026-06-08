"""
run_battery_family.py  —  ④ PLATFORM battery: the family orchestrator.
================================================================================
BATTERY_ARCHITECTURE.md says the platform altitude is "aggregate the page runs +
the cross-page invariants into ONE run + verdict." This is that runner. It drives
the deterministic (headless) half of the battery FAMILY in dependency order and
writes one report + one verdict + the live/MCP to-do the family can't run without
a browser.

It is NOT `run_platform_checks.py` (that is the L0 VALIDATOR gate — the 300+
static validators + readiness). This is the BATTERY family — the altitude audits
(component consistency · IA redundancy · IA rubric · persona walkthrough · journey
plan). They are complementary: validators gate correctness; batteries surface
usability / consistency / IA for human disposition.

WHAT IT RUNS (headless, deterministic), in order:
  ① Component   tools/survey_component_consistency.py     → component_consistency_*
  ④ IA map      tools/survey_ia_redundancy.py             → ia_inventory_corpus.json
  ④ IA rubric   tools/score_ia_streamlining.py            → streamlining_plan.md + candidates
  ④/③ Persona   tools/ux_persona_walkthrough.py           → ux_persona_walkthrough.md
  ③ Journey     tools/plan_journey_battery.py             → journey_battery_plan.md

WHAT STAYS LIVE (listed as MCP to-do, can't run headless):
  ② Page kernel       __UFAI.run() per page (axe/CWV/parity)
  ① Component confirm  __UFAI.component('.simple-card') DOM-accurate
  ③ Journey execution  __JOURNEY across the planned flows
  behaviour subject    __CSB companion stack + validate_companion_stack.py

This is **Mega Gate G3** (see UNIFIED_MEGA_GATE.md + BATTERY_ARCHITECTURE.md §7b).
With `--gate` it becomes a forward-only ratchet (Rule B): it compares the run's
signals to `battery_family_baseline.json` and exits 1 on a regression — a new
component missing-required DEFECT, or surfaced candidates rising above baseline
(dispose them, or `--update-baseline` to accept). The baseline auto-tightens on
reduction. Drop this between G2 and "commit" in the Mega Gate sequence.

OUTPUT:  battery_family_report.md  +  battery_family_baseline.json (G3 persistence)
EXIT:    plain: 0 = all runners executed, 1 = a runner failed.
         --gate: 0 = at/under baseline & 0 new DEFECTs; 1 = regression.
USAGE:   python tools/run_battery_family.py                # run + surface
         python tools/run_battery_family.py --gate         # pre-commit ratchet (G3)
         python tools/run_battery_family.py --update-baseline  # re-freeze (accept)
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
BASELINE = ROOT / "battery_family_baseline.json"   # G3 persistence artefact (Mega Gate Rule B)

RUNNERS = [
    ("① Component", "Interface", "tools/survey_component_consistency.py", "component_consistency_report.md"),
    ("④ IA map", "Interface", "tools/survey_ia_redundancy.py", "streamlining_survey.md"),
    ("④ IA rubric", "Interface", "tools/score_ia_streamlining.py", "streamlining_plan.md"),
    ("③/④ Persona", "Interface", "tools/ux_persona_walkthrough.py", "ux_persona_walkthrough.md"),
    ("③ Journey", "Interface", "tools/plan_journey_battery.py", "journey_battery_plan.md"),
]


def run_one(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        return {"ok": False, "exit": None, "tail": f"(missing: {rel})"}
    r = subprocess.run([PY, str(p)], cwd=str(ROOT), capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    tail = "\n".join(out.strip().splitlines()[-6:])
    return {"ok": r.returncode == 0, "exit": r.returncode, "tail": tail}


def jload(name: str):
    p = ROOT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def signals_from(ia_groups, comp_groups, ia_cand, comp_cand) -> dict:
    """The G3 gate signals — what the ratchet watches."""
    return {
        # hard: a component instance missing a REQUIRED sub-part = a real shape DEFECT
        "component_missing_required": sum(len(r.get("missing_required", []))
                                          for r in comp_groups.get("primitives", {}).values()),
        # ratchet: surfaced candidates awaiting disposition (Rule B — only moves down)
        "candidates_total": len(ia_cand) + len(comp_cand),
        "ia_candidates": len(ia_cand),
        "component_candidates": len(comp_cand),
    }


def gate_eval(sig: dict) -> tuple[int, list[str], dict | None]:
    """Forward-only ratchet vs battery_family_baseline.json (Mega Gate G3, Rule B).
    Returns (exit_code, messages, new_baseline_or_None_to_write)."""
    msgs = []
    base = None
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = None
    if base is None:
        msgs.append(f"G3 baseline SEEDED → {BASELINE.name} (candidates={sig['candidates_total']}, "
                    f"missing-required={sig['component_missing_required']}). First run always passes.")
        return 0, msgs, sig

    fail = False
    # HARD: real component DEFECTs must not grow.
    if sig["component_missing_required"] > base.get("component_missing_required", 0):
        fail = True
        msgs.append(f"🔴 component missing-required rose {base.get('component_missing_required', 0)} "
                    f"→ {sig['component_missing_required']} — a primitive lost a required sub-part (fix inline).")
    # RATCHET (Rule B): surfaced candidates may only move DOWN. New ones must be
    # disposed (or the baseline intentionally re-frozen), never silently grow.
    if sig["candidates_total"] > base.get("candidates_total", 0):
        fail = True
        msgs.append(f"🔴 surfaced candidates rose {base.get('candidates_total', 0)} → {sig['candidates_total']} "
                    "— dispose the new finding(s) via promotion_dispositions.json, or "
                    "`--update-baseline` if intentionally accepted.")
    new_base = None
    if not fail and sig["candidates_total"] < base.get("candidates_total", 0):
        # auto-tighten on reduction (same as clone_debt_baseline.json doctrine).
        msgs.append(f"🟢 candidates fell {base.get('candidates_total', 0)} → {sig['candidates_total']} "
                    "— baseline auto-tightened (Rule B: baselines only move down).")
        new_base = sig
    if not fail and not new_base:
        msgs.append(f"🟢 G3 at baseline (candidates={sig['candidates_total']}, "
                    f"missing-required={sig['component_missing_required']}).")
    return (1 if fail else 0), msgs, new_base


def main() -> int:
    ap = argparse.ArgumentParser(description="④ Platform / G3 battery-family orchestrator.")
    ap.add_argument("--gate", action="store_true",
                    help="forward-only ratchet vs battery_family_baseline.json; exit 1 on regression (Mega Gate G3)")
    ap.add_argument("--update-baseline", action="store_true",
                    help="re-freeze battery_family_baseline.json to the current signals (intentional accept)")
    args = ap.parse_args()

    results = []
    for (name, subject, rel, report) in RUNNERS:
        res = run_one(rel)
        results.append({"name": name, "subject": subject, "rel": rel, "report": report, **res})
        mark = "ok " if res["ok"] else "FAIL"
        print(f"  [{mark}] {name:14s} {rel}")

    # headline tallies from the corpus/candidate files the runners wrote
    ia = jload("ia_inventory_corpus.json") or {}
    ia_groups = ia.get("groups", {})
    comp = jload("component_consistency_corpus.json") or {}
    comp_groups = comp.get("groups", {})
    ia_cand = (jload("ia_streamlining_candidates.json") or {}).get("candidates", [])
    comp_cand = (jload("component_consistency_candidates.json") or {}).get("candidates", [])
    journey = jload("journey_battery_plan.json") or {}

    n_info = len(ia_groups.get("info_redundancy_by_key", [])) + len(ia_groups.get("info_redundancy_by_label", []))
    n_theme = len(ia_groups.get("info_theme_clusters", []))
    n_comp_prim = len(comp_groups.get("primitives", {}))
    n_comp_drift = sum(len(r.get("missing_required", [])) for r in comp_groups.get("primitives", {}).values())

    all_ran = all(r["ok"] for r in results)
    total_cand = len(ia_cand) + len(comp_cand)

    L = []
    L.append("# Battery Family Report — ④ Platform run\n")
    L.append("> One run across the deterministic battery FAMILY (BATTERY_ARCHITECTURE.md). SURFACE-only:"
             " the verdict is whether every altitude runner EXECUTED, plus the count of candidates"
             " surfaced for disposition — not a pass/fail on findings.\n")
    verdict = "🟢 ALL RUNNERS EXECUTED" if all_ran else "🔴 A RUNNER FAILED"
    L.append(f"## Verdict: {verdict}  ·  {total_cand} candidate(s) surfaced\n")
    L.append(f"- Component primitives audited: **{n_comp_prim}** ({n_comp_drift} missing-required drift)")
    L.append(f"- IA redundancy: **{n_info}** exact/key groups · **{n_theme}** theme clusters")
    L.append(f"- Candidates queued-able: **{len(ia_cand)}** IA + **{len(comp_cand)}** component")
    L.append(f"- Journeys planned: **{len(journey.get('journeys', []))}** (execution is live)\n")

    L.append("## Altitude × runner status\n")
    L.append("| Altitude | Subject | Runner | Status | Report |")
    L.append("|---|---|---|---|---|")
    for r in results:
        st = "🟢 ran" if r["ok"] else f"🔴 exit {r['exit']}"
        L.append(f"| {r['name']} | {r['subject']} | `{r['rel']}` | {st} | [{r['report']}]({r['report']}) |")
    L.append("")

    L.append("## Live / MCP to-do (can't run headless)\n")
    L.append("- **② Page kernel** — `__UFAI.run({pageId,role,experience})` per page (axe / CWV / parity).")
    L.append("- **① Component confirm** — `__UFAI.component('.simple-card')` (DOM-accurate shape).")
    L.append("- **③ Journey execution** — drive `journey_battery_plan.md` with `__JOURNEY` across the flows.")
    L.append("- **Behaviour subject** — `__CSB` companion stack + `validate_companion_stack.py` (G0).")
    L.append("")
    L.append("## How to queue what was surfaced\n")
    L.append("```\npython ufai_ingest.py ia_streamlining_candidates.json\n"
             "python ufai_ingest.py component_consistency_candidates.json\n```")
    L.append("Then dispose via `promotion_dispositions.json` (engine proposes, you dispose).")

    (ROOT / "battery_family_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\nBattery family: {verdict}  ·  {total_cand} candidates surfaced "
          f"({len(ia_cand)} IA + {len(comp_cand)} component)")
    print(f"  -> battery_family_report.md")

    sig = signals_from(ia_groups, comp_groups, ia_cand, comp_cand)

    # --update-baseline: intentionally re-freeze (e.g. after accepting new findings)
    if args.update_baseline:
        sig_out = {**sig, "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "_doc": "Mega Gate G3 (battery family) frozen baseline. Rule B: only moves down. "
                           "run_battery_family.py --gate ratchets against this."}
        BASELINE.write_text(json.dumps(sig_out, indent=2) + "\n", encoding="utf-8")
        print(f"  baseline re-frozen → {BASELINE.name} (candidates={sig['candidates_total']})")
        return 0 if all_ran else 1

    # --gate: forward-only ratchet → exit 1 on regression (Mega Gate G3 step)
    if args.gate:
        if not all_ran:
            print("  🔴 G3 GATE FAIL — a runner did not execute (see above).")
            return 1
        code, msgs, new_base = gate_eval(sig)
        if new_base is not None:
            out = {**new_base, "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "_doc": "Mega Gate G3 (battery family) frozen baseline. Rule B: only moves down."}
            BASELINE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print("  " + "\n  ".join(msgs))
        print(f"  G3 GATE {'PASS' if code == 0 else 'FAIL'}")
        return code

    return 0 if all_ran else 1


if __name__ == "__main__":
    raise SystemExit(main())
