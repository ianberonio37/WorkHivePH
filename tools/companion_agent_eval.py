"""
Companion Agent Eval Harness — Phase 8 §8.2 (Agent dimension).
=============================================================
Drives the DETERMINISTIC Agent Tool-Correctness grader (companion_rigorous_grader.grade_agent_*)
over the Agent golden set (companion_agent_golden.json). The grader is independent (no companion
imports, no LLM); this harness just feeds it golden units + observations and normalizes the output
into the eval-results shape the regression gate (ai_eval_gate.py, 8.3) consumes.

Two modes:
  --self-test   (default) prove the grader is correct + negative-controlled with NO live companion:
                an ORACLE observation passes every unit; a BLIND observation (always a confident
                logbook.create) fails every negative control and scores strictly lower. Exit 1 if
                the grader fails to discriminate. This is the $0 build-time guarantee.
  --observed F  grade a real observation map F = { unit_id: observed }, where observed is the
                NORMALIZED route decision the runner extracts from the gateway route_result:
                  single/negative : {"route": str|None, "params": {}, "confidence": float|None, "answer": str}
                  multi-step      : [ <one observed per step> ]
                Emits an ai_eval_results-shaped file (id, passed, score, ...) keyed by the SAME ids
                the splits carry (kind=agent_golden, eval_dimension=agent), so 8.3 can baseline +
                gate the Agent dimension on the locked-test split.

Producing the real observation map (the paid step) is the companion flywheel's job — run the Agent
golden transcripts through the live gateway, capture route_result.intents[0] -> {route:kind, params,
confidence} + the answer text. This harness never calls a model, so it stays free + offline.

Exit: 0 normally (eval, not a gate). --self-test exits 1 if the grader does not discriminate.
"""
from __future__ import annotations
import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT      = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = ROOT / "companion_agent_golden.json"

sys.path.insert(0, str(TOOLS_DIR))
from companion_rigorous_grader import (grade_agent_unit, agent_grader_self_test,
                                       DEFAULT_WRITE_INTENTS, DEFAULT_CONFIDENCE_FLOOR)

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_units(golden: dict) -> list[dict]:
    return (list(golden.get("single_turn") or [])
            + list(golden.get("multi_step") or [])
            + list(golden.get("negative_controls") or []))


def self_test() -> int:
    golden = _load_json(GOLDEN_PATH)
    if not golden:
        print(f"{YEL}No companion_agent_golden.json — Phase 8 §8.1 not built here.{RESET}")
        return 0
    r = agent_grader_self_test(golden)
    print(f"\n{BOLD}Agent grader self-test{RESET}  ·  {r['total']} golden units "
          f"({r['negatives']} negative controls)")
    print("=" * 64)
    print(f"  oracle observation : {r['oracle_pass']}/{r['total']} PASS  (must be all)")
    print(f"  blind  observation : {r['blind_pass']}/{r['total']} PASS  "
          f"(must be < oracle; negatives must all FAIL)")
    print(f"  blind fails negatives: {r['blind_negatives_failed']}/{r['negatives']}")
    if r["ok"]:
        print(f"\n{GREEN}OK{RESET}  grader is correct AND negative-controlled "
              f"(a rubber-stamp grader would have passed the negatives).")
        print("=" * 64)
        return 0
    print(f"\n{RED}FAIL{RESET}  grader self-test problems:")
    for p in r["problems"]:
        print(f"  - {p}")
    print("=" * 64)
    return 1


def grade_observed(observed_path: Path, out_path: Path) -> int:
    golden = _load_json(GOLDEN_PATH)
    if not golden:
        print(f"{YEL}No companion_agent_golden.json.{RESET}")
        return 0
    observed_map = _load_json(observed_path)
    if not isinstance(observed_map, dict):
        print(f"{RED}Observed file {observed_path} not found or not a {{unit_id: observed}} map.{RESET}")
        return 0
    write_intents = golden.get("write_intents", list(DEFAULT_WRITE_INTENTS))
    floor = golden.get("confidence_floor", DEFAULT_CONFIDENCE_FLOOR)

    results, graded, passed, missing = [], 0, 0, 0
    for unit in _all_units(golden):
        uid = unit.get("id")
        if uid not in observed_map:
            missing += 1
            continue
        g = grade_agent_unit(unit, observed_map[uid], write_intents, floor)
        graded += 1
        is_pass = g["verdict"] == "PASS"
        passed += 1 if is_pass else 0
        results.append({"id": uid, "passed": is_pass, "score": 100 if is_pass else 0,
                        "category": unit.get("category", ""), "type": g.get("type"),
                        "verdict": g["verdict"]})

    out = {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "companion_agent_eval", "dimension": "agent",
           "results": results}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    rate = round(100 * passed / graded, 1) if graded else None
    print(f"\n{BOLD}Agent eval (observed){RESET}  ·  {graded} graded "
          f"({missing} golden units had no observation)")
    print(f"  pass {passed}/{graded}" + (f"  ({rate}%)" if rate is not None else ""))
    print(f"  -> {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path}")
    print(f"  (feed this to ai_eval_gate.py once the Agent baseline is frozen in 8.3)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Agent dimension eval harness (Phase 8 §8.2)")
    ap.add_argument("--self-test", action="store_true", help="prove the grader is negative-controlled (default)")
    ap.add_argument("--observed", default=None, help="path to a {unit_id: observed} JSON map to grade")
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "agent_eval_results.json"),
                    help="output results path (with --observed)")
    args = ap.parse_args()
    if args.observed:
        return grade_observed(Path(args.observed), Path(args.out))
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
