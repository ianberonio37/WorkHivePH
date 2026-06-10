"""
Companion Domain Eval Harness — Probe Taxonomy family G (Domain correctness).
============================================================================
Drives the domain-correctness grader (companion_rigorous_grader.grade_domain_*) over the Domain
golden set (companion_domain_golden.json). The domain dimension = is the companion's maintenance
advice actually RIGHT? Graded deterministically: required domain-marker GROUPS all present
(MTBF/MTTR per ISO 14224, OEE/availability per ISO 22400/Nakajima, PM per SMRP/RCM, failure-mode
reasoning, PEC standards) + wrong-domain anti-markers absent (wrong standard / absurd number /
wrong definition). The grader is independent (no companion imports, no LLM).

Mirrors companion_persona_eval.py (same template, family G).

Modes:
  --self-test   (default) prove the grader is correct + discriminating with NO live model: an ORACLE
                observation (echoes the right domain facts) passes every unit; a BLIND (content-free)
                observation fails every unit.
  --observed F  grade a real observation map F = { unit_id: {answer} } and emit an ai_eval_results-
                shaped file (dimension=domain) so the gate can baseline + gate Domain on the
                locked-test split once captured live.

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
GOLDEN_PATH = ROOT / "companion_domain_golden.json"

sys.path.insert(0, str(TOOLS_DIR))
from companion_rigorous_grader import (domain_grader_self_test, grade_domain_or_judgment,
                                       judgment_grader_self_test, is_judgment_unit)

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_units(golden: dict) -> list[dict]:
    return list(golden.get("probes") or golden.get("units") or [])


def self_test() -> int:
    golden = _load_json(GOLDEN_PATH)
    if not golden:
        print(f"{YEL}No companion_domain_golden.json — Domain golden set not built here.{RESET}")
        return 0
    r = domain_grader_self_test(golden)      # substring (CLINICAL-FACT) units — judge units skipped
    j = judgment_grader_self_test(golden)    # JUDGMENT units — offline MOCK judge (no LLM)
    ok = r["ok"] and j["ok"]
    print(f"\n{BOLD}Domain grader self-test{RESET}  ·  {r['total']} substring + {j['total']} judgment units")
    print("=" * 64)
    print(f"  substring  oracle {r['oracle_pass']}/{r['total']} PASS · blind {r['blind_pass']}/{r['total']} PASS (must be 0)")
    print(f"  judgment   oracle {j['oracle_pass']}/{j['total']} PASS · blind {j['blind_pass']}/{j['total']} (must be 0) · "
          f"anti-backstop {j['backstop_ok']}/{j['backstop_n']}")
    if ok:
        print(f"\n{GREEN}OK{RESET}  substring + judgment graders correct AND discriminating "
              f"(judgment via MOCK; live judge calibrated by companion_judge.py --self-test).")
        print("=" * 64)
        return 0
    print(f"\n{RED}FAIL{RESET}  grader self-test problems:")
    for p in (r["problems"] + j["problems"]):
        print(f"  - {p}")
    print("=" * 64)
    return 1


def grade_observed(observed_path: Path, out_path: Path) -> int:
    golden = _load_json(GOLDEN_PATH)
    if not golden:
        print(f"{YEL}No companion_domain_golden.json.{RESET}")
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
        g = grade_domain_or_judgment(unit, observed_map[uid])   # judge units -> live cross-model judge
        graded += 1
        is_pass = g["verdict"] == "PASS"
        passed += 1 if is_pass else 0
        jr = (g.get("judge") or {}).get("reason") if isinstance(g.get("judge"), dict) else None
        results.append({"id": uid, "passed": is_pass, "score": 100 if is_pass else 0,
                        "type": g.get("type"), "probe_type": unit.get("probe_type"),
                        "ability": unit.get("ability"), "verdict": g["verdict"],
                        "anti_markers_hit": g.get("anti_markers_hit"), "judge_reason": jr})

    out = {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "companion_domain_eval", "dimension": "domain", "results": results}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    rate = round(100 * passed / graded, 1) if graded else None
    print(f"\n{BOLD}Domain eval (observed){RESET}  ·  {graded} graded ({missing} had no observation)")
    print(f"  pass {passed}/{graded}" + (f"  ({rate}%)" if rate is not None else ""))
    print(f"  -> {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path}")
    print(f"  (feed to ai_eval_gate.py once the Domain baseline is frozen)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Domain dimension eval harness (Probe Taxonomy family G)")
    ap.add_argument("--self-test", action="store_true", help="prove the grader is discriminating (default)")
    ap.add_argument("--observed", default=None, help="path to a {unit_id: observed} JSON map to grade")
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "domain_eval_results.json"))
    args = ap.parse_args()
    if args.observed:
        return grade_observed(Path(args.observed), Path(args.out))
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
