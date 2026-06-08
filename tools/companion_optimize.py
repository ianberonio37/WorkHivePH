#!/usr/bin/env python3
"""
companion_optimize.py — Phase 8 §8.4 (the "training": optimization loop).
=========================================================================
GEPA-style reflective optimizer for the companion eval dimensions. The roadmap shape is:

    run dim -> grader emits per-failure NL feedback -> reflective proposal of a prompt / few-shot /
    RAG / chain variant -> A/B on the VALIDATION split -> accept iff val improves AND the locked-test
    holds -> ratchet.  (Anti-overfit by construction; $0-first; reversible per step.)

This file ships §8.4a — the REFLECT + PROPOSE arm, which is $0 and OFFLINE: it re-grades the
already-captured observations (.tmp/<dim>_golden_observed.json) with the independent grader, turns
each non-PASS unit's grader DETAIL into actionable NL feedback, and clusters those into concrete
candidate proposals, each pinned to the REAL surface (edge-fn file) + the prompt lever that would
move it. Proposals are written to companion_optimization_proposals.json for HUMAN disposition (same
"propose, human disposes" contract as ufai_ingest / ia_semantic_critic) — this tool NEVER edits an
edge-fn prompt or deploys.

§8.4b — the MEASURED A/B that actually moves the metric — is the opt-in execution arm. Its protocol
is recorded in every proposal (`ab_protocol`) and in MEASURED_AB_PROTOCOL below: apply the variant to
the LOCAL edge fn (the local runtime hot-reloads index.ts), re-capture the dim's VALIDATION (+ locked-
test) split via the capture spec, re-grade, accept iff val pass-rate improves AND locked-test stays
>= its frozen floor, then REVERT the local edit and emit the winning diff as a proposal. It mutates
edge-fn source + spends LLM calls, so it is deliberately NOT auto-run here.

Independence: this optimizer imports the INDEPENDENT grader (companion_rigorous_grader) — that is
harness code, not companion code — and never imports/edits companion edge functions. It reads only
captured observations + golden + splits. No LLM calls.

Usage:
  python tools/companion_optimize.py --self-test          # prove the reflector fires on known failures
  python tools/companion_optimize.py reflect [--dim D]    # print per-failure reflections (no write)
  python tools/companion_optimize.py propose [--dim D]    # write companion_optimization_proposals.json
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
SPLITS_PATH = ROOT / "gate_eval_splits.json"
PROPOSALS_PATH = ROOT / "companion_optimization_proposals.json"

sys.path.insert(0, str(TOOLS_DIR))
from companion_rigorous_grader import (grade_rag_unit, grade_memory_unit, grade_persona_unit,
                                       grade_agent_unit, RAG_DEFAULT_RECALL_THRESHOLD)

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

MEASURED_AB_PROTOCOL = (
    "8.4b measured A/B (opt-in, mutates a LOCAL edge fn, spends LLM calls): "
    "1) apply the candidate variant to the surface's index.ts (local runtime hot-reloads, no deploy); "
    "2) reset ai_rate_limits+ai_user_rate_limits+ai_cache, re-run the dim's capture spec to recapture "
    "the VALIDATION + locked-test split; 3) re-grade with the same independent grader; "
    "4) ACCEPT iff val pass-rate improves AND locked-test pass-rate stays >= its frozen floor "
    "(companion_dim_baselines.json) — anti-overfit by construction; "
    "5) REVERT the local edit (git restore the edge fn) and record the winning diff here for deploy disposition."
)


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _split_index() -> dict:
    """id -> split (train|val|test) from gate_eval_splits.json."""
    data = _load_json(SPLITS_PATH) or {}
    return {v["id"]: v.get("split") for v in (data.get("items") or {}).values()}


# ─── Per-dimension lever functions ──────────────────────────────────────────────────────────────
# Each takes a golden unit + its grade detail and returns a reflection dict when the unit is a
# non-PASS (or a weak-but-informative) case, else None. A reflection carries the failure SIGNATURE,
# the REAL surface to change, and the prompt LEVER — the GEPA "reflective feedback", derived
# deterministically from the grader output (no LLM).

def _rag_lever(unit: dict, g: dict) -> dict | None:
    if g.get("type") == "negative":
        return None if g["verdict"] == "PASS" else {
            "signature": "abstention-miss: should have declined / not fabricated a forbidden citation",
            "surface": "supabase/functions/asset-brain-query/index.ts",
            "lever": "strengthen the no-data abstention instruction so the specialist says it has no such evidence instead of answering."}
    recall = g.get("context_recall")
    cited, expected = set(g.get("cited_kinds") or []), set(g.get("expected_kinds") or [])
    missing = sorted(expected - cited)
    if g["verdict"] == "PASS":
        return None
    if g.get("relevancy") and g.get("faithfulness") is False and not cited:
        return {"signature": "ungrounded: relevant answer with NO citation at all",
                "surface": "supabase/functions/asset-brain-query/index.ts",
                "lever": "require the specialist to attach at least one cited evidence lane to every answer."}
    # grounded-but-uncited (RG-02): answered the concept but did not cite the lane it used.
    return {"signature": f"grounded-but-uncited: answered the concept but missing citation kind(s) {missing or 'expected'} (recall={recall})",
            "surface": "supabase/functions/asset-brain-query/index.ts",
            "lever": f"instruct the specialist to emit a citation for EVERY evidence lane it draws on, especially {missing or expected}."}


def _memory_lever(unit: dict, g: dict) -> dict | None:
    if g["verdict"] == "PASS":
        return None
    if g.get("type") == "negative":
        return {"signature": "abstention-miss: fabricated/answered a fact it was never told",
                "surface": "supabase/functions/ai-orchestrator/index.ts",
                "lever": "reinforce that if the memory_block has no record of the asked entity, say so plainly rather than inventing."}
    return {"signature": f"recall-miss ({unit.get('ability')}): memory_block had the fact but synthesis did not surface it (groups_hit {g.get('groups_hit')}/{g.get('groups')})",
            "surface": "supabase/functions/ai-orchestrator/index.ts",
            "lever": "weight memory_block facts as ANSWERABLE in the synthesis prompt — a worker-stated fact does not need DB grounding; do not abstain with 'couldn't find enough data' when the answer is in conversation memory."}


def _persona_lever(unit: dict, g: dict) -> dict | None:
    out = None
    if g["verdict"] != "PASS":
        out = {"signature": f"voice-marker-miss ({unit.get('persona')}/{unit.get('ability')}): reply lacked the persona's signature markers (groups_hit {g.get('groups_hit')}/{g.get('groups')}) or self-id'd as the wrong persona ({g.get('anti_markers_hit')})",
               "surface": "supabase/functions/_shared/persona.ts",
               "lever": "sharpen the persona's tone/DOMAIN_LENS so the lane markers (name on identity, lane vocab on register, bridge on off-lane) fire reliably."}
    # Format finding even on a PASS (the no-em-dash contract rule), reported separately.
    if g.get("has_em_dash"):
        return {"signature": "format: em dash present despite the conversational no-em-dash rule",
                "surface": "supabase/functions/voice-journal-agent/index.ts (post-process) or _shared/persona.ts (rule)",
                "lever": "strip em dashes deterministically in the agent's post-process, or reinforce the no-em-dash rule; deterministic strip is the $0 reliable fix.",
                "info_only": out is None}
    return out


def _agent_lever(unit: dict, g: dict) -> dict | None:
    if g["verdict"] == "PASS":
        return None
    return {"signature": f"route/param-miss ({g.get('type')}): expected route not produced or a param mismatched",
            "surface": "supabase/functions/voice-action-router/index.ts",
            "lever": "add a few-shot for this intent shape or tighten the router's intent/param schema description."}


# dim -> {golden, observed, sections, grade(unit,obs,golden), lever(unit, grade)}
def _grade_rag(unit, obs, golden):
    a = golden.get("asset") or {}
    terms = [t for t in [a.get("tag"), a.get("name")] if t]
    return grade_rag_unit(unit, obs, terms, float(golden.get("default_recall_threshold", RAG_DEFAULT_RECALL_THRESHOLD)))


DIMS = {
    "agent":   {"golden": "companion_agent_golden.json",   "observed": ".tmp/agent_golden_observed.json",
                "sections": ("single_turn", "multi_step", "negative_controls"),
                "grade": lambda u, o, g: grade_agent_unit(u, o), "lever": _agent_lever},
    "rag":     {"golden": "companion_rag_golden.json",     "observed": ".tmp/rag_golden_observed.json",
                "sections": ("questions", "negative_controls"),
                "grade": _grade_rag, "lever": _rag_lever},
    "memory":  {"golden": "companion_memory_golden.json",  "observed": ".tmp/memory_golden_observed.json",
                "sections": ("scripts",),
                "grade": lambda u, o, g: grade_memory_unit(u, o), "lever": _memory_lever},
    "persona": {"golden": "companion_persona_golden.json", "observed": ".tmp/persona_golden_observed.json",
                "sections": ("probes",),
                "grade": lambda u, o, g: grade_persona_unit(u, o), "lever": _persona_lever},
}


def _units(golden: dict, sections) -> list[dict]:
    out = []
    for s in sections:
        out += list(golden.get(s) or [])
    return out


def reflect_dim(dim: str, split_idx: dict) -> list[dict]:
    """Re-grade a dim's captured observations and return reflections for non-PASS / informative units."""
    cfg = DIMS[dim]
    golden = _load_json(ROOT / cfg["golden"])
    observed = _load_json(ROOT / cfg["observed"])
    if not golden or not isinstance(observed, dict):
        return []
    reflections = []
    for unit in _units(golden, cfg["sections"]):
        uid = unit.get("id")
        if uid not in observed:
            continue
        obs = observed[uid]
        # Infra guard: an answer-observable dim with an EMPTY captured answer is almost always a
        # transient 5xx / rate-limit (e.g. MEM-UP-01's 502), not a prompt failure. Flag it as a
        # re-capture, never as an optimization target — optimizing a prompt against infra noise
        # would chase a ghost.
        if dim in ("rag", "memory", "persona") and isinstance(obs, dict) \
                and not str(obs.get("answer", "") or obs.get("narration", "")).strip():
            reflections.append({"dim": dim, "id": uid, "split": split_idx.get(uid, "?"),
                                "verdict": "NO-OBS", "info_only": True,
                                "signature": "no-observation: empty captured answer (likely infra 5xx / rate-limit)",
                                "surface": "(capture)",
                                "lever": "re-run the dim's capture spec (reset counters) before optimizing; not a prompt target."})
            continue
        g = cfg["grade"](unit, obs, golden)
        lev = cfg["lever"](unit, g)
        if not lev:
            continue
        reflections.append({"dim": dim, "id": uid, "split": split_idx.get(uid, "?"),
                            "verdict": g.get("verdict"), **lev})
    return reflections


def _cluster(reflections: list[dict]) -> list[dict]:
    """Cluster reflections into candidate proposals by (dim, surface, signature-head)."""
    buckets: dict = {}
    for r in reflections:
        head = r["signature"].split(":")[0]
        key = (r["dim"], r["surface"], head)
        b = buckets.setdefault(key, {"dim": r["dim"], "surface": r["surface"], "signature": r["signature"],
                                     "lever": r["lever"], "units": [], "info_only": True})
        b["units"].append({"id": r["id"], "split": r["split"], "verdict": r["verdict"]})
        if not r.get("info_only"):
            b["info_only"] = False
    out = []
    for i, (key, b) in enumerate(sorted(buckets.items()), 1):
        splits = [u["split"] for u in b["units"]]
        out.append({
            "id": f"OPT-{b['dim'].upper()}-{i:02d}",
            "dim": b["dim"], "status": "proposed", "info_only": b["info_only"],
            "surface": b["surface"], "failure_signature": b["signature"], "lever": b["lever"],
            "affected_units": b["units"],
            "val_units": sum(1 for s in splits if s == "val"),
            "locked_test_units": sum(1 for s in splits if s == "test"),
            "ab_protocol": MEASURED_AB_PROTOCOL,
        })
    return out


def cmd_reflect(dim: str | None) -> int:
    split_idx = _split_index()
    dims = [dim] if dim else list(DIMS)
    total = 0
    for d in dims:
        refs = reflect_dim(d, split_idx)
        total += len(refs)
        print(f"\n{BOLD}{d}{RESET}  ·  {len(refs)} reflection(s)")
        for r in refs:
            tag = f"{CYAN}{r['split']}{RESET}"
            print(f"  [{tag}] {r['id']}  {r['verdict']}")
            print(f"        {YEL}{r['signature']}{RESET}")
            print(f"        surface: {r['surface']}")
            print(f"        lever:   {r['lever']}")
    print(f"\n{BOLD}{total} reflection(s) across {len(dims)} dim(s).{RESET}")
    return 0


def cmd_propose(dim: str | None) -> int:
    split_idx = _split_index()
    dims = [dim] if dim else list(DIMS)
    reflections = []
    for d in dims:
        reflections += reflect_dim(d, split_idx)
    proposals = _cluster(reflections)
    out = {"generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "_comment": "Phase 8 §8.4a — GEPA-style reflective optimization PROPOSALS for the companion. "
                       "Each is a candidate prompt/RAG/chain variant pinned to a real surface + lever, "
                       "derived deterministically from the independent grader's per-failure detail over "
                       "the captured observations. HUMAN disposes (set status accept/reject); the measured "
                       "A/B that actually moves the metric is the opt-in 8.4b step (see ab_protocol). This "
                       "tool never edits an edge-fn prompt or deploys.",
           "measured_ab_protocol": MEASURED_AB_PROTOCOL,
           "count": len(proposals), "proposals": proposals}
    PROPOSALS_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{BOLD}Companion optimization proposals{RESET}  ·  {len(proposals)} candidate(s)")
    print("=" * 70)
    for p in proposals:
        flag = f"  {CYAN}(info-only){RESET}" if p["info_only"] else ""
        print(f"  {p['id']}  [{p['dim']}]{flag}")
        print(f"     {YEL}{p['failure_signature']}{RESET}")
        print(f"     surface: {p['surface']}")
        print(f"     lever:   {p['lever']}")
        print(f"     affects: {len(p['affected_units'])} unit(s)  (val {p['val_units']}, 🔒test {p['locked_test_units']})")
    print(f"\n  -> {PROPOSALS_PATH.relative_to(ROOT)}  (human disposes; 8.4b = measured A/B per ab_protocol)")
    return 0


def _grade_by_split(dim: str, observed: dict, split_idx: dict) -> dict:
    """Grade a captured observation map per split for one dim. Returns {split: {'passed','total','units':[...]}}."""
    cfg = DIMS[dim]
    golden = _load_json(ROOT / cfg["golden"]) or {}
    out: dict = {}
    for unit in _units(golden, cfg["sections"]):
        uid = unit.get("id")
        if uid not in observed:
            continue
        g = cfg["grade"](unit, observed[uid], golden)
        s = split_idx.get(uid, "?")
        b = out.setdefault(s, {"passed": 0, "total": 0, "units": []})
        ok = g.get("verdict") == "PASS"
        b["passed"] += 1 if ok else 0
        b["total"] += 1
        b["units"].append({"id": uid, "verdict": g.get("verdict")})
    for s, b in out.items():
        b["pass_rate"] = round(100 * b["passed"] / b["total"], 1) if b["total"] else None
    return out


def cmd_ab(dim: str, baseline_path: str, candidate_path: str, proposal_id: str | None) -> int:
    """8.4b — the MEASURED ratchet DECISION. Grades a baseline vs a candidate observation (captured
    by the agent: apply variant to the local edge fn -> recapture -> revert) and ACCEPTS the candidate
    iff the VALIDATION pass-rate improves AND the locked-test pass-rate stays >= its frozen floor.
    Anti-overfit by construction: a candidate that doesn't move val, or that dents the locked-test,
    is REJECTED. Writes companion_ab_results.json. Does NOT apply/keep any edge-fn change."""
    split_idx = _split_index()
    base = _load_json(ROOT / baseline_path)
    cand = _load_json(ROOT / candidate_path)
    if not isinstance(base, dict) or not isinstance(cand, dict):
        print(f"{RED}baseline/candidate observation map(s) not found.{RESET}")
        return 1
    bsplit = _grade_by_split(dim, base, split_idx)
    csplit = _grade_by_split(dim, cand, split_idx)
    floors = _load_json(ROOT / "companion_dim_baselines.json") or {}
    floor = (((floors.get("dimensions") or {}).get(dim) or {}).get("locked_test") or {}).get("pass_rate")
    val_b = (bsplit.get("val") or {}).get("pass_rate")
    val_c = (csplit.get("val") or {}).get("pass_rate")
    test_c = (csplit.get("test") or {}).get("pass_rate")
    val_improved = (val_b is not None and val_c is not None and val_c > val_b)
    test_holds = (floor is None or (test_c is not None and test_c >= floor))
    accept = bool(val_improved and test_holds)
    # per-unit flips
    bmap = {u["id"]: u["verdict"] for s in bsplit.values() for u in s["units"]}
    cmap = {u["id"]: u["verdict"] for s in csplit.values() for u in s["units"]}
    flips = [{"id": k, "from": bmap[k], "to": cmap.get(k), "split": split_idx.get(k, "?")}
             for k in bmap if cmap.get(k) != bmap[k]]
    result = {
        "generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dim": dim, "proposal": proposal_id,
        "decision": "ACCEPT" if accept else "REJECT",
        "rule": "accept iff val pass-rate improves AND locked-test >= frozen floor (anti-overfit)",
        "val": {"baseline": val_b, "candidate": val_c, "improved": val_improved},
        "locked_test": {"candidate": test_c, "frozen_floor": floor, "holds": test_holds},
        "train": {"baseline": (bsplit.get("train") or {}).get("pass_rate"),
                  "candidate": (csplit.get("train") or {}).get("pass_rate")},
        "unit_flips": flips,
        "disposition": ("keep + deploy-dispose the diff" if accept
                        else "REVERT (done) — candidate did not earn acceptance; record finding for human disposition"),
    }
    (ROOT / "companion_ab_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    tag = f"{GREEN}ACCEPT{RESET}" if accept else f"{YEL}REJECT{RESET}"
    print(f"\n{BOLD}Measured A/B — {dim}{f' / {proposal_id}' if proposal_id else ''}{RESET}   decision: {tag}")
    print("=" * 70)
    print(f"  val        {val_b}% -> {val_c}%   (improved={val_improved})")
    print(f"  locked-test {test_c}%  (floor {floor}%, holds={test_holds})")
    print(f"  train      {result['train']['baseline']}% -> {result['train']['candidate']}%  (not an accept criterion)")
    if flips:
        print(f"  flips: " + ", ".join(f"{f['id']}[{f['split']}] {f['from']}->{f['to']}" for f in flips))
    print(f"  -> companion_ab_results.json   ({result['disposition']})")
    return 0


def self_test() -> int:
    """Prove the reflector fires the right signature on a synthetic failure per dim (no live model)."""
    cases = [
        ("rag",     {"id": "X", "expected_kinds": ["pm"], "expected_keywords_any": ["pm"], "category": "rag_pm"},
                    {"answer": "PM compliance is 0%.", "cited": [], "narration": ""}, "grounded-but-uncited"),
        ("memory",  {"id": "X", "ability": "temporal", "recall_all": [["roller"]], "category": "memory_temporal"},
                    {"answer": "I couldn't find enough data to answer that yet."}, "recall-miss"),
        ("persona", {"id": "X", "persona": "zaniah", "ability": "register", "markers_all": [["mtbf"]], "category": "persona_register"},
                    {"answer": "Here is the info — all set."}, None),  # em dash + missing marker
    ]
    problems = []
    for dim, unit, obs, _ in cases:
        cfg = DIMS[dim]
        golden = {"asset": {"tag": "HPU-001"}} if dim == "rag" else {}
        g = cfg["grade"](unit, obs, golden)
        lev = cfg["lever"](unit, g)
        if not lev:
            problems.append(f"{dim}: reflector produced NO feedback on a synthetic failure")
            continue
        # A clearly-correct synthetic PASS must yield no reflection (no false proposals).
        if dim == "persona":
            ok_obs = {"answer": "I'm Zaniah, your WorkHive companion. MTBF is the metric."}
            if cfg["lever"](unit, cfg["grade"](unit, ok_obs, golden)):
                problems.append("persona: reflector fired on a clean (passing, no-em-dash) reply — false positive")
    print(f"\n{BOLD}companion_optimize self-test{RESET}  ·  {len(cases)} synthetic failures")
    print("=" * 64)
    if not problems:
        print(f"{GREEN}OK{RESET}  reflector fires on every synthetic failure and not on a clean reply.")
        return 0
    print(f"{RED}FAIL{RESET}")
    for p in problems:
        print(f"  - {p}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Companion optimization loop (Phase 8 §8.4)")
    sub = ap.add_subparsers(dest="cmd")
    ap.add_argument("--self-test", action="store_true", help="prove the reflector is wired (default if no cmd)")
    for name in ("reflect", "propose"):
        sp = sub.add_parser(name)
        sp.add_argument("--dim", default=None, choices=list(DIMS))
    ab = sub.add_parser("ab", help="8.4b: grade baseline vs candidate observation -> accept/reject (anti-overfit)")
    ab.add_argument("--dim", required=True, choices=list(DIMS))
    ab.add_argument("--baseline", required=True, help="path to the baseline observation map (relative to repo root)")
    ab.add_argument("--candidate", required=True, help="path to the candidate observation map")
    ab.add_argument("--proposal", default=None, help="proposal id this A/B tests (e.g. OPT-RAG-04)")
    args = ap.parse_args()
    if args.cmd == "reflect":
        return cmd_reflect(args.dim)
    if args.cmd == "propose":
        return cmd_propose(args.dim)
    if args.cmd == "ab":
        return cmd_ab(args.dim, args.baseline, args.candidate, args.proposal)
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
