#!/usr/bin/env python3
"""
geo_sov_audit.py — SEO/AEO/GEO Arc, the AI Share-of-Voice scoreboard (Layer B's
measurement instrument; the AEO + GEO outcome metric).

WHY THIS IS THE SCOREBOARD: classic rank no longer predicts AI visibility (they
decoupled in 2026). The only honest measure of AEO/GEO is: on a FIXED prompt set,
how often do the live answer engines (ChatGPT, Perplexity, Gemini, Google AI
Overviews, Claude) CITE / MENTION / RECOMMEND WorkHive, and with what sentiment.

WHY MEASUREMENT IS LAYER B (manual/keyed, not auto-local): a valid SOV reading
needs the LIVE answer engines that do web-RAG — base LLMs (incl. our free-tier
chain) don't know a new brand from training and don't web-search, so they CANNOT
proxy it. So the operator (or a keyed API) runs the prompts; this tool supplies the
fixed bilingual prompt set, the recording template, and the scorecard + forward-only
baseline. That makes the off-site work (P4/P5) a measured curve, not a vibe.

CLI:
    python tools/geo_sov_audit.py --template [out.json]   # emit a blank results sheet to fill
    python tools/geo_sov_audit.py --score results.json     # compute the SOV scorecard (+ratchet)
    python tools/geo_sov_audit.py --self-test
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "prompt_audit_queries.json"
BASELINE = ROOT / "geo_sov_baseline.json"
TEMPLATE_OUT = ROOT / ".tmp" / "geo_sov_results_template.json"

ENGINES = ["chatgpt", "perplexity", "gemini", "ai_overviews", "claude"]
# A recorded cell per (query, engine): each field is the operator's observation.
CELL_FIELDS = {
    "cited": "bool — did the answer link/cite a workhiveph.com URL?",
    "mentioned": "bool — did the answer name WorkHive in the text?",
    "recommended": "bool — did the answer suggest WorkHive as an option?",
    "sentiment": "1 | 0 | -1  (positive / neutral-absent / negative)",
}


def load_queries() -> list[dict]:
    data = json.loads(QUERIES.read_text(encoding="utf-8"))
    return data.get("queries", [])


def emit_template(queries: list[dict]) -> dict:
    return {
        "_meta": {
            "instructions": "For each query, run it in each engine and fill cited/mentioned/recommended (true/false) + sentiment (1/0/-1). Then: python tools/geo_sov_audit.py --score <this file>.",
            "cell_fields": CELL_FIELDS,
            "engines": ENGINES,
            "query_count": len(queries),
        },
        "results": {
            q["id"]: {eng: {"cited": None, "mentioned": None, "recommended": None, "sentiment": None}
                      for eng in ENGINES}
            for q in queries
        },
    }


def score(results: dict, queries: list[dict] | None = None) -> dict:
    """Compute the SOV scorecard from a (partially) filled results sheet.
    Unfilled (None) cells are EXCLUDED from rates (so a partial audit still scores
    what was measured) — `n` reports how many cells fed each rate."""
    queries = queries if queries is not None else load_queries()
    qid_lang = {q["id"]: q.get("lang", "en") for q in queries}

    def rate(cells, field):
        vals = [c.get(field) for c in cells if c.get(field) is not None]
        truthy = sum(1 for v in vals if v is True)
        return (round(100 * truthy / len(vals), 1) if vals else None), len(vals)

    per_engine = {}
    all_cells, tl_cells = [], []
    for eng in ENGINES:
        cells = [results["results"][qid][eng] for qid in results["results"] if eng in results["results"][qid]]
        all_cells += cells
        tl_cells += [results["results"][qid][eng] for qid in results["results"]
                     if eng in results["results"][qid] and qid_lang.get(qid) == "tl"]
        cr, ncr = rate(cells, "cited")
        mr, nmr = rate(cells, "mentioned")
        rr, nrr = rate(cells, "recommended")
        svals = [c["sentiment"] for c in cells if c.get("sentiment") is not None]
        per_engine[eng] = {
            "cited_rate": cr, "mention_rate": mr, "recommend_rate": rr,
            "sentiment_avg": (round(sum(svals) / len(svals), 2) if svals else None),
            "n_measured": nmr,
        }

    def agg(cells, field):
        vals = [c.get(field) for c in cells if c.get(field) is not None]
        return (round(100 * sum(1 for v in vals if v is True) / len(vals), 1) if vals else 0.0)

    # SOV (the headline) = aggregate MENTION rate across all measured cells.
    scorecard = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queries_total": len(queries),
        "sov_pct": agg(all_cells, "mentioned"),
        "citation_rate": agg(all_cells, "cited"),
        "recommendation_rate": agg(all_cells, "recommended"),
        "taglish_sov_pct": agg(tl_cells, "mentioned"),
        "cells_measured": sum(1 for c in all_cells if any(c.get(f) is not None for f in ("cited", "mentioned", "recommended"))),
        "cells_total": len(all_cells),
        "per_engine": per_engine,
    }
    return scorecard


def _ratchet(scorecard: dict) -> dict:
    """Forward-only: record the best SOV seen so a later audit that DROPS below it
    is a flagged regression (the off-site curve should climb, not slide)."""
    prior = {}
    if BASELINE.exists():
        try:
            prior = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
    best = max(prior.get("best_sov_pct", 0.0), scorecard["sov_pct"])
    regressed = scorecard["sov_pct"] < prior.get("best_sov_pct", 0.0)
    BASELINE.write_text(json.dumps({
        "best_sov_pct": best,
        "last_sov_pct": scorecard["sov_pct"],
        "last_run": scorecard["generated_at"],
        "history": (prior.get("history", []) + [{"at": scorecard["generated_at"], "sov_pct": scorecard["sov_pct"]}])[-24:],
    }, indent=2), encoding="utf-8")
    return {"best_sov_pct": best, "regressed": regressed}


def self_test() -> int:
    fails = 0

    def ck(cond, msg):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1mgeo_sov_audit.py --self-test\033[0m")
    print("=" * 55)

    qs = load_queries()
    ck(len(qs) >= 30, f"prompt set is sized for SOV ({len(qs)} queries)")
    ck(any(q.get("lang") == "tl" for q in qs), "prompt set is bilingual (has Taglish queries)")

    tmpl = emit_template(qs)
    ck(set(next(iter(tmpl["results"].values())).keys()) == set(ENGINES), "template has a cell per engine")

    # Synthetic results: 2 queries (1 en, 1 tl), engine cells set so the math is known.
    synth_q = [{"id": "q_en", "lang": "en"}, {"id": "q_tl", "lang": "tl"}]
    res = {"results": {
        "q_en": {e: {"cited": e == "perplexity", "mentioned": e in ("perplexity", "chatgpt"),
                     "recommended": e == "perplexity", "sentiment": 1} for e in ENGINES},
        "q_tl": {e: {"cited": False, "mentioned": e == "chatgpt", "recommended": False, "sentiment": 0} for e in ENGINES},
    }}
    sc = score(res, synth_q)
    # mentions: q_en → perplexity+chatgpt (2), q_tl → chatgpt (1) = 3 of 10 cells = 30%
    ck(sc["sov_pct"] == 30.0, f"SOV = aggregate mention rate (got {sc['sov_pct']}, expected 30.0)")
    # taglish: q_tl chatgpt mentioned (1) of 5 = 20%
    ck(sc["taglish_sov_pct"] == 20.0, f"taglish SOV computed separately (got {sc['taglish_sov_pct']}, expected 20.0)")
    ck(sc["per_engine"]["perplexity"]["cited_rate"] == 50.0, "per-engine cited rate (perplexity 1/2 = 50%)")
    ck(sc["citation_rate"] == 10.0, f"citation rate aggregate (1 of 10 = 10%, got {sc['citation_rate']})")

    print("=" * 55)
    print("\033[92m  self-test PASS\033[0m\n" if not fails else f"\033[91m  self-test FAIL — {fails}\033[0m\n")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    qs = load_queries()
    if "--template" in argv:
        out = Path(argv[argv.index("--template") + 1]) if len(argv) > argv.index("--template") + 1 and not argv[argv.index("--template") + 1].startswith("--") else TEMPLATE_OUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(emit_template(qs), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"SOV results template ({len(qs)} queries x {len(ENGINES)} engines) -> {out}")
        print("Fill cited/mentioned/recommended/sentiment per cell, then: python tools/geo_sov_audit.py --score " + str(out))
        return 0
    if "--score" in argv:
        path = Path(argv[argv.index("--score") + 1])
        results = json.loads(path.read_text(encoding="utf-8"))
        sc = score(results, qs)
        ratchet = _ratchet(sc)
        (ROOT / "geo_sov_scorecard.json").write_text(json.dumps(sc, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  AI SHARE-OF-VOICE  ·  {sc['generated_at']}")
        print("  " + "=" * 56)
        print(f"    SOV (mention rate)   {sc['sov_pct']}%   [best {ratchet['best_sov_pct']}%]" + ("  REGRESSED" if ratchet["regressed"] else ""))
        print(f"    citation rate        {sc['citation_rate']}%")
        print(f"    recommendation rate  {sc['recommendation_rate']}%")
        print(f"    Taglish SOV          {sc['taglish_sov_pct']}%")
        print(f"    cells measured       {sc['cells_measured']}/{sc['cells_total']}")
        for e, v in sc["per_engine"].items():
            print(f"      {e:<13} mention={v['mention_rate']}  cite={v['cited_rate']}  rec={v['recommend_rate']}  sent={v['sentiment_avg']}  (n={v['n_measured']})")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
