#!/usr/bin/env python3
# audit-scope-allow: narrative surfaces are ROOT-level feature/app pages (analytics, predictive,
# shift-brain, …); learn/ subdirectories are static SEO content that render no AI prose, so a
# root *.html scan is the correct (and intended) denominator — subdirectory rglob would add noise.
"""
mine_narrative_surfaces — §13.16 A7.1 Phase 0: DISCOVER every page that renders AI prose.
==========================================================================================
The whole-platform analogue of the calc-grounding denominator (A6). A feature page that
renders LLM-generated PROSE (an analytics summary, a predictive narrative, a shift brief,
an intelligence report) must have the same grounding guarantee the companion already has:
**the prose cites ONLY true platform values — no fabricated number.** Today only `assistant`
(the companion) is grounding-checked; this mine establishes the HONEST denominator for the
other narrative pages so A7.1's grounding ratchet has a measured base.

Evidence-grade signature (the §13 "classify by evidence, not heuristic" rule — the loose
word "narrative" is only a CANDIDATE, see mine_artifact_map.py): a page is a narrative
surface iff it INVOKES a known narrative-emitting edge fn (`functions/v1/<fn>` or
`.invoke('<fn>')`) AND reads a prose field from that response into the DOM. Both signals
required → no stray-word false positives.

Writes narrative_surfaces.json + .md + a console summary. Verifies nothing yet (that is
A7.1.1 = validate_narrative_grounding.py); it answers WHICH pages owe a grounding check.
Run:  python tools/mine_narrative_surfaces.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LMAP = ROOT / "lineage_map.json"

# Edge fns that return LLM-generated prose a PAGE renders. Derived by evidence: each was
# confirmed to be invoked by ≥1 feature page (grep functions/v1/<fn>). Infrastructure/
# non-page producers (ai-gateway, ai-eval-runner, hierarchical-summarizer) excluded; the
# eng-design (engineering-bom-sow/calc-agent) + resume (resume-extract/polish) prose are
# grounding-covered by their OWN arcs (A4b / resume), so excluded here to avoid double-count.
NARRATIVE_EDGE_FNS = [
    "analytics-orchestrator", "intelligence-api", "intelligence-report",
    "ai-orchestrator", "amc-orchestrator", "asset-brain-query",
    "project-orchestrator", "parts-staging-recommender", "voice-journal-agent",
    "scheduled-agents",
]
# Prose fields a page injects into the DOM (the rendered-prose signal).
PROSE_FIELDS = r"\.(narrative|summary|insights?|recommendations?|analysis|briefing|explanation|advice|rationale|story)\b"
DOM_INJECT = r"innerHTML|textContent|insertAdjacent|\.html\(|\.text\("

# The companion (assistant) is ALREADY grounding-checked (companion gate) — record, don't re-owe.
ALREADY_GROUNDED = {"assistant"}


def _feature_pages() -> list[str]:
    if LMAP.exists():
        pages = json.loads(LMAP.read_text(encoding="utf-8")).get("pages", {})
        if pages:
            return sorted(pages.keys())
    skip = re.compile(r"test|debug|backup|^index$|^architecture$|^symbol-gallery$|^platform-health$", re.I)
    return sorted(p.stem for p in ROOT.glob("*.html") if not skip.search(p.stem))


def _fns_invoked(html: str) -> list[str]:
    hit = []
    for fn in NARRATIVE_EDGE_FNS:
        rx = re.compile(rf"functions/v1/{re.escape(fn)}\b|invoke\(\s*['\"]{re.escape(fn)}['\"]|['\"]{re.escape(fn)}['\"]")
        if rx.search(html):
            hit.append(fn)
    return hit


def main() -> int:
    pages = _feature_pages()
    surfaces: dict[str, dict] = {}     # page -> {fns, renders_prose}
    already: list[str] = []

    for pg in pages:
        f = ROOT / f"{pg}.html"
        if not f.exists():
            continue
        html = f.read_text(encoding="utf-8", errors="ignore")
        if pg in ALREADY_GROUNDED:
            already.append(pg)
            continue
        fns = _fns_invoked(html)
        if not fns:
            continue
        renders_prose = bool(re.search(PROSE_FIELDS, html, re.I) and re.search(DOM_INJECT, html))
        surfaces[pg] = {"edge_fns": fns, "renders_prose": renders_prose}

    # evidence tiers: STRONG = invokes a narrative fn AND renders prose; WEAK = invokes only.
    strong = {p: d for p, d in surfaces.items() if d["renders_prose"]}
    weak = {p: d for p, d in surfaces.items() if not d["renders_prose"]}

    out = {
        "_doc": "§13.16 A7.1 — AI-narrative surface discovery (the narrative-grounding denominator). "
                "A surface OWES a grounding check if it invokes a narrative-emitting edge fn AND renders "
                "the prose. STRONG = both signals; WEAK = invokes only (prose-render not detected — verify). "
                "Evidence-grade, not the loose word-match (the classify-by-evidence rule).",
        "pages_scanned": len(pages),
        "narrative_surfaces": len(surfaces),
        "strong_evidence": sorted(strong.keys()),
        "weak_evidence": sorted(weak.keys()),
        "already_grounded": sorted(already),
        "denominator_strong": len(strong),
        "by_page": surfaces,
    }
    (ROOT / "narrative_surfaces.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# §13.16 A7.1 — Narrative-Surface Map (discovered denominator)\n",
          f"- pages scanned: **{len(pages)}** · narrative surfaces (evidence-grade): **{len(surfaces)}**",
          f"- STRONG (invokes narrative fn **and** renders prose): **{len(strong)}** = the grounding denominator",
          f"- WEAK (invokes only — prose-render not auto-detected, verify): **{len(weak)}**",
          f"- already grounding-checked (companion): {', '.join(sorted(already)) or '—'}\n",
          "## Surfaces", "| Page | Edge fn(s) | Renders prose | Tier |", "|---|---|---|---|"]
    for pg in sorted(surfaces):
        d = surfaces[pg]
        tier = "STRONG" if d["renders_prose"] else "weak"
        md.append(f"| {pg} | {', '.join(d['edge_fns'])} | {'yes' if d['renders_prose'] else 'no'} | {tier} |")
    (ROOT / "narrative_surfaces.md").write_text("\n".join(md), encoding="utf-8")

    print("=" * 72)
    print("  §13.16 A7.1 Phase 0 — NARRATIVE-SURFACE DISCOVERY (grounding denominator)")
    print("=" * 72)
    print(f"  pages scanned         : {len(pages)}")
    print(f"  narrative surfaces    : {len(surfaces)}   (evidence-grade: invokes a narrative edge fn)")
    print(f"  STRONG (renders prose): {len(strong)}   ← the A7.1 grounding denominator")
    print(f"  weak (invokes only)   : {len(weak)}   (verify prose-render: {', '.join(sorted(weak)) or '—'})")
    print(f"  already grounded      : {', '.join(sorted(already)) or '—'} (companion gate)")
    print(f"\n  STRONG surfaces: {', '.join(sorted(strong)) or '—'}")
    print(f"  wrote narrative_surfaces.json + narrative_surfaces.md")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
