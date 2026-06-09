"""
Companion Safety-Gaps Eval Harness — Probe Taxonomy family E (E2/E5/E7; dim safety).
===================================================================================
Drives the generic marker grader over companion_safety_gaps_golden.json — the safety probe TYPES the
25-probe adversarial bank misses: E2 indirect injection, E5 excessive agency, E7 harmful maintenance
advice. markers_all = the SAFE behaviour (refuse / flag / safety-first); anti_markers = unsafe
compliance that must be ABSENT. Deterministic, independent. Same template as companion_robustness_eval.py.

  --self-test   (default) ORACLE passes every unit; BLIND (content-free) fails.
  --observed F  grade a {unit_id: {answer}} map.
"""
from __future__ import annotations
import argparse, io, json, sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = ROOT / "companion_safety_gaps_golden.json"
DIMENSION = "safety"

sys.path.insert(0, str(TOOLS_DIR))
from companion_rigorous_grader import grade_markers_unit, markers_grader_self_test

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def self_test() -> int:
    golden = _load_json(GOLDEN_PATH)
    if not golden:
        print(f"{YEL}No {GOLDEN_PATH.name} — safety-gaps golden set not built here.{RESET}")
        return 0
    r = markers_grader_self_test(golden)
    print(f"\n{BOLD}Safety-gaps grader self-test{RESET}  ·  {r['total']} golden units")
    print("=" * 64)
    print(f"  oracle observation : {r['oracle_pass']}/{r['total']} PASS  (must be all)")
    print(f"  blind  observation : {r['blind_pass']}/{r['total']} PASS  (must be 0 — content-free)")
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
        print(f"{YEL}No {GOLDEN_PATH.name}.{RESET}")
        return 0
    observed_map = _load_json(observed_path)
    if not isinstance(observed_map, dict):
        print(f"{RED}Observed file {observed_path} not found or not a {{unit_id: observed}} map.{RESET}")
        return 0
    results, graded, passed, missing = [], 0, 0, 0
    for unit in (golden.get("probes") or golden.get("units") or []):
        uid = unit.get("id")
        if uid not in observed_map:
            missing += 1
            continue
        g = grade_markers_unit(unit, observed_map[uid])
        graded += 1
        is_pass = g["verdict"] == "PASS"
        passed += 1 if is_pass else 0
        results.append({"id": uid, "passed": is_pass, "score": 100 if is_pass else 0,
                        "probe_type": unit.get("probe_type"), "ability": unit.get("ability"),
                        "verdict": g["verdict"], "anti_markers_hit": g.get("anti_markers_hit")})
    out = {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "companion_safety_gaps_eval", "dimension": DIMENSION, "results": results}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    rate = round(100 * passed / graded, 1) if graded else None
    print(f"\n{BOLD}Safety-gaps eval (observed){RESET}  ·  {graded} graded ({missing} no obs)")
    print(f"  pass {passed}/{graded}" + (f"  ({rate}%)" if rate is not None else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Safety-gaps eval harness (Probe Taxonomy E2/E5/E7)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--observed", default=None)
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "safety_gaps_eval_results.json"))
    args = ap.parse_args()
    if args.observed:
        return grade_observed(Path(args.observed), Path(args.out))
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
