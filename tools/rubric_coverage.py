#!/usr/bin/env python3
"""rubric_coverage.py — the UNIFIED 63-dim UFAI coverage board (UR-P4 tail).

The single-page family sweep (family_rubric_scoreboard.json) measures the 61 single-page dims.
The two CROSS-PAGE dims (S2 shared-chrome parity, S3 card-primitive parity) are owned by a
different instrument (survey_component_consistency.py -> component_consistency_corpus.json), so
the family board alone reads 61/63. This tool AGGREGATES all three sources into ONE 63-dim
coverage view keyed by the spec (ufai-rubric-spec.json), so "wire S2/S3 into the board" is done
at the reporting layer — no expensive 32-page re-sweep.

  S3 = fraction of corpus pages whose canonical card primitive has 0 missing_required parts.
  S2 = fraction of corpus pages carrying the shared card primitive at all (a proxy for shared-
       chrome parity; the authoritative nav/footer parity is enforced by codebase-integrity).

  python tools/rubric_coverage.py            # print + write rubric_coverage.json
  python tools/rubric_coverage.py --check    # exit 1 if the board is missing dims (gate-friendly)
  python tools/rubric_coverage.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "ufai-rubric-spec.json"
BOARD = REPO / "family_rubric_scoreboard.json"
CORPUS = REPO / "component_consistency_corpus.json"
OUT = REPO / "rubric_coverage.json"

CANONICAL_CARD = "simple-card"   # the exemplar primitive (Hive/Home design system)


def spec_dims(spec: dict) -> dict:
    import re
    return {k: v for k, v in spec.items() if k != "_meta" and re.fullmatch(r"[A-Z][0-9]", k)}


def cross_page_s3(corpus: dict) -> dict:
    """S3 = card-primitive parity from the AUTHORITATIVE corpus signal: modal-shape conformance
    across the canonical primitives (modal_count / instances), plus the flagged candidate defects.

    NOTE (2026-07-21): an earlier heuristic counted 'page lacks a non-empty .simple-card' as a miss
    and read a false ~59%. That conflates the multi-primitive reality (pages legitimately use
    .sum-card / other primitives) with a real defect. The real parity signal is the corpus's own
    modal conformance + its `candidates` (e.g. hive's .simple-card missing .sc-label)."""
    groups = corpus.get("groups") or {}
    prims = groups.get("primitives") or {}
    inst = modal = 0
    for _, info in prims.items():
        if isinstance(info, dict):
            inst += int(info.get("instances") or 0)
            modal += int(info.get("modal_count") or 0)
    cands = groups.get("candidates") or []
    pages = corpus.get("corpus") or {}
    return {"S3": (round(100 * modal / inst) if inst else None),
            "instances": inst, "modal": modal, "candidates": len(cands),
            "pages": len(pages) if isinstance(pages, dict) else 0}


def build(spec: dict, board: dict, corpus: dict) -> dict:
    dims = spec_dims(spec)
    per = (board or {}).get("perDim") or {}
    cross = cross_page_s3(corpus or {})
    w2 = (per.get("W2") or {}).get("mean")   # shared-chrome parity, already measured per page
    try:   # journey-ux source-grep dims (J3/G5/S4) — validate_journey_ux_dims.py
        journey = json.loads((REPO / "journey_ux_dims_report.json").read_text(encoding="utf-8"))
    except Exception:
        journey = {}
    out_dims = {}
    for dim, entry in dims.items():
        owner = entry.get("owner", "rubric-lens")
        row = {"class": entry.get("class"), "title": entry.get("title"),
               "verdict": entry.get("verdict"), "owner": owner, "source": None, "pct": None}
        if dim in per:                       # single-page dim, from the family board
            row["source"] = "family_rubric_scoreboard.json"
            row["pct"] = per[dim].get("mean")
        elif dim == "S3":                    # cross-page card-primitive parity (corpus modal conformance)
            row["source"] = "component_consistency_corpus.json (modal conformance)"
            row["pct"] = cross.get("S3")
        elif dim == "S2":                    # cross-page shared-chrome parity (proxy: the W2 dim)
            row["source"] = "family board W2 (shared-chrome) + codebase-integrity nav-registry"
            row["pct"] = w2
        elif owner == "journey-validator":   # J3/G5/S4 — source-grep gate (validate_journey_ux_dims.py)
            row["source"] = "journey_ux_dims_report.json (validate_journey_ux_dims.py)"
            row["pct"] = (journey.get(dim) or {}).get("pct")
        elif (entry.get("verdict") or "").lower() == "planned":
            # DECLARED in the SSOT (prose + spec) but its detector is roadmap-pending — the experience-in-motion
            # journey dims (X/Y/G5/J3/S4, 2026-07-22). Accounted to the roadmap (not "no source"), pct stays
            # honestly null until the journey-PDDA builds its detector, then verdict flips measured + gets a board pct.
            row["source"] = "PDDA_UX_PAINPOINT_JOURNEY_ROADMAP.md (planned — detector pending)"
            row["pct"] = None
        out_dims[dim] = row
    measured = [d for d in out_dims.values() if d["pct"] is not None]
    accounted = [d for d in out_dims.values() if d["source"] is not None]
    summary = {"dims_total": len(dims), "dims_accounted": len(accounted),
               "dims_with_pct": len(measured),
               "board_pages": ((board or {}).get("summary") or {}).get("measuredPages"),
               "board_mean": ((board or {}).get("summary") or {}).get("mean"),
               "s2_shared_chrome": w2, "cross_page": cross}
    return {"summary": summary, "dims": out_dims}


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    for f in (SPEC, BOARD):
        if not f.exists():
            print(f"FAIL rubric-coverage: missing {f}")
            return 1
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8")) if CORPUS.exists() else {}
    res = build(spec, board, corpus)
    s = res["summary"]
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    cp = s["cross_page"]
    print(f"rubric-coverage: {s['dims_accounted']}/{s['dims_total']} dims accounted "
          f"({s['dims_with_pct']} with a measured %) · board {s['board_pages']} pages, mean {s['board_mean']} "
          f"· S3 card-parity {cp.get('S3')}% ({cp.get('modal')}/{cp.get('instances')} modal, "
          f"{cp.get('candidates')} candidate defect(s)) · S2 shared-chrome {s['s2_shared_chrome']}% "
          f"· wrote {OUT.name}")
    if "--check" in argv:
        missing = s["dims_total"] - s["dims_accounted"]
        if missing:
            unaccounted = [k for k, v in res["dims"].items() if v["source"] is None]
            print(f"FAIL rubric-coverage: {missing} dim(s) have no measurement source: {unaccounted}")
            return 1
        print("PASS rubric-coverage — all 63 dims accounted across the family board + corpus.")
    return 0


def self_test() -> int:
    fails = []
    spec = {"_meta": {}, "A1": {"class": "A", "owner": "rubric-lens"},
            "S2": {"class": "S", "owner": "family-sweep"}, "S3": {"class": "S", "owner": "family-sweep"}}
    board = {"summary": {"measuredPages": 2, "mean": 100},
             "perDim": {"A1": {"mean": 95}, "W2": {"mean": 88}}}
    corpus = {"groups": {"primitives": {"simple-card": {"instances": 4, "modal_count": 3}},
                         "candidates": [{"page": "hive"}]},
              "corpus": {"p1": {}, "p2": {}}}
    res = build(spec, board, corpus)
    if res["summary"]["dims_accounted"] != 3:
        fails.append(f"all 3 dims should be accounted, got {res['summary']['dims_accounted']}")
    if res["dims"]["A1"]["pct"] != 95:
        fails.append(f"A1 should read 95 from the board, got {res['dims']['A1']['pct']}")
    if res["dims"]["S3"]["pct"] != 75:   # modal conformance 3/4
        fails.append(f"S3 should be 75 (3/4 modal), got {res['dims']['S3']['pct']}")
    if res["dims"]["S2"]["pct"] != 88:   # shared-chrome from the W2 dim
        fails.append(f"S2 should be 88 (from W2), got {res['dims']['S2']['pct']}")
    if res["summary"]["cross_page"]["candidates"] != 1:
        fails.append(f"should surface 1 candidate defect, got {res['summary']['cross_page']['candidates']}")
    if fails:
        print("FAIL rubric_coverage self-test:")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS rubric_coverage self-test (board + corpus aggregation, S2/S3 from primitives)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
