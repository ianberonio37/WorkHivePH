"""
Companion Persona Eval Harness — Phase 8 §8.2 (Persona dimension).
=================================================================
Drives the voice-marker grader (companion_rigorous_grader.grade_persona_*) over the Persona golden
set (companion_persona_golden.json). The companion's persona dimension = does the reply wear the
SELECTED persona's voice (Hezekiah=technical / Zaniah=strategist) and not the other's? Graded
deterministically: presence of the persona's signature markers (name + lane vocab + bridges) +
absence of the wrong-persona self-identification. The grader is independent (no companion imports,
no LLM). Persona is per-call toggleable (ai-gateway honours a supplied context.persona), so the
capture sets context.persona per probe.

Modes:
  --self-test   (default) prove the grader is correct + discriminating with NO live model: an ORACLE
                observation passes every unit; a BLIND (voice-less) observation fails every unit.
  --observed F  grade a real observation map F = { unit_id: {answer} } and emit an ai_eval_results-
                shaped file keyed by the same ids the splits carry (kind=persona_golden,
                eval_dimension=persona) so 8.3 can baseline + gate Persona on the locked-test split.

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
GOLDEN_PATH = ROOT / "companion_persona_golden.json"

sys.path.insert(0, str(TOOLS_DIR))
from companion_rigorous_grader import grade_persona_unit, persona_grader_self_test

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_units(golden: dict) -> list[dict]:
    return list(golden.get("probes") or [])


def self_test() -> int:
    golden = _load_json(GOLDEN_PATH)
    if not golden:
        print(f"{YEL}No companion_persona_golden.json — Phase 8 §8.1 (Persona) not built here.{RESET}")
        return 0
    r = persona_grader_self_test(golden)
    print(f"\n{BOLD}Persona grader self-test{RESET}  ·  {r['total']} golden units")
    print("=" * 64)
    print(f"  oracle observation : {r['oracle_pass']}/{r['total']} PASS  (must be all)")
    print(f"  blind  observation : {r['blind_pass']}/{r['total']} PASS  (must be 0 — voice-less)")
    if r["ok"]:
        print(f"\n{GREEN}OK{RESET}  grader is correct AND discriminating.")
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
        print(f"{YEL}No companion_persona_golden.json.{RESET}")
        return 0
    observed_map = _load_json(observed_path)
    if not isinstance(observed_map, dict):
        print(f"{RED}Observed file {observed_path} not found or not a {{unit_id: observed}} map.{RESET}")
        return 0

    results, graded, passed, missing = [], 0, 0, 0
    for unit in _all_units(golden):
        uid = unit.get("id")
        if uid not in observed_map:
            missing += 1
            continue
        g = grade_persona_unit(unit, observed_map[uid])
        graded += 1
        is_pass = g["verdict"] == "PASS"
        passed += 1 if is_pass else 0
        results.append({"id": uid, "passed": is_pass, "score": 100 if is_pass else 0,
                        "category": unit.get("category", ""), "type": g.get("type"),
                        "persona": unit.get("persona"), "ability": unit.get("ability"),
                        "verdict": g["verdict"], "anti_markers_hit": g.get("anti_markers_hit")})

    out = {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "companion_persona_eval", "dimension": "persona", "results": results}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    rate = round(100 * passed / graded, 1) if graded else None
    print(f"\n{BOLD}Persona eval (observed){RESET}  ·  {graded} graded ({missing} had no observation)")
    print(f"  pass {passed}/{graded}" + (f"  ({rate}%)" if rate is not None else ""))
    print(f"  -> {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path}")
    print(f"  (feed to ai_eval_gate.py once the Persona baseline is frozen in 8.3)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Persona dimension eval harness (Phase 8 §8.2)")
    ap.add_argument("--self-test", action="store_true", help="prove the grader is discriminating (default)")
    ap.add_argument("--observed", default=None, help="path to a {unit_id: observed} JSON map to grade")
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "persona_eval_results.json"))
    args = ap.parse_args()
    if args.observed:
        return grade_observed(Path(args.observed), Path(args.out))
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
