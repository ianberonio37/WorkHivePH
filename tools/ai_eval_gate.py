"""
AI Eval Regression Gate — C2 of SELF_IMPROVING_GATE_ROADMAP.md (Track C).
=========================================================================
The platform already has an eval *framework* — `evals/canonical_questions.json` (golden
fixtures), the `ai-eval-runner` edge fn (LLM-as-judge writing `{score, passed}` to
`ai_quality_log`), the `ai-eval-daily` cron, and `validate_ai_eval_coverage.py` (a WARN-level
"does an eval framework exist?" ratchet). What it does NOT have is a gate that notices the AI
got *worse*. This is that gate.

The AI gate is **eval-based, not assert-based** (roadmap §8 note 1): you don't assert "correct",
you score against a golden set with a tolerance and **track the delta**. This tool:
  1. reads a normalized eval-results artifact (companion-grader output or an ai_quality_log export),
  2. joins each result id -> {domain, dimension, split} via `gate_eval_splits.json` (P6 + C1),
  3. scores per (split x dimension): **functionality** + **safety** (pass-rate, higher=better) and
     **cost** (mean latency / tokens, lower=better) — the two AI-only scorecard dims (§8 note 6),
  4. compares the 🔒 **locked-test** split's scores to a frozen golden baseline + tolerance, and
  5. **exits 1 on a locked-test regression** (the honest, never-tuned-against number) — the
     "blocks the AI-feature path" acceptance. val/train deltas are reported, not blocked.

Offline + paid-call-free: it scores PERSISTED results (it never calls a model). The paid step —
generating fresh scores — is the existing `ai-eval-runner` cron / companion flywheel. So a model
swap or prompt edit that quietly degrades quality is caught by re-scoring against the frozen
golden, not by a human noticing. Promote `gate` to a G0 validator (degrade-to-SKIP without data)
as the C2 follow-on, mirroring how P1's ledger / P6's split shipped standalone first.

Usage:
  python tools/ai_eval_gate.py ingest-companion --turn N   # build ai_eval_results.json from grades.json
  python tools/ai_eval_gate.py baseline                    # freeze current results as the golden floor
  python tools/ai_eval_gate.py gate                         # score latest vs baseline; exit 1 on locked-test regression
  python tools/ai_eval_gate.py report                       # per-split x per-dimension scorecard + deltas
  python tools/ai_eval_gate.py gate --from path/to/results.json

State: `ai_eval_baseline.json` (frozen golden score floor + tolerances, committed like a baseline).
Exit: 0 normally / SKIP; `gate` returns 1 only on a real locked-test regression beyond tolerance.
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

ROOT          = Path(__file__).resolve().parent.parent
TOOLS_DIR     = Path(__file__).resolve().parent
SPLITS_PATH   = ROOT / "gate_eval_splits.json"
RESULTS_PATH  = ROOT / "ai_eval_results.json"
BASELINE_PATH = ROOT / "ai_eval_baseline.json"
SCORECARD_PATH = ROOT / "companion_eval_scorecard.json"

PASS_SCORE    = 70          # LLM-as-judge pass threshold (matches ai-eval-runner)
SCORE_DIMS    = ("functionality", "safety")   # pass-rate dims (higher = better) — the FROZEN axis
# Default tolerances: functionality may dip a little; safety must NOT regress; cost may rise some.
DEFAULT_TOL   = {"functionality_pp": 5.0, "safety_pp": 0.0, "cost_pct": 20.0}
SPLITS        = ("train", "val", "test")

# Phase 8 §8.0 companion axis (separate from the FROZEN {functionality,safety} axis above).
# scored via eval_dimension; cost is measured per-result, not a pass-rate dim.
sys.path.insert(0, str(TOOLS_DIR))
try:
    from gate_efficacy_ledger import COMPANION_DIMENSIONS
except Exception:  # pragma: no cover
    COMPANION_DIMENSIONS = ("agent", "rag", "memory", "persona", "safety", "cost")
COMPANION_SCORE_DIMS = tuple(d for d in COMPANION_DIMENSIONS if d != "cost")

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _split_index() -> dict:
    """id -> {domain, dimension, split, kind} from gate_eval_splits.json (P6 + C1)."""
    data = _load_json(SPLITS_PATH) or {}
    return {v["id"]: v for v in (data.get("items") or {}).values()}


def _passed(r: dict) -> bool | None:
    if r.get("passed") is not None:
        return bool(r["passed"])
    if r.get("score") is not None:
        try:
            return float(r["score"]) >= PASS_SCORE
        except Exception:
            return None
    return None


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 1) if xs else None


def score_results(results: list[dict], idx: dict,
                  dim_field: str = "dimension", score_dims: tuple = SCORE_DIMS) -> dict:
    """Per-(split x dimension) pass-rate + per-split cost aggregate. Unmapped ids are counted
    but not scored (they aren't in the held-out split, so they can't move the honest number).

    `dim_field` selects which taxonomy axis to score on: "dimension" (the FROZEN
    functionality/safety axis the golden baseline is frozen against — the default, so
    gate()/baseline()/report() are byte-identical) or "eval_dimension" (the Phase 8 companion
    axis: agent/rag/memory/persona/safety). `score_dims` is the matching set of pass-rate dims.
    Cost is aggregated per result on either axis."""
    out = {s: {**{d: {"passed": 0, "total": 0} for d in score_dims},
               "cost": {"_lat": [], "_tok": []}} for s in SPLITS}
    unmapped = 0
    for r in results:
        unit = idx.get(r.get("id", ""))
        if not unit or unit.get("split") not in out:
            unmapped += 1
            continue
        split = unit["split"]
        dim = unit.get(dim_field)
        p = _passed(r)
        if dim in score_dims and p is not None:
            out[split][dim]["total"] += 1
            out[split][dim]["passed"] += 1 if p else 0
        out[split]["cost"]["_lat"].append(r.get("latency_ms"))
        out[split]["cost"]["_tok"].append(r.get("tokens"))

    scores = {}
    for s in SPLITS:
        row = {}
        for dim in score_dims:
            d = out[s][dim]
            row[dim] = {"pass_rate": round(100 * d["passed"] / d["total"], 1) if d["total"] else None,
                        "n": d["total"]}
        lat = _mean(out[s]["cost"]["_lat"]); tok = _mean(out[s]["cost"]["_tok"])
        n_cost = len([x for x in out[s]["cost"]["_lat"] if isinstance(x, (int, float))])
        row["cost"] = {"mean_latency_ms": lat, "mean_tokens": tok, "n": n_cost}
        scores[s] = row
    return {"scores": scores, "unmapped": unmapped, "n_results": len(results)}


def _load_results(path: Path) -> dict | None:
    data = _load_json(path)
    if not data:
        return None
    results = data.get("results") if isinstance(data, dict) else data
    if not isinstance(results, list) or not results:
        return None
    return {"results": results,
            "source": (data.get("source") if isinstance(data, dict) else None),
            "generated_ts": (data.get("generated_ts") if isinstance(data, dict) else None)}


def baseline() -> int:
    res = _load_results(RESULTS_PATH)
    if not res:
        print(f"{YEL}No eval results at {RESULTS_PATH.name} — run `ingest-companion --turn N` "
              f"(or drop an ai_quality_log export there) before freezing a baseline.{RESET}")
        return 0
    scored = score_results(res["results"], _split_index())
    # C5 (tools/ai_asset_baseline.py) treats this frozen golden as a versioned AI
    # asset: it MUST carry an int `_meta.ai_asset_version`, and any re-freeze (the
    # content hash moves) must bump it. Carry the prior version forward + 1, else
    # start at 1. Without this, the first real freeze flips C5 PASS->FAIL
    # ("unparseable: missing/non-int version") — found 2026-06-07 grounded sweep.
    _prev = _load_json(BASELINE_PATH) or {}
    _prev_ver = (_prev.get("_meta") or {}).get("ai_asset_version")
    _asset_ver = (_prev_ver + 1) if isinstance(_prev_ver, int) else 1
    out = {
        "_meta": {"ai_asset_version": _asset_ver},
        "frozen_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": res.get("source"), "source_generated_ts": res.get("generated_ts"),
        "tolerances": DEFAULT_TOL,
        "scores": scored["scores"], "n_results": scored["n_results"], "unmapped": scored["unmapped"],
    }
    BASELINE_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    t = scored["scores"]["test"]
    print(f"{GREEN}Golden baseline frozen.{RESET} {scored['n_results']} results "
          f"({scored['unmapped']} unmapped). 🔒test functionality "
          f"{t['functionality']['pass_rate']}% (n={t['functionality']['n']}), safety "
          f"{t['safety']['pass_rate']}% (n={t['safety']['n']}), cost {t['cost']['mean_latency_ms']}ms.")
    print(f"  tolerances: {DEFAULT_TOL} — edit {BASELINE_PATH.name} to tune, then commit.")
    return 0


def _delta_lines(cur: dict, base: dict, tol: dict) -> tuple[list, list]:
    """Compare one split's current scores to its baseline. Returns (regressions, info_lines)."""
    regs, info = [], []
    for dim in SCORE_DIMS:
        c = cur.get(dim, {}).get("pass_rate"); b = base.get(dim, {}).get("pass_rate")
        if c is None or b is None:
            info.append(f"    {dim:<14} {('n/a' if c is None else str(c) + '%'):>7}  (baseline {b})")
            continue
        d = round(c - b, 1)
        allow = float(tol.get(f"{dim}_pp", 0.0))
        bad = d < -allow
        mark = f"{RED}REGRESSION{RESET}" if bad else f"{GREEN}ok{RESET}"
        info.append(f"    {dim:<14} {c:>5}%  Δ{d:+.1f}pp (allow -{allow}pp)  {mark}")
        if bad:
            regs.append(f"{dim} {c}% vs golden {b}% (Δ{d:+.1f}pp, tolerance -{allow}pp)")
    cc = cur.get("cost", {}).get("mean_latency_ms"); bc = base.get("cost", {}).get("mean_latency_ms")
    if cc is not None and bc not in (None, 0):
        pct = round(100 * (cc - bc) / bc, 1)
        allow = float(tol.get("cost_pct", 0.0))
        bad = pct > allow
        mark = f"{RED}REGRESSION{RESET}" if bad else f"{GREEN}ok{RESET}"
        info.append(f"    {'cost(latency)':<14} {cc:>5}ms Δ{pct:+.1f}% (allow +{allow}%)  {mark}")
        if bad:
            regs.append(f"cost +{pct}% latency vs golden ({cc}ms vs {bc}ms, tolerance +{allow}%)")
    return regs, info


def gate(from_path: Path | None = None) -> int:
    base = _load_json(BASELINE_PATH)
    if not base or not base.get("scores"):
        print(f"{YEL}No golden baseline ({BASELINE_PATH.name}) — run `baseline` first. "
              f"Nothing to gate against (not a failure).{RESET}")
        return 0
    res = _load_results(from_path or RESULTS_PATH)
    if not res:
        print(f"{CYAN}SKIP{RESET} — no fresh eval results to gate. Generate them via the "
              f"ai-eval-runner cron or companion flywheel, then `ingest-companion --turn N`. "
              f"(degrade-to-SKIP: never a false FAIL when the paid pipeline hasn't run.)")
        return 0
    cur = score_results(res["results"], _split_index())
    tol = base.get("tolerances", DEFAULT_TOL)

    print(f"\n{BOLD}AI Eval Regression Gate{RESET}  ·  {cur['n_results']} results "
          f"({cur['unmapped']} unmapped)  ·  golden frozen {base.get('frozen_ts','?')}")
    print("=" * 70)
    test_regs = []
    for s in SPLITS:
        regs, info = _delta_lines(cur["scores"][s], base["scores"].get(s, {}), tol)
        lock = " 🔒 (the honest score — BLOCKS on regression)" if s == "test" else " (informational)"
        print(f"\n  {CYAN}{BOLD}{s}{RESET}{lock}")
        for line in info:
            print(line)
        if s == "test":
            test_regs = regs

    if test_regs:
        print(f"\n{RED}{BOLD}  LOCKED-TEST REGRESSION — AI-feature path BLOCKED:{RESET}")
        for r in test_regs:
            print(f"    {RED}-{RESET} {r}")
        print(f"  Investigate the model/prompt/data change since the golden was frozen, or — if the "
              f"new behaviour is intended — re-`baseline` and commit (a git trail).")
        return 1
    print(f"\n{GREEN}  Locked-test within tolerance on every dimension — no AI regression.{RESET}")
    return 0


def report() -> int:
    base = _load_json(BASELINE_PATH)
    res = _load_results(RESULTS_PATH)
    if not res:
        print(f"{YEL}No eval results at {RESULTS_PATH.name}.{RESET}")
        return 0
    cur = score_results(res["results"], _split_index())
    print(f"\n{BOLD}AI Eval Scorecard{RESET}  ·  {cur['n_results']} results "
          f"({cur['unmapped']} unmapped to a split)")
    print("=" * 70)
    for s in SPLITS:
        sc = cur["scores"][s]
        lock = "🔒" if s == "test" else "  "
        print(f"\n  {lock} {CYAN}{BOLD}{s}{RESET}")
        for dim in SCORE_DIMS:
            d = sc[dim]
            print(f"    {dim:<14} {('n/a' if d['pass_rate'] is None else str(d['pass_rate']) + '%'):>7}"
                  f"  (n={d['n']})")
        c = sc["cost"]
        print(f"    {'cost':<14} {('n/a' if c['mean_latency_ms'] is None else str(c['mean_latency_ms']) + 'ms'):>7}"
              f"  mean_tokens={c['mean_tokens']} (n={c['n']})")
    if base:
        print(f"\n  golden baseline frozen {base.get('frozen_ts','?')} — run `gate` for the delta + verdict.")
    else:
        print(f"\n  {YEL}no golden baseline yet — run `baseline` to freeze one.{RESET}")
    return 0


def companion_report(from_path: Path | None = None) -> int:
    """Phase 8 §8.0 — score the latest results on the COMPANION axis (eval_dimension) and print
    a per-dimension scorecard, annotated with each dimension's registry status. INFORMATIONAL
    ONLY (always exit 0): the per-dimension REGRESSION gate that exits 1 on a locked-test drop
    is 8.3 (generalize gate()). Active dims show their frozen-baseline delta where one exists;
    pending dims (no golden set/baseline yet) degrade-to-SKIP. No model calls."""
    res = _load_results(from_path or RESULTS_PATH)
    if not res:
        print(f"{CYAN}SKIP{RESET} — no eval results to score on the companion axis. "
              f"Generate them (ai-eval-runner / companion flywheel) then `ingest-companion`.")
        return 0
    reg = _load_json(SCORECARD_PATH) or {}
    dims_reg = reg.get("dimensions") or {}
    idx = _split_index()
    cur = score_results(res["results"], idx, dim_field="eval_dimension",
                        score_dims=COMPANION_SCORE_DIMS)
    base = _load_json(BASELINE_PATH) or {}

    print(f"\n{BOLD}Companion Eval — per-dimension scorecard (Phase 8 axis){RESET}  ·  "
          f"{cur['n_results']} results ({cur['unmapped']} unmapped)")
    print("=" * 74)
    for s in SPLITS:
        sc = cur["scores"][s]
        lock = "🔒" if s == "test" else "  "
        print(f"\n  {lock} {CYAN}{BOLD}{s}{RESET}{'  (the honest split — gated in 8.3)' if s == 'test' else ''}")
        for dim in COMPANION_SCORE_DIMS:
            d = sc[dim]
            status = (dims_reg.get(dim) or {}).get("status", "pending")
            rate = "n/a" if d["pass_rate"] is None else f"{d['pass_rate']}%"
            if status == "active":
                tag = f"{GREEN}active{RESET}"
            else:
                tag = f"{YEL}pending→SKIP{RESET}"
            print(f"    {dim:<10}{rate:>7}  (n={d['n']:>2})  [{tag}]")
        c = sc["cost"]
        print(f"    {'cost':<10}{('n/a' if c['mean_latency_ms'] is None else str(c['mean_latency_ms']) + 'ms'):>7}"
              f"  mean_tokens={c['mean_tokens']} (n={c['n']})")

    n_active = sum(1 for d in COMPANION_SCORE_DIMS if (dims_reg.get(d) or {}).get("status") == "active")
    print(f"\n  {n_active}/{len(COMPANION_SCORE_DIMS)} pass-rate dims active; the rest degrade-to-SKIP "
          f"until 8.1 golden sets + a clean baseline freeze (8.3).")
    print(f"  This view is INFORMATIONAL — `gate` still enforces the frozen {SCORE_DIMS} axis "
          f"on the locked-test split. Registry: companion_eval_scorecard.json.\n")
    return 0


def ingest_companion(turn: int, artifact_root: str = ".tmp") -> int:
    """Adapter: build a normalized ai_eval_results.json from a companion flywheel turn's
    grades.json (verdict -> passed, latency_ms if present). The grader is the existing scorer;
    this just normalizes its output into the gate's input shape. No model calls."""
    grades_path = ROOT / artifact_root / f"flywheel-turn-{turn}" / "grades.json"
    grades = _load_json(grades_path)
    if not isinstance(grades, list):
        print(f"{YEL}No grades.json at {grades_path} — run the companion grader for turn {turn} first.{RESET}")
        return 0
    results = []
    for g in grades:
        gid = g.get("id") or g.get("probe_id")
        if not gid:
            continue
        verdict = (g.get("verdict") or "").upper()
        results.append({
            "id": gid,
            "passed": verdict == "PASS" if verdict else None,
            "score": g.get("score"),
            "latency_ms": g.get("latency_ms") or g.get("latency"),
            "tokens": g.get("tokens"),
        })
    out = {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": f"companion-grader:turn-{turn}", "results": results}
    RESULTS_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{GREEN}Ingested{RESET} {len(results)} companion grades from turn {turn} -> {RESULTS_PATH.name}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="AI eval regression gate (C2) — score vs golden on the locked split")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("baseline", help="freeze current results as the golden score floor")
    g = sub.add_parser("gate", help="score latest vs baseline; exit 1 on locked-test regression")
    g.add_argument("--from", dest="from_path", default=None, help="results JSON path (default ai_eval_results.json)")
    sub.add_parser("report", help="per-split x per-dimension scorecard")
    cr = sub.add_parser("companion-report", help="Phase 8: per-companion-dimension scorecard (informational)")
    cr.add_argument("--from", dest="cr_from", default=None, help="results JSON path (default ai_eval_results.json)")
    ic = sub.add_parser("ingest-companion", help="build ai_eval_results.json from a companion turn's grades.json")
    ic.add_argument("--turn", type=int, required=True)
    ic.add_argument("--artifact-root", default=".tmp")
    args = ap.parse_args()

    cmd = args.cmd or "report"
    if cmd == "baseline":
        return baseline()
    if cmd == "gate":
        return gate(Path(args.from_path) if args.from_path else None)
    if cmd == "companion-report":
        return companion_report(Path(args.cr_from) if args.cr_from else None)
    if cmd == "ingest-companion":
        return ingest_companion(args.turn, args.artifact_root)
    return report()


if __name__ == "__main__":
    sys.exit(main())
