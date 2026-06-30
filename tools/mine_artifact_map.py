#!/usr/bin/env python3
# audit-scope-allow: derived artifacts live on ROOT-level feature pages; learn/ subdirs are static
# SEO content with no artifacts, so a root *.html scan is the intended denominator (mirrors mine_narrative_surfaces).
"""
mine_artifact_map — §13.13 Phase A0: DISCOVER each feature page's derived artifacts.
=====================================================================================
The correctness arc's denominator. The platform's full correctness = source correct
(nerves) + computation correct (engine validators) + ARTIFACTS correct (this arc).
A derived artifact is any downstream output a page emits that must stay value-aligned
with its source: a PDF/report, an AI-generated document, a diagram, a CSV export, a
help guide, or an AI narrative. Half of them are AI-generated = the highest drift risk.

This scans each feature page's HTML (+ its known edge-fn artifact producers) for the
6 artifact-type signatures and emits a measured (page × artifact-type) matrix — the
denominator for "fully check the correctness of all my platform." It does NOT verify
alignment yet (that is Phases A1-A4); it establishes WHAT must be aligned, discovered
not hand-listed (the §13 "discover, don't enumerate" discipline).

Writes artifact_map.json + artifact_map.md + a console summary.
Run:  python tools/mine_artifact_map.py
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

# FIRM artifact-type signatures — SPECIFIC patterns (an edge-fn name, an export API),
# so a hit is evidence the page actually EMITS that artifact (not a stray word). These
# form the honest denominator. (csv tightened 2026-06-17: bare `\.csv` matched a static
# string on integrations = false positive — now requires a real export API.)
ARTIFACT_SIGNATURES = {
    "ai_doc":    r"engineering-bom-sow|resume-extract|resume-polish|send-report-email|voice-report-intent",
    "pdf":       r"html2pdf|/pdf\b|generatePDF|exportPDF|jspdf|downloadPDF|window\.print|printReport",
    "diagram":   r"render[A-Za-z]*Diagram|render[A-Za-z]*SLD|schemdraw|drawing-symbols|renderGantt",
    "csv":       r"exportCSV|toCSV|downloadCSV|download[A-Za-z]*Csv|export[A-Za-z]*Csv|text/csv|new Blob\([^)]*csv",
    "guide":     r"\bGUIDES\b|renderGuide|guide-content",
}
# CANDIDATE signature — a LOOSE pattern (the word appears) that does NOT prove an
# AI-generated narrative artifact exists. These need PER-PAGE EVIDENCE (A2) before
# counting — tracked separately, NEVER folded into the firm denominator (the §13
# "classify by evidence, not heuristic" lesson — a loose match is a candidate, not a fact).
NARRATIVE_CANDIDATE_SIGNATURE = r"generateNarrative|renderNarrative|ai.?summary|\bnarrative\b|\binsight|recommendation"
# AI-generated firm artifact classes = the highest drift risk (LLM output can hallucinate).
AI_GENERATED = {"ai_doc"}


def _feature_pages() -> list[str]:
    if LMAP.exists():
        pages = json.loads(LMAP.read_text(encoding="utf-8")).get("pages", {})
        if pages:
            return sorted(pages.keys())
    # Fallback: top-level html minus scaffolding
    skip = re.compile(r"test|debug|backup|^index$|^architecture$|^symbol-gallery$|^platform-health$", re.I)
    return sorted(p.stem for p in ROOT.glob("*.html") if not skip.search(p.stem))


def _scan(html: str) -> dict[str, bool]:
    return {atype: bool(re.search(rx, html, re.I)) for atype, rx in ARTIFACT_SIGNATURES.items()}


def main() -> int:
    pages = _feature_pages()
    per_page: dict[str, list[str]] = {}
    narrative_candidates: list[str] = []
    cells = 0
    ai_cells = 0
    type_counts = {a: 0 for a in ARTIFACT_SIGNATURES}

    for pg in pages:
        f = ROOT / f"{pg}.html"
        if not f.exists():
            continue
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        found = [a for a, hit in _scan(html).items() if hit]
        if found:
            per_page[pg] = found
            cells += len(found)
            ai_cells += sum(1 for a in found if a in AI_GENERATED)
            for a in found:
                type_counts[a] += 1
        # Narrative is a CANDIDATE only (loose match ≠ proof) — tracked separately.
        if re.search(NARRATIVE_CANDIDATE_SIGNATURE, html, re.I):
            narrative_candidates.append(pg)

    pages_with_artifacts = len(per_page)
    out = {
        "_doc": "§13.13 — derived-artifact discovery (the correctness-arc denominator). FIRM cells "
                "(specific-signature, evidence-grade) are the denominator; narrative is a CANDIDATE "
                "bucket needing per-page A2 evidence (loose match ≠ proof — the evidence-not-heuristic rule).",
        "pages_scanned": len(pages),
        "pages_with_artifacts": pages_with_artifacts,
        "artifact_cells_total": cells,                 # FIRM denominator only
        "artifact_cells_ai_generated": ai_cells,
        "narrative_candidate_pages": sorted(narrative_candidates),
        "narrative_candidate_count": len(narrative_candidates),
        "by_type": type_counts,
        "by_page": per_page,
    }
    (ROOT / "artifact_map.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# §13.13 Artifact Map — A0 (discovered, the correctness-arc denominator)\n",
          f"- pages scanned: **{len(pages)}** · with FIRM artifacts: **{pages_with_artifacts}**",
          f"- **FIRM artifact cells (the denominator): {cells}** · of which AI-generated: **{ai_cells}**",
          f"- narrative candidates (loose match — need A2 per-page evidence, NOT in denominator): **{len(narrative_candidates)}** pages\n",
          "## By artifact type", "| Type | Pages | AI-gen? |", "|---|---|---|"]
    for a in ARTIFACT_SIGNATURES:
        md.append(f"| {a} | {type_counts[a]} | {'★ yes' if a in AI_GENERATED else ''} |")
    md += ["\n## By page", "| Page | Derived artifacts |", "|---|---|"]
    for pg in sorted(per_page):
        md.append(f"| {pg} | {', '.join(per_page[pg])} |")
    (ROOT / "artifact_map.md").write_text("\n".join(md), encoding="utf-8")

    print("=" * 70)
    print("  §13.13 A0 — ARTIFACT DISCOVERY (the whole-platform correctness denominator)")
    print("=" * 70)
    print(f"  pages scanned          : {len(pages)}")
    print(f"  pages with FIRM artifacts: {pages_with_artifacts}")
    print(f"  FIRM artifact cells    : {cells}   (evidence-grade signature — THE denominator)")
    print(f"  AI-generated (ai_doc)  : {ai_cells}   ★ highest drift risk (LLM output)")
    print(f"  narrative candidates   : {len(narrative_candidates)} pages   (loose match — need A2 per-page evidence, NOT counted)")
    print("  by firm type           : " + ", ".join(f"{a}={n}" for a, n in type_counts.items()))
    print(f"\n  wrote artifact_map.json + artifact_map.md")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
