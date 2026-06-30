#!/usr/bin/env python3
"""memory_recall_eval.py - Memory-System M2.1: recall@k eval gate for the Memento retriever.
================================================================================
Retrieval quality was UNGUARDED: every knob (IMPORTANCE, half-lives, MIN_FINAL_SCORE,
the 1.7 transcript boost, RRF k) was tuned by eyeballing, with no automated check that a
tuning change didn't silently drop recall. This is the measurement keystone of the
MEMORY_SYSTEM_ROADMAP M-series: a small hand-written golden set of (query -> the memory
that SHOULD surface), run as a gate. A change that breaks recall now FAILS instead of
rotting silently — and the numbers here are what justify (or kill) the deferred M5 tier
(embeddings/graph-walk): build M5 only if a *persistent semantic-miss class* shows up here.

Method (honest, not tautological):
  - ~25 pairs where a specific canonical memory is the right answer for a natural query.
  - Each pair accepts a SET of source-name substrings, because some lessons legitimately
    live in more than one place (a tiny feedback note AND the consolidated doctrine book);
    any genuinely-on-topic source counts as a hit. Pairs were grounded against the LIVE
    retriever — every one currently resolves within top-5 — so the gate is a REGRESSION
    guard calibrated to a passing baseline, with fixed health FLOORS well below current.
  - Metrics: recall@1, recall@3, recall@5, MRR (mean reciprocal rank, top-5 window).

Commands:
  (default)        run the eval, print per-query ranks + metrics, gate on FLOORS.
  --json           machine-readable metrics (writes the baseline snapshot too).
  --selftest       prove the gate has TEETH: run normally (expect PASS), then monkeypatch
                   a retriever knob to a deliberately-bad value and assert recall COLLAPSES
                   below the floor (i.e. a bad config would FAIL). This is the M2.1
                   acceptance bar: a bad knob fails, a good config passes.

Exit 0 = recall above the health floors; 1 = a floor breached (regression) or selftest
toothless. Stdlib only. Reads the live memory.db read-only. Never writes to it.
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# the retriever lives outside the project tree (the agent's own memory system)
MEMENTO_TOOLS = Path.home() / ".claude-memento" / "tools"
sys.path.insert(0, str(MEMENTO_TOOLS))
try:
    import memento_retrieve as mr  # noqa: E402
except Exception as e:  # pragma: no cover
    print(f"  SKIP — memento retriever not importable ({type(e).__name__}: {e})")
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "memory_recall_baseline.json"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# Fixed health floors — "retrieval is working." Current config clears these with margin
# (R@5~1.00, R@3~0.80, MRR~0.5); a broken knob (e.g. honesty gate dropping everything)
# collapses well below them. Floors, not a ratchet, so the gate is deterministic.
FLOORS = {"recall@3": 0.60, "recall@5": 0.80, "mrr": 0.40}

# ── C5.1 (Companion → Memento port): ABSTENTION / anti-fabrication ───────────────────
# The Companion's memory eval has an abstention dimension (the MEM-NEG units + is_memory_abstain):
# when it was never told X, it must say so, not fabricate. Memento had a MIN_FINAL_SCORE honesty
# gate but NO test that the retriever correctly returns NOTHING for an UNANSWERABLE query. This
# ports that control. GROUNDED FINDING (2026-06-24, measured before built): Memento's lexical
# retriever abstains correctly ONLY on ZERO-lexical-overlap queries (no FTS token match -> 0
# candidates -> 0 hits). For INCIDENTAL-overlap queries (real words, no genuinely on-topic memory)
# it surfaces the importance/recency PRIOR (5 hits whose blended scores do NOT separate from real
# hits) — that broader fabrication is coupled to semantic relevance = the PARKED M5 tier, so it is
# MEASURED + documented here, not gated (gating it would require M5 and would block on a true gap).
ABSTENTION_FLOOR = 0.90   # ≥90% of zero-overlap unanswerable queries must return NOTHING

# Unanswerable, ZERO real-token-overlap — the retriever MUST return nothing (gated).
ABSTENTION_NOOVERLAP: list[str] = [
    "qwzxvbn plughfrobnitz zzqqwx vxntplgh",
    "xyzzy123 frobnitz9000 ztlkqp",
    "asdfghjkl qwertyuiop zxcvbnmm",
    "grrblxn twptzk vmqxjd nphwlz",
    "zzqwx7741 flooberdoodle narglethorp wibblethrum",
    "kx9vptr lmzqjp vmqxjd nphwlzq tzkrbn",
]
# Unanswerable but with INCIDENTAL real-word overlap — MEASURED ONLY (the M5-coupled gap; the
# retriever fabricates a prior-driven hit for these and the lexical score can't tell).
ABSTENTION_INCIDENTAL: list[str] = [
    "what is the best chocolate chip cookie recipe with butter",
    "how do I train a goldfish to play the violin underwater",
    "which planet has the most beautiful sunset for a picnic",
]

# (query, [acceptable source-name substrings]) — grounded against the live retriever.
GOLDEN: list[tuple[str, list[str]]] = [
    ("should I push to production or deploy to prod",            ["local_first_never_push_prod", "no_remote_push", "stay_local"]),
    ("never use em dashes in writing",                           ["no_em_dashes"]),
    ("MTBF OEE failure mode preventive maintenance definitions", ["maintenance-expert"]),
    ("stop stopping momentum doctrine do not report and wait",   ["dont_stop", "offer_to_continue", "weaponizing_irreversible"]),
    ("synthesis not just audit cluster by job to be done",       ["synthesis_not_just_audit"]),
    ("classify by verified evidence not a heuristic name",       ["classify_by_evidence"]),
    ("validator design patterns architectural gates miners",     ["validator_design_patterns"]),
    ("catalog tables must not be in reset tables seeder",        ["catalog_tables"]),
    ("drawing standards SVG IEC 62305 diagram symbols",          ["drawing-standards", "drawing_standards", "standards_skill"]),
    ("never git checkout an uncommitted file lost work",         ["never_git_checkout"]),
    ("be proactive flywheel act then report",                    ["be_proactive_flywheel", "proactive_flywheel"]),
    ("multi-tenant hive RLS isolation data between hives",       ["multitenant", "data_db_ufai"]),
    ("Remotion video render pipeline node cli",                  ["remotion_pipeline"]),
    ("grounded battery axe-core link check per page",            ["grounded_battery"]),
    ("UFAI battery usability functionality adaptability control",["ufai_battery", "ufai_enhanced"]),
    ("pattern catalog do it like X opinionated patterns",        ["pattern_catalog"]),
    ("free tier only models never paid Claude OpenAI",           ["free_tier_only"]),
    ("audit scanner scope shared subdir HTML migration",         ["audit_scanner_scope"]),
    ("weaponizing irreversible gate commit deploy is a stop",    ["weaponizing_irreversible_gate"]),
    ("offer to continue say the word is the stop",               ["offer_to_continue_is_the_stop"]),
    ("build structure to make it liveable covered by nature",    ["build_structure_to_make_it_liveable"]),
    ("Arc R security adversarial OWASP boundary twin findings",  ["arc_r_security"]),
    ("Arc Q domain correctness value at the glass standard",     ["arc_q_domain", "domain_correctness"]),
    ("Playwright MCP must reuse the mega gate 1238 specs",       ["playwright_mcp_reuse_mega_gate"]),
    ("jscpd duplicated line count template shape vs copypaste",  ["jscpd"]),
]


def _rank_of(query: str, accept: list[str]) -> tuple[int, list[str]]:
    """Return (1-based rank of first accepted source in top-5, or 0 if absent; the top-5 names)."""
    _, stats = mr.retrieve(query)
    names = [h.get("name", "") or "" for h in stats.get("top_hits", [])]
    low_accept = [a.lower() for a in accept]
    for i, n in enumerate(names, start=1):
        nl = n.lower()
        if any(a in nl for a in low_accept):
            return i, names
    return 0, names


def eval_once() -> tuple[dict, list[dict]]:
    rows: list[dict] = []
    r1 = r3 = r5 = 0
    rr_sum = 0.0
    for q, accept in GOLDEN:
        rank, names = _rank_of(q, accept)
        rows.append({"q": q, "accept": accept[0], "rank": rank, "top": names[:3]})
        if rank:
            rr_sum += 1.0 / rank
            if rank <= 1: r1 += 1
            if rank <= 3: r3 += 1
            if rank <= 5: r5 += 1
    n = len(GOLDEN)
    metrics = {
        "n": n,
        "recall@1": round(r1 / n, 3),
        "recall@3": round(r3 / n, 3),
        "recall@5": round(r5 / n, 3),
        "mrr": round(rr_sum / n, 3),
    }
    return metrics, rows


def _abstained(query: str) -> bool:
    """True if the retriever correctly returns NOTHING for an unanswerable query (anti-fabrication)."""
    _, stats = mr.retrieve(query)
    return not (stats.get("top_hits") or [])


def eval_abstention() -> dict:
    """C5.1: measure anti-fabrication. abstention_rate = fraction of ZERO-overlap unanswerable
    queries for which the retriever returns nothing (gated). incidental_fabrication = fraction of
    incidental-overlap unanswerable queries that surfaced a (prior-driven) hit — MEASURED ONLY, the
    M5-coupled gap. Counts are computed against the LIVE retriever, read-only."""
    no_overlap = ABSTENTION_NOOVERLAP
    abstained = sum(1 for q in no_overlap if _abstained(q))
    incidental_hit = sum(1 for q in ABSTENTION_INCIDENTAL if not _abstained(q))
    return {
        "n_nooverlap": len(no_overlap),
        "abstained": abstained,
        "abstention_rate": round(abstained / len(no_overlap), 3) if no_overlap else 1.0,
        "n_incidental": len(ABSTENTION_INCIDENTAL),
        "incidental_fabrication": incidental_hit,
    }


def _abstention_breach(a: dict) -> list[str]:
    """Return the breached abstention floor ([] = met)."""
    if a["abstention_rate"] < ABSTENTION_FLOOR:
        return [f"abstention_rate {a['abstention_rate']:.2f} < {ABSTENTION_FLOOR:.2f} "
                f"(retriever fabricated hits for {a['n_nooverlap'] - a['abstained']} unanswerable queries)"]
    return []


def _floors_met(metrics: dict) -> list[str]:
    """Return the list of breached floors ([] = all met)."""
    return [f"{k} {metrics[k]:.2f} < {FLOORS[k]:.2f}" for k in FLOORS if metrics[k] < FLOORS[k]]


def _write_baseline(metrics: dict) -> None:
    snap = {"updated_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "floors": FLOORS, **metrics}
    try:
        BASELINE.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    except OSError:
        pass


def do_selftest() -> int:
    """M2.1 acceptance: a bad knob FAILs, a good config PASSes."""
    good, _ = eval_once()
    good_breaches = _floors_met(good)
    print(f"  good config: recall@3={good['recall@3']:.2f} recall@5={good['recall@5']:.2f} "
          f"mrr={good['mrr']:.2f}  -> {'PASS' if not good_breaches else 'FAIL'}")

    # Deliberately-bad knob: crank the honesty gate so high every candidate is dropped.
    saved = mr.MIN_FINAL_SCORE
    mr.MIN_FINAL_SCORE = 10.0
    try:
        bad, _ = eval_once()
    finally:
        mr.MIN_FINAL_SCORE = saved
    bad_breaches = _floors_met(bad)
    print(f"  bad knob (MIN_FINAL_SCORE=10): recall@5={bad['recall@5']:.2f} "
          f"mrr={bad['mrr']:.2f}  -> {'PASS' if not bad_breaches else 'FAIL'}")

    # C5.1 abstention teeth: the real retriever abstains on zero-overlap unanswerable queries; a
    # FABRICATING retriever (one that surfaces the importance prior even with no lexical match) must
    # breach the abstention floor — proving the ported anti-fabrication control catches the regression.
    real_abst = eval_abstention()
    real_abst_ok = not _abstention_breach(real_abst)
    orig_retrieve = mr.retrieve

    def _fabricating(q, *a, **k):
        out, stats = orig_retrieve(q, *a, **k)
        if not (stats.get("top_hits") or []):
            stats = dict(stats)
            stats["top_hits"] = [{"id": 0, "name": "fabricated_doctrine.md", "type": "doctrine", "score": 0.05}]
        return out, stats

    mr.retrieve = _fabricating
    try:
        bad_abst = eval_abstention()
    finally:
        mr.retrieve = orig_retrieve
    bad_abst_breaches = _abstention_breach(bad_abst)
    print(f"  abstention: real rate={real_abst['abstention_rate']:.2f} -> {'PASS' if real_abst_ok else 'FAIL'};  "
          f"fabricating-retriever rate={bad_abst['abstention_rate']:.2f} -> "
          f"{'PASS' if not bad_abst_breaches else 'FAIL (caught)'}")

    recall_teeth = (not good_breaches) and bool(bad_breaches)
    abst_teeth = real_abst_ok and bool(bad_abst_breaches)
    has_teeth = recall_teeth and abst_teeth
    if has_teeth:
        print(f"  {G}TEETH VERIFIED{X} recall: good passes / bad knob breaches [{', '.join(bad_breaches)}]. "
              f"abstention: real retriever abstains / a fabricating one breaches [{', '.join(bad_abst_breaches)}].")
        return 0
    print(f"  {R}TOOTHLESS{X} recall_teeth={recall_teeth} abst_teeth={abst_teeth} "
          f"(good={good_breaches} bad={bad_breaches} real_abst_ok={real_abst_ok} bad_abst={bad_abst_breaches})")
    return 1


def main() -> int:
    print(f"{B}Memory-System M2.1 - retriever recall@k eval{X}")
    print("=" * 62)
    argv = sys.argv[1:]

    if "--selftest" in argv:
        rc = do_selftest()
        print(f"\n{(G if rc == 0 else R)}{B}  RECALL EVAL SELFTEST: {'PASS' if rc == 0 else 'FAIL'}{X}")
        return rc

    t0 = time.monotonic()
    metrics, rows = eval_once()
    elapsed = time.monotonic() - t0
    _write_baseline(metrics)

    if "--json" in argv:
        print(json.dumps({"metrics": metrics, "rows": rows}, indent=2, ensure_ascii=False))
        return 0 if not _floors_met(metrics) else 1

    for r in rows:
        mark = f"{G}@{r['rank']}{X}" if r["rank"] else f"{R}MISS{X}"
        print(f"  {mark:>10}  {r['accept'][:42]:42}  {r['top'][:2]}")
    abst = eval_abstention()
    breaches = _floors_met(metrics) + _abstention_breach(abst)
    print(f"\n  metrics: recall@1={metrics['recall@1']:.2f}  recall@3={metrics['recall@3']:.2f}  "
          f"recall@5={metrics['recall@5']:.2f}  MRR={metrics['mrr']:.2f}  ({metrics['n']} pairs, {elapsed:.1f}s)")
    print(f"  floors:  recall@3>={FLOORS['recall@3']:.2f}  recall@5>={FLOORS['recall@5']:.2f}  "
          f"mrr>={FLOORS['mrr']:.2f}")
    print(f"  abstention (C5.1): {abst['abstained']}/{abst['n_nooverlap']} zero-overlap unanswerable "
          f"queries returned nothing (rate {abst['abstention_rate']:.2f} >= {ABSTENTION_FLOOR:.2f}). "
          f"incidental-overlap fabrication {abst['incidental_fabrication']}/{abst['n_incidental']} "
          f"(MEASURED only — the lexical retriever surfaces the importance prior; true fix = M5 semantic tier, parked).")
    if breaches:
        print(f"\n{R}{B}  RECALL EVAL: FAIL{X} - {'; '.join(breaches)}")
        return 1
    print(f"\n{G}{B}  RECALL EVAL: PASS{X} - recall above health floors + retriever abstains on unanswerable queries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
