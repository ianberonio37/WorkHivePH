"""
Companion Perturbation-Invariance Generator — Probe Taxonomy §9 #2 (grokking-informed).
=======================================================================================
Write ONE golden question; auto-spawn k surface VARIANTS (casing/STT-typo/filler/distractor/
reorder/Taglish-wrap/Cebuano-wrap) that preserve the gradeable intent; run seed + variants LIVE
through the ai-gateway and require the SAME verdict. "invariance %" = the generalization score
(how often the companion answers a rephrasing the way it answered the original). A memorizer that
pattern-matched the seed surface flips on the variants -> low invariance; a model that generalized
from the foundation pretraining + our doctrine stays put -> high invariance.

This is the direct answer to the standing constraint "millions of scenarios, no time to hand-write
them" (COMPANION_DEV_TOOL.md §9): we do NOT enumerate scenarios, we scale the corpus MULTIPLICATIVELY
from a few principle-grounded seeds and MEASURE generalization on the perturbed (held-out-by-
construction) variants. The companion is a FROZEN API model, so we can't induce grokking in its
weights — but the grokking lesson (train acc lied, held-out told the truth; a memorizer fails on
rephrased inputs) is exactly this measurement.

REUSE (no new runtime, no new grader):
  - companion_live_capture.call_voice_journal / answer_of / reset_counters  (the LIVE runtime)
  - companion_rigorous_grader.grade_markers_unit                            (the generic verdict)
  - companion_rigorous_grader._domain_oracle_observed / _domain_blind_observed (self-test sims)
The perturbations are DETERMINISTIC (seeded per question+type) so a seed always yields the same
variants and the self-test is reproducible offline.

Modes:
  --self-test            (default) NO live calls. Proves (a) the generator emits k distinct,
                         intent-preserving variants per seed, and (b) the invariance metric
                         DISCRIMINATES a simulated generalizer (every variant PASS -> 100%) from a
                         simulated memorizer (only the exact seed PASSes -> ~0%). Same oracle/blind
                         discipline as the dim graders; green = the metric is meaningful, not a
                         rubber stamp. Exits 1 if the metric fails to discriminate.
  --live --family F      Generate variants for every unit in family F's golden, call the gateway for
                         seed + each variant (counters reset + paced, like companion_live_capture),
                         grade each with grade_markers_unit, report per-unit + mean invariance.
  --samples K            (§9 #4 rider) Multi-sample EACH call K times; aggregate the per-call verdict
                         by majority (or --gate worst), and report per-unit run-to-run VARIANCE
                         (high variance = not robustly learned; de-noises the ROB-F6-style flips).
  --emit                 Write PASSing new variant phrasings to .tmp/companion_perturb_candidates.json
                         as golden-unit skeletons (split hint train/val ONLY, NEVER locked-test) for
                         human disposal — legitimate corpus growth toward the n>=20 gate threshold.

Families (reused from companion_live_capture.FAMILIES): domain | robustness | doctrine | safety_gaps.
"""
from __future__ import annotations
import argparse
import io
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Wrap stdout to UTF-8 BEFORE importing companion_live_capture so its identical guard no-ops
# (its guard checks sys.stdout.encoding; once we've wrapped, it sees utf-8 and skips re-wrapping).
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
OUT_DIR = ROOT / ".tmp"

sys.path.insert(0, str(TOOLS_DIR))
from companion_rigorous_grader import (  # noqa: E402
    grade_markers_unit, _domain_oracle_observed, _domain_blind_observed,
)
import companion_live_capture as live  # noqa: E402  (call_voice_journal / answer_of / reset_counters / FAMILIES)

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

# A unit is "brittle" when more than a third of its variants flip the seed verdict.
INVARIANCE_BRITTLE = 0.67
# A multi-sampled call is "noisy" when more than a third of its samples disagree with the majority.
VARIANCE_NOISY = 0.34

# Deterministic distractor prefixes (irrelevant friendly chatter — tests distractor robustness like F4).
_DISTRACTORS = [
    "by the way the canteen food was amazing today haha anyway ",
    "oh and traffic was crazy this morning, anyway ",
    "random but my phone battery is dying lol, so ",
    "kumain ka na ba? anyway ",
]
# STT-style hesitation fillers (front + mid injection).
_FILLERS_FRONT = ["uh, um... ", "ah, eto, ", "hmm, so, "]


def _seeded(text: str, ptype: str) -> random.Random:
    """A per-(question,type) RNG so the same seed always spawns the same variant (reproducible self-test)."""
    return random.Random(f"{ptype}::{text}")


def _marker_tokens(unit: dict) -> set[str]:
    """Flatten markers_all/markers_any synonym groups to a lowercase token set — these are the gradeable
    words the typo perturbation must NOT corrupt (corrupting them would change the expected answer,
    making the variant an unfair, different question rather than a surface rephrasing)."""
    toks: set[str] = set()
    for g in (unit.get("markers_all") or []):
        for s in (g if isinstance(g, list) else [g]):
            for w in re.findall(r"[a-z0-9\-]+", str(s).lower()):
                if len(w) >= 3:
                    toks.add(w)
    for s in (unit.get("markers_any") or []):
        for w in re.findall(r"[a-z0-9\-]+", str(s).lower()):
            if len(w) >= 3:
                toks.add(w)
    return toks


# ── Perturbation generators ──────────────────────────────────────────────────
# Each takes (question, rng, protected_tokens) and returns a CHANGED string, or None if the transform
# does not apply / produced no change (those are skipped — variants are only the distinct ones).

def p_casing(q: str, rnd, protected) -> str | None:
    v = q.lower().rstrip(" ?.!")
    return v if v != q else None


def p_filler(q: str, rnd, protected) -> str:
    return rnd.choice(_FILLERS_FRONT) + q


def p_distractor(q: str, rnd, protected) -> str:
    return rnd.choice(_DISTRACTORS) + q


def p_reorder(q: str, rnd, protected) -> str | None:
    """Swap the two clauses around the first connector — preserves all tokens, changes word order."""
    for sep in (" tapos ", " then ", " and ", ", "):
        if sep in q:
            head, tail = q.split(sep, 1)
            if head.strip() and tail.strip():
                return f"{tail.strip().rstrip('?.!')} — {head.strip()}?"
    return None


def p_typo(q: str, rnd, protected) -> str | None:
    """Apply up to 2 STT-style adjacent-char swaps to long, NON-marker words (markers stay intact)."""
    words = q.split(" ")
    eligible = [i for i, w in enumerate(words)
                if len(re.sub(r"[^a-zA-Z]", "", w)) >= 5
                and not any(t in w.lower() for t in protected)]
    if not eligible:
        return None
    changed = False
    for i in rnd.sample(eligible, min(2, len(eligible))):
        w = words[i]
        a = [c for c in w]
        # swap two adjacent interior letters
        letters = [j for j, c in enumerate(a) if c.isalpha()]
        if len(letters) >= 3:
            k = rnd.choice(letters[1:-1])
            if k + 1 < len(a) and a[k + 1].isalpha():
                a[k], a[k + 1] = a[k + 1], a[k]
                words[i] = "".join(a)
                changed = True
    v = " ".join(words)
    return v if changed and v != q else None


def p_taglish(q: str, rnd, protected) -> str:
    return f"boss, {q.rstrip('?.! ')}, ano sa tingin mo?"


def p_cebuano(q: str, rnd, protected) -> str:
    return f"bai, {q.rstrip('?.! ')}, unsa man imong sugyot?"


PERTURBATIONS = {
    "casing": p_casing, "filler": p_filler, "distractor": p_distractor,
    "reorder": p_reorder, "typo": p_typo, "taglish": p_taglish, "cebuano": p_cebuano,
}


def make_variants(unit: dict, types: list[str]) -> list[dict]:
    """Build the distinct surface variants for one seed unit. Each carries the SAME markers/anti, so
    the verdict is expected to be invariant; only the QUESTION surface changes."""
    q = unit.get("question") or unit.get("utterance") or ""
    protected = _marker_tokens(unit)
    out, seen = [], {q.strip().lower()}
    for ptype in types:
        fn = PERTURBATIONS[ptype]
        v = fn(q, _seeded(q, ptype), protected)
        if not v:
            continue
        key = v.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"parent_id": unit.get("id"), "ptype": ptype, "question": v})
    return out


# ── Invariance metric ────────────────────────────────────────────────────────

def invariance_of(seed_verdict: str, variant_verdicts: list[str]) -> float:
    """Fraction of variants whose verdict matches the seed's. 1.0 = the rephrasings did not move the
    answer (generalized); low = the model keyed off the seed surface (memorized)."""
    if not variant_verdicts:
        return 1.0
    same = sum(1 for v in variant_verdicts if v == seed_verdict)
    return same / len(variant_verdicts)


def _verdict(unit: dict, answer: str) -> str:
    return grade_markers_unit(unit, {"answer": answer})["verdict"]


# ── Live run ─────────────────────────────────────────────────────────────────

def _aggregate(verdicts: list[str], gate: str) -> tuple[str, float]:
    """Collapse K sampled verdicts to one + a variance score (fraction disagreeing with the majority)."""
    if not verdicts:
        return "ERROR", 0.0
    counts = Counter(verdicts)
    majority, n = counts.most_common(1)[0]
    variance = 1.0 - (n / len(verdicts))
    if gate == "worst":
        verdict = "FAIL" if "FAIL" in counts else majority
    else:
        verdict = majority
    return verdict, round(variance, 3)


def _sampled_verdict(unit: dict, question: str, conn, samples: int, pace: float,
                     no_reset: bool, gate: str) -> dict:
    """Call the gateway `samples` times for one question, grade each reply, aggregate."""
    verdicts, answers = [], []
    for _ in range(samples):
        if not no_reset:
            live.reset_counters(conn)
        r = live.call_voice_journal(question)
        ans = live.answer_of(r["body"]) if r["ok"] else ""
        verdicts.append(_verdict(unit, ans) if ans else "ERROR")
        answers.append(ans)
        time.sleep(pace)
    verdict, variance = _aggregate(verdicts, gate)
    return {"verdict": verdict, "variance": variance, "samples": verdicts,
            "answer": answers[0] if answers else ""}


def run_live(golden_path: Path, dim: str, types: list[str], samples: int, pace: float,
             no_reset: bool, gate: str, emit: bool) -> int:
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    units = [u for u in (golden.get("probes") or golden.get("units") or []) if _marker_tokens(u)]
    if not units:
        print(f"{YEL}No marker-bearing units in {golden_path.name}.{RESET}")
        return 0

    conn = None
    if not no_reset and live.psycopg2 is not None:
        try:
            conn = live.psycopg2.connect(live.DB_DSN)
        except Exception as e:
            print(f"{YEL}WARN: no DB for counter reset ({e}); pacing only.{RESET}")

    print(f"\n{BOLD}{CYAN}== perturbation-invariance · {dim} =={RESET}  {golden_path.name}"
          f"  ({len(units)} seeds · {len(types)} perturbations · samples={samples} · gate={gate})")
    report_units, candidates = [], []
    n_calls = 0
    for u in units:
        variants = make_variants(u, types)
        seed_q = u.get("question") or u.get("utterance") or ""
        seed = _sampled_verdict(u, seed_q, conn, samples, pace, no_reset, gate)
        n_calls += samples
        v_results = []
        for var in variants:
            sv = _sampled_verdict(u, var["question"], conn, samples, pace, no_reset, gate)
            n_calls += samples
            v_results.append({**var, "verdict": sv["verdict"], "variance": sv["variance"]})
            if emit and sv["verdict"] == "PASS" and sv["verdict"] == seed["verdict"]:
                candidates.append(_candidate_skeleton(u, var, dim))
        inv = invariance_of(seed["verdict"], [v["verdict"] for v in v_results])
        passes = sum(1 for v in [seed] + v_results if v["verdict"] == "PASS")
        pass_rate = passes / (1 + len(v_results))
        max_var = max([seed["variance"]] + [v["variance"] for v in v_results], default=0.0)
        report_units.append({
            "id": u.get("id"), "probe_type": u.get("probe_type"), "ability": u.get("ability"),
            "seed_verdict": seed["verdict"], "seed_variance": seed["variance"],
            "invariance_pct": round(100 * inv, 1), "pass_rate_pct": round(100 * pass_rate, 1),
            "max_variance": max_var, "variants": v_results,
        })
        flag = (GREEN + "stable" + RESET) if inv >= INVARIANCE_BRITTLE else (RED + "BRITTLE" + RESET)
        nvar = YEL + " noisy" + RESET if max_var > VARIANCE_NOISY else ""
        print(f"  {u.get('id'):<10} seed={seed['verdict']:<5} inv={round(100*inv,1):>5}%  "
              f"pass={round(100*pass_rate,1):>5}%  {flag}{nvar}  ({len(v_results)} variants)")

    mean_inv = round(sum(r["invariance_pct"] for r in report_units) / len(report_units), 1)
    mean_pass = round(sum(r["pass_rate_pct"] for r in report_units) / len(report_units), 1)
    brittle = [r["id"] for r in report_units if r["invariance_pct"] < 100 * INVARIANCE_BRITTLE]
    noisy = [r["id"] for r in report_units if r["max_variance"] > VARIANCE_NOISY]
    report = {
        "generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "companion_perturb", "dimension": dim, "golden": golden_path.name,
        "samples": samples, "gate": gate, "perturbations": types, "n_calls": n_calls,
        "summary": {"seeds": len(units), "mean_invariance_pct": mean_inv,
                    "mean_pass_rate_pct": mean_pass, "brittle_units": brittle, "noisy_units": noisy},
        "units": report_units,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{dim}_perturb_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n  {BOLD}mean invariance {mean_inv}%{RESET}  ·  mean pass {mean_pass}%  ·  {n_calls} calls")
    if brittle:
        print(f"  {RED}brittle (invariance < {int(100*INVARIANCE_BRITTLE)}%): {', '.join(brittle)}{RESET}")
    if noisy:
        print(f"  {YEL}noisy (run-to-run variance > {VARIANCE_NOISY}): {', '.join(noisy)}{RESET}")
    print(f"  -> {out_path.relative_to(ROOT)}")
    if emit and candidates:
        cand_path = OUT_DIR / "companion_perturb_candidates.json"
        cand_path.write_text(json.dumps({
            "_comment": "PASSing perturbation variants — corpus-growth CANDIDATES, human-disposed. "
                        "split is train/val ONLY; NEVER promote a perturbation into the locked-test "
                        "split (it derives from a seed the prompt may have been tuned against).",
            "generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dimension": dim, "candidates": candidates,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  -> {cand_path.relative_to(ROOT)}  ({len(candidates)} variant candidates, human-disposed)")
    if conn:
        conn.close()
    return 0


def _candidate_skeleton(unit: dict, variant: dict, dim: str) -> dict:
    """A golden-unit skeleton for a passing variant — same markers/anti as the parent, train/val split."""
    return {
        "id": f"{unit.get('id')}-pz-{variant['ptype']}",
        "parent_id": unit.get("id"), "perturbation": variant["ptype"],
        "probe_type": unit.get("probe_type"), "dimension": unit.get("dimension") or dim,
        "ability": unit.get("ability"), "question": variant["question"],
        "markers_all": unit.get("markers_all"), "anti_markers": unit.get("anti_markers", []),
        "split_hint": "train_or_val_only_never_locked_test",
    }


# ── Self-test (no live calls) ────────────────────────────────────────────────

def self_test(golden_path: Path, types: list[str]) -> int:
    """Prove the generator + invariance metric WITHOUT a model:
      - generator: every seed yields >=1 distinct, non-empty, intent-preserving variant.
      - GENERALIZER sim (answer always echoes the unit's markers) -> every variant PASSes ->
        per-seed invariance 100%.
      - MEMORIZER sim (echoes markers ONLY for the exact seed string, content-free otherwise) ->
        seed PASSes, every variant FAILs -> per-seed invariance ~0%.
      - the metric DISCRIMINATES: mean generalizer invariance must be strictly > memorizer's, and
        the generalizer must sit at 100% while the memorizer collapses. A non-discriminating metric
        (e.g. ignoring the variants) would score them equal -> FAIL.
    """
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    units = [u for u in (golden.get("probes") or golden.get("units") or []) if _marker_tokens(u)]
    if not units:
        print(f"{YEL}No marker-bearing units in {golden_path.name} — nothing to self-test.{RESET}")
        return 0

    problems: list[str] = []
    gen_invs, mem_invs = [], []
    total_variants = 0
    for u in units:
        variants = make_variants(u, types)
        total_variants += len(variants)
        if not variants:
            problems.append(f"{u.get('id')}: generator produced 0 variants")
            continue
        seed_q = (u.get("question") or u.get("utterance") or "").strip().lower()
        for v in variants:
            if not v["question"].strip():
                problems.append(f"{u.get('id')}/{v['ptype']}: empty variant")
            if v["question"].strip().lower() == seed_q:
                problems.append(f"{u.get('id')}/{v['ptype']}: variant identical to seed")

        oracle_ans = _domain_oracle_observed(u)["answer"]   # echoes the unit's markers
        blind_ans = _domain_blind_observed(u)["answer"]     # content-free

        # GENERALIZER: same (marker-echoing) answer for seed + every variant.
        gen_seed = _verdict(u, oracle_ans)
        gen_vars = [_verdict(u, oracle_ans) for _ in variants]
        gen_inv = invariance_of(gen_seed, gen_vars)
        gen_invs.append(gen_inv)
        if gen_seed != "PASS":
            problems.append(f"{u.get('id')}: oracle answer did not PASS the seed (markers unreachable)")
        if gen_inv != 1.0:
            problems.append(f"{u.get('id')}: generalizer invariance {gen_inv} != 100% (metric broke)")

        # MEMORIZER: marker-echo ONLY for the exact seed; content-free for every variant.
        mem_seed = _verdict(u, oracle_ans)
        mem_vars = [_verdict(u, blind_ans) for _ in variants]
        mem_inv = invariance_of(mem_seed, mem_vars)
        mem_invs.append(mem_inv)

    mean_gen = sum(gen_invs) / len(gen_invs) if gen_invs else 0.0
    mean_mem = sum(mem_invs) / len(mem_invs) if mem_invs else 0.0
    if mean_gen <= mean_mem:
        problems.append(f"metric does NOT discriminate: generalizer {mean_gen:.2f} <= memorizer {mean_mem:.2f}")
    if mean_mem >= INVARIANCE_BRITTLE:
        problems.append(f"memorizer invariance {mean_mem:.2f} not below brittle floor {INVARIANCE_BRITTLE} "
                        f"— a memorizer should read as BRITTLE")

    print(f"\n{BOLD}Perturbation-invariance self-test{RESET}  ·  {len(units)} seeds · "
          f"{total_variants} variants ({total_variants/len(units):.1f}/seed)")
    print("=" * 70)
    print(f"  generalizer mean invariance : {round(100*mean_gen,1)}%  (must be 100% — rephrasing didn't move the answer)")
    print(f"  memorizer   mean invariance : {round(100*mean_mem,1)}%  (must be ~0% / < {int(100*INVARIANCE_BRITTLE)}% — flips on rephrasing)")
    if not problems:
        print(f"\n{GREEN}OK{RESET}  generator emits intent-preserving variants AND the invariance metric "
              f"separates a generalizer from a memorizer.")
        print("=" * 70)
        return 0
    print(f"\n{RED}FAIL{RESET}  self-test problems:")
    for p in problems:
        print(f"  - {p}")
    print("=" * 70)
    return 1


def _resolve_golden(family: str | None, golden: str | None) -> tuple[Path, str]:
    if golden:
        return Path(golden), (family or "domain")
    fam = family or "robustness"
    if fam not in live.FAMILIES:
        print(f"{RED}Unknown family '{fam}'. Choose: {', '.join(live.FAMILIES)} (or pass --golden).{RESET}")
        sys.exit(2)
    gfile, _out, dim = live.FAMILIES[fam]
    return ROOT / gfile, dim


def main() -> int:
    ap = argparse.ArgumentParser(description="Perturbation-invariance generator (COMPANION_DEV_TOOL.md §9 #2)")
    ap.add_argument("--self-test", action="store_true", help="(default) prove the generator+metric offline")
    ap.add_argument("--live", action="store_true", help="run seed+variants through the live ai-gateway")
    ap.add_argument("--family", default=None, help="domain | robustness | doctrine | safety_gaps")
    ap.add_argument("--golden", default=None, help="explicit golden path (overrides --family)")
    ap.add_argument("--perturbations", default=None,
                    help=f"comma list (default all): {','.join(PERTURBATIONS)}")
    ap.add_argument("--samples", type=int, default=1, help="multi-sample each call K times (§9 #4)")
    ap.add_argument("--gate", default="majority", choices=["majority", "worst"],
                    help="how to collapse K samples to one verdict")
    ap.add_argument("--pace", type=float, default=4.0, help="seconds between live calls (rate-limit pacing)")
    ap.add_argument("--no-reset", action="store_true", help="do NOT reset rate-limit counters between calls")
    ap.add_argument("--emit", action="store_true", help="write passing variants as corpus candidates")
    args = ap.parse_args()

    types = [t.strip() for t in (args.perturbations.split(",") if args.perturbations else PERTURBATIONS)
             if t.strip() in PERTURBATIONS]
    if not types:
        print(f"{RED}No valid perturbations. Choose from: {', '.join(PERTURBATIONS)}{RESET}")
        return 2

    golden_path, dim = _resolve_golden(args.family, args.golden)
    if not golden_path.exists():
        print(f"{RED}missing golden: {golden_path}{RESET}")
        return 2

    if args.live:
        return run_live(golden_path, dim, types, max(1, args.samples), args.pace,
                        args.no_reset, args.gate, args.emit)
    return self_test(golden_path, types)


if __name__ == "__main__":
    sys.exit(main())
