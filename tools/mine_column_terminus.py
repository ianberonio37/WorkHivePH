"""
mine_column_terminus -- DB-COLUMN TERMINUS map for the §13 "196 assertable-but-
value-unverified" capture fields (the last value-correctness spoke).
=========================================================================================
WHY THIS EXISTS
---------------
The Phantom Capture Auditor proved each of the 196 capture fields is CONSUMED (the page
reads it from the DOM), but it carries NO DB-column terminus -- so "the captured value is
value-correct" is unproven, AND we don't even know which fields persist at all. The §13
triage (triage_lineage_paths.py) deliberately refused to bucket them passthrough/structural
without that terminus evidence ([[feedback_classify_by_evidence_not_heuristic]]).

This miner supplies the missing evidence by STATIC ANALYSIS of each surface's own page JS:
for every capture field id, it finds where the id is referenced and classifies the field
by the CODE EVIDENCE around that reference -- never by the field's name.

THE HONEST BUCKETS (each carries evidence line numbers; never claims value-correct):
  • PERSISTED      -- the id is read directly into an insert/upsert/update payload object
                      ( `column: getElementById('<id>')...` ). Records table + column.
                      This is the value-VERIFIABLE set (a live round-trip can confirm it).
  • PERSISTED?     -- the id is read inside a function that also calls a persistence op, but
                      the exact `column:` mapping is indirected through a variable. Records
                      the candidate table(s); column needs one live confirm.
  • AI_EDGE        -- the id flows into a fetch()/functions.invoke() body (AI ask box, intent
                      text, JD matcher). Correctly NOT a DB column -- it is sent to an edge fn.
  • TRANSIENT_UI   -- the id is used only in a filter/search/sort/render context (`*-filter`,
                      `*-search`, input-event handlers, .includes/.filter). Correctly NOT
                      persisted -- a UI control, not a write.
  • NO_TERMINUS    -- the id is only cleared/reset (`.value=''`) or never reaches a persist /
                      fetch / filter. A genuine captured-but-DROPPED field = a REAL bug to
                      investigate (the value the user typed goes nowhere).

CRITICAL HONESTY RULE (the whole point): this is a TERMINUS map, NOT a value-verification.
PERSISTED means "this field lands in table.column" -- it does NOT mean the value is correct.
Value-correctness is the SECOND pass (live round-trip on the real DB), and only the PERSISTED
set is eligible for it. Buckets are reported with confidence; low-confidence rows are flagged
for live confirmation, never silently asserted.

Reads lineage_map.json (for the 196 field set) + each surface's <surface>.html.
Writes column_terminus.json + column_terminus.md + a console summary.
Hermetic (no network/DB). The live round-trip verification is a separate step.
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LMAP = ROOT / "lineage_map.json"

# Surfaces whose fields are the 196 (calc surface engineering-design is the SEPARATE 265
# class, value-verified by validate_calc_formula_accuracy.py — excluded here).
CALC_SURFACES = {"engineering-design"}
PERSISTED_SURFACES = {
    "resume", "dayplanner", "logbook", "pm-scheduler", "inventory", "marketplace",
    "asset-hub", "project-manager", "community", "integrations", "alert-hub",
    "skillmatrix", "voice-journal", "report-sender",
}
# surface -> page file (all resolve to <surface>.html, confirmed 2026-06-17)
SURFACE_FILE = {s: f"{s}.html" for s in PERSISTED_SURFACES}

PERSIST_RE = re.compile(r"\.from\(['\"]([\w.]+)['\"]\)\s*\.\s*(insert|upsert|update)\b")
EDGE_RE    = re.compile(r"\.functions\.invoke\(['\"]([\w-]+)['\"]|\bfetch\(")
FILTER_CTX = re.compile(r"\b(filter|search|sort|render|addEventListener\(['\"]input|"
                        r"\.includes\(|\.toLowerCase\(\)|querySelectorAll|textContent\s*=)\b", re.I)
RESET_RE   = re.compile(r"getElementById\(['\"]{ID}['\"]\)\.value\s*=")  # .format(ID=...)

# Element read helpers seen across WorkHive pages: document.getElementById('id'),
# querySelector('#id'/'id'), and the `$('id')` getElementById shorthand (most pages
# define `const $ = id => document.getElementById(id)`). All three reference the field.
_READ = r"(?:getElementById|querySelector(?:All)?|\$)\(\s*['\"]#?{ID}['\"]"

# A direct column mapping:  `   columnName: ...$('<id>')... ` or `...getElementById('<id>')...`
def direct_col_re(fid: str) -> re.Pattern:
    return re.compile(r"([A-Za-z_]\w*)\s*:\s*[^,;{}\n]*?" + _READ.format(ID=re.escape(fid)))

def id_ref_re(fid: str) -> re.Pattern:
    return re.compile(_READ.format(ID=re.escape(fid)))


def load_capture_fields() -> dict[str, list[str]]:
    m = json.loads(LMAP.read_text(encoding="utf-8"))
    by_surface: dict[str, list[str]] = defaultdict(list)
    for rec in m.get("fields", {}).values():
        if rec.get("kind") != "capture":
            continue
        surfs = rec.get("input_surfaces") or []
        if any(s in CALC_SURFACES for s in surfs):
            continue
        tgt = next((s for s in surfs if s in PERSISTED_SURFACES), None)
        if tgt:
            by_surface[tgt].append(rec.get("field"))
    return by_surface


def nearest_signal(lines: list[str], anchor: int, regex: re.Pattern, window: int = 60):
    """Return (lineno_1based, matchtext, distance) of nearest regex hit to anchor, or None.
    Searches both directions; persistence usually follows the reads in the same handler."""
    best = None
    lo = max(0, anchor - window)
    hi = min(len(lines), anchor + window + 1)
    for i in range(lo, hi):
        mm = regex.search(lines[i])
        if mm:
            dist = abs(i - anchor)
            if best is None or dist < best[2]:
                best = (i + 1, mm.group(0)[:60], dist, mm)
    return best


def classify_surface(surface: str, fids: list[str]) -> list[dict]:
    page = ROOT / SURFACE_FILE[surface]
    if not page.exists():
        return [{"surface": surface, "field": f, "bucket": "PAGE_MISSING",
                 "confidence": "n/a", "evidence": []} for f in fids]
    text = page.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    out = []
    for fid in fids:
        ref = id_ref_re(fid)
        occ = [i for i, ln in enumerate(lines) if ref.search(ln)]
        rec = {"surface": surface, "field": fid, "bucket": None,
               "confidence": None, "table": None, "column": None, "evidence": []}

        if not occ:
            # id never read via getElementById/querySelector — maybe read via a generic
            # form serialiser or value bound elsewhere; honest unknown, flag for live.
            rec.update(bucket="UNRESOLVED", confidence="low",
                       evidence=["no getElementById/querySelector read found in page"])
            out.append(rec)
            continue

        # 1) DIRECT column mapping at any read site = strongest evidence.
        dcol = direct_col_re(fid)
        direct = None
        for i in occ:
            dm = dcol.search(lines[i])
            if dm:
                direct = (i + 1, dm.group(1))
                break
        # nearest persistence / edge / filter signals — searched from EVERY read site,
        # keeping the closest hit (a field is often read in several handlers).
        def best_across(regex, window):
            cands = [nearest_signal(lines, a, regex, window) for a in occ]
            cands = [c for c in cands if c]
            return min(cands, key=lambda c: c[2]) if cands else None
        persist = best_across(PERSIST_RE, 120)
        edge    = best_across(EDGE_RE, 60)
        filt    = best_across(FILTER_CTX, 25)
        reset   = re.compile(_READ.format(ID=re.escape(fid)) + r"\)?\.value\s*=")
        reset_only = all(reset.search(lines[i]) for i in occ)

        # A direct `column: $('id')` mapping is the strongest evidence → PERSISTED.
        if direct and persist:
            rec.update(bucket="PERSISTED", confidence="high",
                       table=persist[3].group(1), column=direct[1],
                       evidence=[f"L{direct[0]}: column '{direct[1]}' := {fid}",
                                 f"L{persist[0]}: {persist[3].group(1)}.{persist[3].group(2)}()"])
        elif direct and not persist:
            # direct `column:` mapping but the persist op is outside window — still strong
            # evidence the field is a write payload key; live-confirm the table.
            rec.update(bucket="PERSISTED?", confidence="medium", column=direct[1],
                       evidence=[f"L{direct[0]}: column '{direct[1]}' := {fid} (payload key; table live-confirm)"])
        else:
            # No direct column line → pick the NEAREST contextual signal among
            # persist / edge / filter (distance-competitive, evidence-based).
            ranked = sorted(
                [(persist, "persist"), (edge, "edge"), (filt, "filter")],
                key=lambda x: x[0][2] if x[0] else 10 ** 9)
            top, kind = ranked[0]
            if top is None:
                if reset_only:
                    rec.update(bucket="NO_TERMINUS", confidence="medium",
                               evidence=[f"id only assigned (.value=) at L{occ[0]+1} — captured-but-dropped?"])
                else:
                    rec.update(bucket="UNRESOLVED", confidence="low",
                               evidence=[f"L{occ[0]+1}: read {fid}; no persist/edge/filter within window"])
            elif kind == "persist":
                rec.update(bucket="PERSISTED?", confidence="medium", table=top[3].group(1),
                           evidence=[f"L{occ[0]+1}: read {fid}",
                                     f"L{top[0]}: {top[3].group(1)}.{top[3].group(2)}() @Δ{top[2]} (column indirected — live-confirm)"])
            elif kind == "edge":
                tgt = top[3].group(1) or "fetch"
                rec.update(bucket="AI_EDGE", confidence="medium", table=f"edge:{tgt}",
                           evidence=[f"L{occ[0]+1}: read {fid}", f"L{top[0]}: {top[1]} @Δ{top[2]}"])
            else:
                rec.update(bucket="TRANSIENT_UI", confidence="medium",
                           evidence=[f"L{occ[0]+1}: read {fid}", f"L{top[0]}: {top[1]} @Δ{top[2]} (filter/render context)"])
        out.append(rec)
    return out


def main() -> int:
    if not LMAP.exists():
        print("  lineage_map.json missing — run mine_lineage_map.py first")
        return 1
    by_surface = load_capture_fields()
    total = sum(len(v) for v in by_surface.values())

    all_recs: list[dict] = []
    for surface in sorted(by_surface):
        all_recs.extend(classify_surface(surface, sorted(by_surface[surface])))

    buckets = Counter(r["bucket"] for r in all_recs)
    persisted = [r for r in all_recs if r["bucket"] in ("PERSISTED", "PERSISTED?")]
    gaps      = [r for r in all_recs if r["bucket"] == "NO_TERMINUS"]

    print("=" * 80)
    print("  §13 COLUMN-TERMINUS MAP — the 196 assertable-but-value-unverified capture fields")
    print("  (EVIDENCE-BASED static analysis; a TERMINUS map, NOT a value-verification)")
    print("=" * 80)
    print(f"\n  Total capture fields triaged: {len(all_recs)} (expected 196)\n")
    print("  ── Buckets ─────────────────────────────────────────────")
    order = ["PERSISTED", "PERSISTED?", "AI_EDGE", "TRANSIENT_UI", "NO_TERMINUS", "UNRESOLVED", "PAGE_MISSING"]
    for b in order:
        if buckets.get(b):
            print(f"     {b:14} {buckets[b]:3}")
    print(f"\n  → value-VERIFIABLE set (PERSISTED + PERSISTED?) = {len(persisted)} fields"
          f" across {len({r['surface'] for r in persisted})} surfaces")
    print(f"     these are the only ones eligible for the live round-trip value check.")
    if gaps:
        print(f"\n  ⚠ NO_TERMINUS (captured-but-dropped — investigate as possible bugs): {len(gaps)}")
        for g in gaps[:12]:
            print(f"     · {g['surface']}:{g['field']}  ({g['evidence'][0]})")

    # persisted-by-table preview
    tbl = Counter(r["table"] for r in persisted if r.get("table"))
    if tbl:
        print(f"\n  ── PERSISTED fields by target table (top) ──")
        for t, c in tbl.most_common(12):
            print(f"     {t:32} {c}")

    out = {
        "_doc": "§13 column-terminus map for the 196 assertable capture fields. EVIDENCE-BASED "
                "static analysis. PERSISTED = lands in table.column (value-VERIFIABLE, not yet "
                "verified); AI_EDGE/TRANSIENT_UI = correctly not a DB write; NO_TERMINUS = "
                "captured-but-dropped (investigate). Value-correctness is a SEPARATE live round-trip.",
        "total_fields": len(all_recs),
        "buckets": dict(buckets),
        "value_verifiable_count": len(persisted),
        "no_terminus_gaps": [f"{g['surface']}:{g['field']}" for g in gaps],
        "fields": all_recs,
    }
    (ROOT / "column_terminus.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# §13 Column-Terminus Map — the 196 capture fields\n",
          "> EVIDENCE-BASED static analysis of each surface's page JS. This is a **terminus map** "
          "(where each captured field lands), **not** a value-verification. Only the PERSISTED set "
          "is eligible for the live round-trip value check.\n",
          "## Buckets\n", "| Bucket | Count | Meaning |", "|---|---|---|",
          f"| PERSISTED | {buckets.get('PERSISTED',0)} | direct `column: getElementById(id)` into insert/upsert — value-verifiable |",
          f"| PERSISTED? | {buckets.get('PERSISTED?',0)} | inside a persisting function; column indirected — live-confirm |",
          f"| AI_EDGE | {buckets.get('AI_EDGE',0)} | sent to a fetch/edge fn (AI box, intent) — correctly not a DB column |",
          f"| TRANSIENT_UI | {buckets.get('TRANSIENT_UI',0)} | filter/search/render control — correctly not persisted |",
          f"| NO_TERMINUS | {buckets.get('NO_TERMINUS',0)} | captured-but-dropped — **investigate** |",
          f"| UNRESOLVED | {buckets.get('UNRESOLVED',0)} | no clear signal in window — needs live confirm |",
          "",
          f"**Value-verifiable set = {len(persisted)} fields** (PERSISTED + PERSISTED?). "
          "Value-correctness is the next pass (live DB round-trip), only on this set.\n"]
    if gaps:
        md += ["## NO_TERMINUS (possible captured-but-dropped bugs)\n"]
        md += [f"- `{g['surface']}:{g['field']}` — {g['evidence'][0]}" for g in gaps]
    (ROOT / "column_terminus.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n  ✓ wrote column_terminus.json + column_terminus.md")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
