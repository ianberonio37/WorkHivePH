#!/usr/bin/env python3
"""validate_analytics_synthesis_grounding.py — Analytics Engine arc (AI2/F5) gate: the AI action-plan
synthesis must read REAL phase-output keys.

THE RISK: `analytics-orchestrator` builds the prompt for the AI "action plan" (the one user-facing AI
narrative on analytics-report + the Prescriptive phase) by reading fields off each 4-phase payload —
`pred.<key>`, `diag.<key>`, `desc.<key>`, `pres.<key>`. If any of those keys DRIFT from what the Python
phase actually emits (e.g. `pred.next_failure_forecast` when predictive.py emits `next_failure_dates`),
that signal silently becomes `undefined` — the AI is then ORDERED by the system prompt to reason about
"forecasted next failure dates / anomalies / stockout risk" with NOTHING fed → omission or fabrication.
This is exactly the drift found 2026-07-10 (next_failure_forecast / anomaly_detection / stockout_forecast
/ repeat_failures / average_oee_pct all stale → zero predictive grounding).

THE CONTROL: every `(<phase>.<key> as ...)` the synthesis reads must exist in that phase's real
top-level assembly-return keys (parsed from python-api/analytics/<phase>.py).

Static (no deno/DB) → runs in --fast. Self-test: --self-test injects a bogus read → must FAIL (teeth).
Skills: ai-engineer (grounding/no-fabrication), analytics-engineer (4-phase contract), data-engineer.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ORCH = ROOT / "supabase" / "functions" / "analytics-orchestrator" / "index.ts"
PHASE_FILE = {
    "desc": ROOT / "python-api" / "analytics" / "descriptive.py",
    "diag": ROOT / "python-api" / "analytics" / "diagnostic.py",
    "pred": ROOT / "python-api" / "analytics" / "predictive.py",
    "pres": ROOT / "python-api" / "analytics" / "prescriptive.py",
}
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]


def phase_keys(py_src: str) -> set[str]:
    """Top-level keys of a phase's MAIN assembly return = the `return {...}` block with the most
    string keys (the dispatch return has far more keys than any single sub-calc's early return)."""
    best: set[str] = set()
    for m in re.finditer(r"return\s*\{", py_src):
        i = m.end() - 1; depth = 0
        for j in range(i, len(py_src)):
            if py_src[j] == "{": depth += 1
            elif py_src[j] == "}":
                depth -= 1
                if depth == 0:
                    block = py_src[i:j + 1]
                    break
        else:
            continue
        # only TOP-LEVEL keys: `"key":` at brace-depth 1 within this block
        keys, d = set(), 0
        for k, ch in enumerate(block):
            if ch == "{": d += 1
            elif ch == "}": d -= 1
            elif ch == '"' and d == 1:
                km = re.match(r'"([a-z_][a-z0-9_]*)"\s*:', block[k:])
                if km:
                    keys.add(km.group(1))
        if len(keys) > len(best):
            best = keys
    return best


def synthesis_reads(ts_src: str, extra: tuple[str, str] | None = None) -> list[tuple[str, str]]:
    """Every `(<phase>.<key> as ...)` read in the orchestrator synthesis payload."""
    reads = [(p, k) for p, k in re.findall(r"\((desc|diag|pred|pres)\.([a-z_]+)\s+as", ts_src)]
    if extra:
        reads.append(extra)
    return reads


def main() -> int:
    print(f"\n{'='*64}\n  Analytics arc AI2/F5 — AI action-plan synthesis grounding\n{'='*64}")
    if not ORCH.exists():
        print(f"{RED}  FAIL  analytics-orchestrator/index.ts not found{RST}"); return 1
    ts = ORCH.read_text(encoding="utf-8", errors="replace")
    keys = {ph: phase_keys(f.read_text(encoding="utf-8", errors="replace")) for ph, f in PHASE_FILE.items()}
    for ph, ks in keys.items():
        print(f"  {ph}: {len(ks)} phase-output keys parsed")

    # ── intelligence-report narrative grounding (AI2b): if `seasonal_insight` is a REQUIRED
    # output field, the seasonal DATA must be in the prompt — else the AI invents it. ────────
    INTEL = ROOT / "supabase" / "functions" / "intelligence-report" / "index.ts"
    intel_ok, intel_detail = True, "intelligence-report not present (skipped)"
    if INTEL.exists():
        it = INTEL.read_text(encoding="utf-8", errors="replace")
        requires_seasonal = "seasonal_insight" in it
        # the generateNarrative prompt must reference data.seasonal when seasonal_insight is required
        prompt_has_seasonal = bool(re.search(r"data\.seasonal", it))
        intel_ok = (not requires_seasonal) or prompt_has_seasonal
        if SELF_TEST:  # prove teeth: pretend the prompt lost its seasonal grounding
            intel_ok = (not requires_seasonal) or False
        intel_detail = ("seasonal_insight required + data.seasonal grounds the prompt"
                        if intel_ok else "seasonal_insight is a required output but data.seasonal is NOT in the narrative prompt → AI invents it")

    extra = ("pred", "__bogus_stale_key__") if SELF_TEST else None
    reads = synthesis_reads(ts, extra)
    drift = [(p, k) for p, k in reads if k not in keys[p]]

    if SELF_TEST:
        caught = (("pred", "__bogus_stale_key__") in drift) and (not intel_ok)
        print(f"  self-test: bogus synthesis read + dropped seasonal grounding both caught = {caught} "
              f"({GREEN+'teeth OK'+RST if caught else RED+'NO TEETH'+RST})")
        drift = [d for d in drift if d != ("pred", "__bogus_stale_key__")]
        intel_ok = True  # consumed the self-test perturbation

    ok = (not drift) and intel_ok
    print(f"  {GREEN+'PASS'+RST if not drift else RED+'FAIL'+RST}  {len(reads) - (1 if SELF_TEST else 0)} synthesis reads all resolve to a real phase-output key")
    print(f"  {GREEN+'PASS'+RST if intel_ok else RED+'FAIL'+RST}  intelligence-report: {intel_detail}")
    if drift:
        for p, k in drift:
            print(f"  {RED}DRIFT: synthesis reads {p}.{k} — not in {PHASE_FILE[p].name} output {sorted(keys[p])}{RST}")
    print("-" * 64)
    print(f"{(GREEN if ok else RED)}  RESULT: {'GREEN — both AI narratives (action plan + intelligence report) are fed real signals.' if ok else 'RED — an AI narrative is asked to reason about a signal it never receives.'}{RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
