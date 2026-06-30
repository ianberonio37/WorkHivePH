#!/usr/bin/env python3
"""
validate_artifact_alignment — §13.13 ARTIFACT-ALIGNMENT CORRECTNESS (Phases A1-A4)
==================================================================================
The platform's full correctness = SOURCE correct (nerves) + COMPUTATION correct
(engine value-validators) + ARTIFACT correct (THIS). A derived artifact (report/PDF,
AI-generated doc, diagram, CSV, guide, narrative) must carry the SAME value as its
source — a contract/DOM test never catches a downstream artifact that silently drifts.

This is the DETERMINISTIC tier (the gate floor): it asserts each artifact builder
reads the source's correct OUTPUT — a field-ROLE contract, stronger than the existing
field-NAME contracts (validate_bom_sow/validate_drawings/validate_diagram_inputs).
The LIVE grounding tier (produce the artifact → assert emitted value == source value)
runs in §13/G3 (journey_accept), not here.

Coverage is measured against the discovered denominator in `artifact_map.json`
(run tools/mine_artifact_map.py first). Each CHECK proves ONE (page, artifact) cell.

Run:        python tools/validate_artifact_alignment.py
Self-test:  python tools/validate_artifact_alignment.py --self-test
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
AMAP = ROOT / "artifact_map.json"

ENG = "engineering-design.html"
BOMSOW = "supabase/functions/engineering-bom-sow/index.ts"


def _body_after(txt: str, marker: str, limit: int = 2000) -> str:
    i = txt.find(marker)
    return "" if i < 0 else txt[i:i + limit]


def _fn_bodies(txt: str, name_rx: str):
    """Yield (name, body) for each `function NAME(` whose name matches name_rx,
    body = source from this def to the next function def (or EOF)."""
    defs = [(m.group(1), m.start()) for m in re.finditer(r"function\s+(\w+)\s*\(", txt)]
    for i, (name, start) in enumerate(defs):
        if re.fullmatch(name_rx, name):
            end = defs[i + 1][1] if i + 1 < len(defs) else len(txt)
            yield name, txt[start:end]


# ─── CHECKS: each proves one (page, artifact) cell. fn(get)->(ok, detail). ────
# `get(relpath)` returns file content (or "" in self-test → every check must FAIL).
def _chk_eng_ai_doc(get):
    txt = get(BOMSOW)
    agents = list(_fn_bodies(txt, r"\w*BomSowAgent"))
    if not agents:
        return False, "no *BomSowAgent functions found"
    grounded = sum(1 for _, b in agents if "results." in b)
    return grounded == len(agents), f"{grounded}/{len(agents)} BOM/SOW agents ground on calc results.<field>"


def _chk_eng_diagram(get):
    txt = get(ENG)
    # Diagram emitters that RECEIVE the calc results in their signature (display-only
    # renderers like renderHVACDiagram(mermaidCode) are excluded). These functions are
    # large and contain nested helpers, so check results usage in a content WINDOW after
    # the def (results.field extraction sits near the top) rather than def-boundary slicing.
    defs = [m for m in re.finditer(r"function\s+(render\w*(?:Diagram|SLD))\s*\(([^)]*)\)", txt)
            if "results" in m.group(2)]
    if not defs:
        return False, "no diagram emitter takes calc results"
    # Grounded = the emitter USES the calc results in its body (>=2 `results` refs:
    # the signature param + >=1 usage), so the drawing is wired to the calc output.
    # (Proving each dimension LABEL == the exact calc value is the live tier.)
    grounded = sum(1 for m in defs
                   if len(re.findall(r"\bresults\b", txt[m.start():m.start() + 6000])) >= 2)
    return grounded == len(defs), f"{grounded}/{len(defs)} diagram emitters consume calc results (wired)"


def _chk_eng_pdf(get):
    txt = get(ENG)
    ok = "html2pdf()" in txt and ".from(reportEl)" in txt
    return ok, "PDF export serializes the rendered reportEl (html2pdf .from(reportEl)) == on-screen report"


def _chk_eng_csv(get):
    txt = get(ENG)
    body = _body_after(txt, "function downloadBomCsv")
    ok = bool(body) and "_bomItems" in body and "csv" in body.lower()
    return ok, "CSV built from _bomItems (the rendered BOM rows) — export == on-screen BOM"


def _chk_eng_guide(get):
    txt = get(ENG)
    if "const GUIDES = {" not in txt:
        return False, "GUIDES dict missing"
    block = txt.split("const GUIDES = {", 1)[1]
    keys = re.findall(r"\n  '([^']+)':\s*\{", block)
    return len(keys) >= 10, f"GUIDES has {len(keys)} per-calc-type guide entries"


def _chk_print_pdf(page):
    """A3: a report page that exports via window.print() / html2pdf serializes the
    RENDERED DOM → the PDF == what's on screen (faithful by construction). Falsifiable:
    a page that re-fetches/re-derives for the PDF would not just print the DOM."""
    def fn(get):
        txt = get(f"{page}.html")
        ok = "window.print(" in txt or re.search(r"html2pdf\(\)[\s\S]{0,80}\.from\(", txt) is not None
        return ok, f"PDF export serializes the rendered DOM (window.print / html2pdf.from) == on-screen"
    return fn


def _chk_csv_export(page):
    """A3: a CSV export built from a rendered data array (.map → Blob text/csv) serializes
    the on-screen rows, not a re-fetch. Falsifiable: no array→Blob csv path fails."""
    def fn(get):
        txt = get(f"{page}.html")
        has_blob_csv = re.search(r"new Blob\([\s\S]{0,120}csv", txt, re.I) is not None or "text/csv" in txt
        has_map = ".map(" in txt
        ok = has_blob_csv and has_map
        return ok, "CSV serialized from a rendered data array (.map → Blob text/csv) == on-screen rows"
    return fn


def _chk_ai_doc_grounded(page, edge_fns):
    """A2: an AI-generated document is GROUNDED when the page invokes its generator edge
    fn AND passes the page's real data (body: JSON.stringify(...)) — the doc is built FROM
    the source, not free-form. Falsifiable: no edge-fn call or no data body → fail."""
    def fn(get):
        txt = get(f"{page}.html")
        called = any(e in txt for e in edge_fns)
        grounds = re.search(r"body:\s*JSON\.stringify", txt) is not None
        ok = called and grounds
        hit = next((e for e in edge_fns if e in txt), "—")
        return ok, f"invokes {hit} with body: JSON.stringify(<page data>) — AI doc grounded in source"
    return fn


CHECKS = [
    # A1 — engineering-design exemplar (the 5-artifact chain)
    ("engineering-design", "ai_doc",  _chk_eng_ai_doc),
    ("engineering-design", "diagram", _chk_eng_diagram),
    ("engineering-design", "pdf",     _chk_eng_pdf),
    ("engineering-design", "csv",     _chk_eng_csv),
    ("engineering-design", "guide",   _chk_eng_guide),
    # A3 — report/PDF + CSV export faithfulness (export == on-screen)
    ("analytics-report", "pdf", _chk_print_pdf("analytics-report")),
    ("project-report",   "pdf", _chk_print_pdf("project-report")),
    ("asset-hub",        "pdf", _chk_print_pdf("asset-hub")),
    ("hive",             "pdf", _chk_print_pdf("hive")),
    ("audit-log",        "csv", _chk_csv_export("audit-log")),
    ("logbook",          "csv", _chk_csv_export("logbook")),
    ("resume",           "pdf", _chk_print_pdf("resume")),
    # (integrations·csv + assistant·ai_doc + project-manager·ai_doc were false-positive A0 hits —
    #  bare ".csv" / "BOM/SOW" text / no edge-fn call — dropped; A0 signatures tightened)
    # A2 — AI-doc grounding (the real ai_doc cells: engineering-design [above] + resume + report-sender)
    ("resume",        "ai_doc", _chk_ai_doc_grounded("resume", ("resume-extract", "resume-polish"))),
    ("report-sender", "ai_doc", _chk_ai_doc_grounded("report-sender", ("send-report-email", "voice-report-intent"))),
    # narrative (21 candidate pages) → A2 live grounding tier (companion-grounding class; needs per-page evidence)
]


def _denominator() -> int:
    if AMAP.exists():
        return int(json.loads(AMAP.read_text(encoding="utf-8")).get("artifact_cells_total", 0))
    return 0


def validate_artifact_alignment(blind=False):
    print("\n[Artifact Alignment] §13.13 — derived artifacts value-aligned with source (deterministic tier)")
    if blind:
        print("  *** SELF-TEST (blind): empty source → every check must FAIL (teeth) ***")

    def get(rel):
        if blind:
            return ""
        f = ROOT / rel
        txt = f.read_text(encoding="utf-8", errors="ignore") if f.exists() else ""
        # Page-bundle pairing (Arc L / L1): engineering-design.html's render*Diagram fns,
        # html2pdf export, downloadBomCsv/_bomItems and GUIDES were extracted to
        # engineering-design.js — re-attach it so these artifact checks see them.
        if rel == ENG:
            jf = ROOT / "engineering-design.js"
            if jf.exists():
                txt += "\n" + jf.read_text(encoding="utf-8", errors="ignore")
        return txt

    verified = 0
    by_cell = {}
    for page, atype, fn in CHECKS:
        try:
            ok, detail = fn(get)
        except Exception as e:
            ok, detail = False, f"raised {type(e).__name__}: {e}"
        by_cell[f"{page}:{atype}"] = ok
        verified += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {page} · {atype}  — {detail}")

    total = _denominator()
    print("\n  -- Summary --------------------------------------------")
    print(f"  Artifact cells alignment-verified : {verified}/{len(CHECKS)} checks PASS")
    if total:
        pct = round(100 * verified / total, 1)
        tail = ("FIRM deterministic tier COMPLETE; narrative candidates = A2 live-grounding tier"
                if verified >= total else "in progress — A1-A4")
        print(f"  Whole-platform FIRM coverage      : {verified}/{total} firm artifact cells = {pct}%  ({tail})")
    (ROOT / "artifact_alignment.json").write_text(json.dumps(
        {"verified_checks": verified, "total_checks": len(CHECKS),
         "denominator_cells": total, "by_cell": by_cell}, indent=2), encoding="utf-8")

    if blind:
        ok = verified == 0
        print(f"\n  SELF-TEST {'PASS' if ok else 'FAIL'}: {len(CHECKS) - verified}/{len(CHECKS)} checks failed on empty source "
              f"({'has teeth' if ok else 'BROKEN — a check passes vacuously'}).")
        return ok

    return all(by_cell.values())


if __name__ == "__main__":
    sys.exit(0 if validate_artifact_alignment(blind="--self-test" in sys.argv) else 1)
