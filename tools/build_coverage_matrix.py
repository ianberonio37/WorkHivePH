#!/usr/bin/env python3
"""build_coverage_matrix.py — Phase 1 of the P-program: the page x layer GAP MAP.

Ian's P-program is "issue-driven, matrix-guided". This builds the matrix that makes
"comprehensive" measurable instead of asserted: every real page x every layer that page actually
rests on, annotated with the coverage that already exists, so the deepwalk can be aimed at the
cells nothing has touched rather than re-walking what 725 trajectories already cover.

THREE DESIGN RULES, each one a lesson already paid for:

1. **APPLICABILITY IS DERIVED FROM THE PAGE'S OWN SOURCE, never assumed.** A page that never calls
   an edge function has no API layer to cover, and inventing that cell would manufacture a gap that
   cannot be closed. Each layer carries a SIGNAL (a regex over the page's real text); no signal ->
   the cell is `n-a` with the signal named, so the judgement is falsifiable by reading the file.

2. **A CELL IS ONLY `covered` BY EVIDENCE THAT NAMES ITS LAYER.** The 725 legacy rows carry pages
   but no layer field, so crediting them to a layer would be inference dressed as measurement -
   the exact "a mirror guarantees agreement, not correctness" failure. They are recorded per PAGE
   as `legacy_page_rows` context and never promoted into a cell verdict. A gap map must
   over-report gaps; under-reporting is what makes a program declare itself finished early.

3. **PLATFORM-SCOPE LAYERS ARE NOT PER-PAGE CELLS.** Hosting, CI/CD and Load-Balancing are
   properties of the deployment, not of alert-hub.html. Fanning them across 156 pages would add
   468 vacuous cells that could only ever be filled by the same one piece of evidence - a
   denominator that flatters whoever divides by it. They are scored ONCE, from layer_depth.json.

  (default)   write substrate/reference/coverage_matrix.json + print the ranked gap list
  --check     exit 1 if the committed matrix differs from a fresh build (drift gate)
  --top N     how many ranked gaps to print (default 25)
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROSTER = ROOT / "substrate" / "reference" / "page_roster.json"
REGISTRY = ROOT / "trajectory_registry.json"
CRITIC = ROOT / "critic_registry.json"
BANKS = ROOT / "banks"
LAYER_DEPTH = ROOT / "layer_depth.json"
OUT = ROOT / "substrate" / "reference" / "coverage_matrix.json"

# ---- the 13 layers (COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §2) ----
# page-scoped: a signal in the page's own source decides applicability
PAGE_LAYERS = [
    ("F",  "Frontend",              None),                       # every page renders
    ("A",  "APIs & Backend Logic",  r"functions/v1/"),
    ("D",  "Database & Storage",    r"\.from\(|\.rpc\(|getDb\("),
    ("AU", "Auth & Permissions",    r"wh_hive_role|hive_id|signInWithPassword|auth\.getUser"),
    # ★SIGNALS ARE MEASURED, NOT GUESSED. The first draft used bare `offline` for AV and bare
    # `cache` for CA; counting them showed `offline` matching 127/156 pages and `cache` 23 — they
    # were hitting page COPY and prose ("works offline", "ai_cache" in a comment), not an
    # availability or caching surface. An over-broad signal inflates the applicable denominator and
    # manufactures gaps that cannot be closed, which is the same dishonesty as under-reporting,
    # pointed the other way. These are the narrowed forms, each hitting a real mechanism:
    #   AV  /health + navigator.onLine + the offline-fallback page itself  (~14, was 105)
    #   CA  serviceWorker + sw.js + caches.                                (~33)
    #   S   innerHTML + escHtml + auth_uid  (hive_id dropped: it is AU's signal, and reusing it
    #       here double-counted one fact as two layers' evidence)
    ("S",  "Security & RLS",        r"innerHTML|escHtml|auth_uid"),
    ("C",  "Cloud & Compute (LLM)", None),                       # set by AI-fn reference, below
    ("RL", "Rate Limiting",         None),                       # implied by an AI/edge call
    ("CA", "Caching & CDN",         r"serviceWorker|sw\.js|caches\."),
    ("L",  "Error Tracking & Logs", r"onerror|console\.error|trace_id|whTrace"),
    ("AV", "Availability & Recovery", r"/health|wh_health|navigator\.onLine|offline-fallback"),
]
# platform-scoped: scored once from layer_depth.json, never fanned across pages
PLATFORM_LAYERS = [("H", "Hosting & Deployment"), ("CI", "CI / CD"),
                   ("LB", "Load Balancing & Scaling")]

# an AI edge function reference makes the LLM + rate-limit layers applicable
AI_FN = re.compile(r"functions/v1/(ai-|voice-|agentic-|semantic-|tts-|resume-|assistant|"
                   r"[a-z-]*orchestrator|[a-z-]*rag[a-z-]*|[a-z-]*agent)", re.I)

LAYER_DEPTH_NAME = {
    "F": "Frontend", "A": "APIs & Backend Logic", "D": "Database & Storage",
    "AU": "Auth & Permissions", "S": "Security & RLS", "C": "Cloud & Compute",
    "H": "Hosting & Deployment", "CI": "CI/CD & Version Control",
}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def build() -> dict:
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["pages"]
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))["trajectories"]
    critic = {r["id"]: r for r in json.loads(CRITIC.read_text(encoding="utf-8"))["rows"]}
    banked = {p.name.replace("_live_mcp_bank.json", "") for p in BANKS.glob("*_live_mcp_bank.json")}

    # page -> trajectory rows naming it, split by whether the row declares LAYERS (the P program)
    by_page_layered: dict[str, list] = {}
    by_page_legacy: dict[str, list] = {}
    for t in reg:
        for pg in t.get("pages") or []:
            (by_page_layered if t.get("layers") else by_page_legacy).setdefault(pg, []).append(t)

    # ★A NEW ROSTER KIND IS A CONTRACT CHANGE — name the kinds this matrix is about, loudly
    # (2026-09-10). The roster gained `page` (about/, feedback/, privacy-policy/, terms-of-service/)
    # and `promo` (promo_posters/*) when its disk scan was widened from three hardcoded globs to the
    # deployed set. Iterating every row would have silently added twelve all-`gap` pages and aimed
    # the deepwalk at legal boilerplate and marketing artwork. Unknown kinds are REPORTED, never
    # defaulted into an existing kind's contract. See feedback_a_new_roster_kind_must_teach_every_consumer.
    MATRIX_KINDS = {"root", "learn", "tools"}
    skipped = sorted({e.get("kind", "?") for e in roster if e.get("kind") not in MATRIX_KINDS})
    if skipped:
        n = sum(1 for e in roster if e.get("kind") not in MATRIX_KINDS)
        print(f"  coverage-matrix scope: kinds {sorted(MATRIX_KINDS)} · skipping {n} page(s) of "
              f"kind {skipped} (not deepwalk subjects; declared, not silently dropped)")
    roster = [e for e in roster if e.get("kind") in MATRIX_KINDS]

    cells, pages_out = [], []
    for entry in roster:
        path = entry["path"]
        src = _read(ROOT / path)
        slug = Path(path).stem if not path.endswith("/index.html") else path.split("/")[-2]
        has_ai = bool(AI_FN.search(src))
        has_edge = "functions/v1/" in src
        layered = by_page_layered.get(path, [])
        legacy = by_page_legacy.get(path, [])
        page_cells = []

        for code, name, sig in PAGE_LAYERS:
            if code == "F":
                applicable, why = True, "every page renders"
            elif code == "C":
                applicable, why = has_ai, "references an AI edge function" if has_ai else \
                    "no AI edge function referenced"
            elif code == "RL":
                applicable, why = has_edge, "calls an edge function (rate-limited)" if has_edge \
                    else "calls no edge function"
            else:
                applicable = bool(re.search(sig, src)) if sig else False
                why = f"signal /{sig}/ {'found' if applicable else 'absent'}"

            # ONLY layer-naming evidence may fill a cell (design rule 2)
            ev = [t["id"] for t in layered if code in (t.get("layers") or [])]
            open_ev = [i for i in ev if (critic.get(i, {}).get("status") in ("pending", "walked"))
                       or next((t["status"] for t in layered if t["id"] == i), "") != "locked"]
            # ★TWO KINDS OF "NO LAYER EVIDENCE" — and collapsing them would misdirect the whole
            # deepwalk. Rule 2 refuses to credit the 725 legacy rows to a layer (they carry no
            # layer field, so it would be inference). But a cell on a page that a LOCKED legacy
            # trajectory actually walked is not in the same state as a cell on a page nothing has
            # ever opened: the first is very likely covered and merely unprovable at layer
            # granularity; the second is genuinely untouched. Reporting both as `gap` inflated
            # Frontend to 84 "gaps" that were mostly learn/tools pages the locked T/U waves had
            # already walked — aiming the program at work already done. `gap-legacy` keeps the
            # honest refusal to claim coverage while ranking below a true gap.
            locked_legacy = sum(1 for t in legacy if t.get("status") == "locked")
            if not applicable:
                verdict = "n-a"
            elif ev and not open_ev:
                verdict = "covered"
            elif ev:
                verdict = "partial"
            elif locked_legacy:
                verdict = "gap-legacy"
            else:
                verdict = "gap"
            # `locked_legacy_rows` is recorded EXPLICITLY because it is the one gap signal that
            # does NOT depend on the P program: it answers "did anything ever walk this page and
            # lock it?", which no amount of P-row seeding can change. The seeder steers its pools
            # on this field rather than on `verdict` — steering on `verdict` would be circular
            # (seeding a cell flips it out of `gap`, so the next run would un-steer and drop the
            # page again, oscillating instead of converging).
            c = {"page": path, "layer": code, "layer_name": name, "applicable": applicable,
                 "why": why, "verdict": verdict, "layer_evidence": ev,
                 "legacy_page_rows": len(legacy), "locked_legacy_rows": locked_legacy,
                 "banked": slug in banked}
            cells.append(c)
            page_cells.append(c)

        pages_out.append({
            "page": path, "kind": entry["kind"], "banked": slug in banked,
            "legacy_page_rows": len(legacy), "p_rows": len(layered),
            "applicable_layers": sum(1 for c in page_cells if c["applicable"]),
            "gaps": sum(1 for c in page_cells if c["verdict"] == "gap"),
            "gaps_legacy": sum(1 for c in page_cells if c["verdict"] == "gap-legacy"),
        })

    # platform layers, scored ONCE (design rule 3)
    depth = json.loads(LAYER_DEPTH.read_text(encoding="utf-8")) if LAYER_DEPTH.exists() else {}
    platform = []
    for code, name in PLATFORM_LAYERS:
        d = depth.get(LAYER_DEPTH_NAME.get(code, name)) or depth.get(name) or {}
        platform.append({"layer": code, "layer_name": name,
                         "coverage_pct": d.get("coverage_pct"),
                         "source": "layer_depth.json",
                         "scope": "platform — deliberately NOT fanned across pages"})

    v = Counter(c["verdict"] for c in cells)
    applicable = sum(1 for c in cells if c["applicable"])
    return {
        "_doc": ("Phase 1 gap map of the P-program: every real page x every layer that page's own "
                 "source shows it rests on. GENERATED by tools/build_coverage_matrix.py — never "
                 "hand-edited. `applicable` is derived from a named signal in the page text; a cell "
                 "is `covered` ONLY by evidence that names its layer (the 725 legacy rows carry no "
                 "layer field, so they are page-level context, never a cell verdict). Hosting/CI/LB "
                 "are platform-scope and scored once, not per page."),
        "generated_by": "tools/build_coverage_matrix.py",
        "pages": len(pages_out), "page_layers": len(PAGE_LAYERS),
        "cells_total": len(cells), "cells_applicable": applicable,
        "summary": {k: v[k] for k in ("covered", "partial", "gap", "gap-legacy", "n-a") if k in v},
        "coverage_pct_of_applicable": round(100 * v["covered"] / applicable, 1) if applicable else 0,
        "platform_layers": platform,
        "page_index": pages_out,
        "cells": cells,
    }


def ranked_gaps(m: dict, n: int) -> list:
    """Rank gaps so the deepwalk starts where the loss is largest, not alphabetically.

    Weight = layer criticality x page reach. Security/auth/data on a heavily-used authed page
    outranks an error-log gap on a static learn article — and saying so here beats re-deciding it
    ad hoc on every walk."""
    LW = {"S": 5, "AU": 5, "D": 4, "C": 4, "A": 3, "F": 3, "CA": 2, "AV": 2, "RL": 2, "L": 1}
    KW = {"root": 3, "tools": 2, "learn": 1}
    kind = {p["page"]: p["kind"] for p in m["page_index"]}
    gaps = [c for c in m["cells"] if c["verdict"] == "gap"]
    for g in gaps:
        g["_rank"] = LW.get(g["layer"], 1) * KW.get(kind.get(g["page"], "learn"), 1) \
            + (1 if g["banked"] else 0)
    gaps.sort(key=lambda g: (-g["_rank"], g["page"], g["layer"]))
    return gaps[:n]


def main() -> int:
    m = build()
    if "--check" in sys.argv:
        if not OUT.exists():
            print("coverage_matrix.json missing — run tools/build_coverage_matrix.py")
            return 1
        cur = json.loads(OUT.read_text(encoding="utf-8"))
        if json.dumps(cur, sort_keys=True) != json.dumps(m, sort_keys=True):
            print("COVERAGE MATRIX DRIFT — run: python tools/build_coverage_matrix.py")
            return 1
        print("coverage matrix current.")
        return 0
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    s = m["summary"]
    print(f"coverage_matrix.json — {m['pages']} pages x {m['page_layers']} page-scoped layers "
          f"= {m['cells_total']} cells ({m['cells_applicable']} applicable)")
    print("  " + " · ".join(f"{k} {v}" for k, v in s.items())
          + f" · covered {m['coverage_pct_of_applicable']}% of applicable")
    print("  platform layers (scored once, not per page): "
          + " · ".join(f"{p['layer']} {p['coverage_pct']}%" for p in m["platform_layers"]))
    n = 25
    if "--top" in sys.argv:
        try:
            n = int(sys.argv[sys.argv.index("--top") + 1])
        except (ValueError, IndexError):
            pass
    gaps = [c for c in m["cells"] if c["verdict"] == "gap"]
    print(f"\nRANKED GAPS (top {min(n, len(gaps))} of {len(gaps)}):")
    for g in ranked_gaps(m, n):
        print(f"  [{g['_rank']:>2}] {g['layer']:<3} {g['page']:<52} {g['why']}")
    by_layer = Counter(g["layer"] for g in gaps)
    print("\ngaps by layer: " + " · ".join(f"{k} {v}" for k, v in by_layer.most_common()))
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
