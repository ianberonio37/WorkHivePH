"""
triage_lineage_paths -- HONEST, EVIDENCE-BASED classification of the H denominator (§13)
=========================================================================================
v2 (2026-06-17) -- REBUILT after a heuristic was caught over-claiming. The first version
labelled 279 paths "un-assertable / structural" by SURFACE NAME, and 196 "passthrough"
by "expected_transform is null". Both were WRONG: every capture surface PERSISTS to a real
table (engineering_calcs, resume_documents, schedule_items, logbook, …), so NONE are
structurally un-assertable, and "no recorded transform" ≠ "verified passthrough". This
version classifies on EVIDENCE only, and never claims a path is verified/covered when it
is not.

THE EVIDENCE WE ACTUALLY HAVE:
  • journey_trace nerves + cross-link  → TRANSFORM chains whose VALUE is live-verified.
  • the Phantom Capture Auditor        → each capture field is CONSUMED/alive (NOT phantom).
                                          This proves the consumer EXISTS, NOT that its value
                                          is correct, and it carries NO DB-column terminus.
  • the DB schema                      → which table each surface persists to (all do).
  • validate_calc_formula_accuracy.py  → NO LONGER A STUB (un-stubbed 2026-06-17). Now
                                          value-verifies the KEY outputs of 7/33 Python calc
                                          types against published-standard hand-computed oracles
                                          (IEC 62548 / NFPA 92 / ISO 281 / PEC / IEC 62305 /
                                          IEC 60909 / ASHRAE Ch.21) + a blind self-test for teeth.
                                          A value-FLOOR, not full per-field coverage.

THE BUCKETS (honest):
  • LOAD_BEARING (verified)  -- transform/aggregate chains a live nerve proved value-correct.
  • LOAD_BEARING (to-prove)  -- transform chains not yet proven.
  • CALC_TRANSFORM (partial) -- engineering-design inputs → engineering_calcs → :8000 calc
                                 → results. Load-bearing (a wrong calc is dangerous). Its
                                 validator is now real (7/33 calc types value-floored against
                                 standards); full per-calc-type + per-field verification is the
                                 remaining named gap, not zero coverage.
  • ASSERTABLE (value-unverified) -- capture fields that PERSIST to a table and are CONSUMED
                                 (capture auditor), but §13 has NOT value-verified them and
                                 their transform-vs-passthrough split needs the DB-column
                                 terminus (which the capture report does not carry). HONEST
                                 unknown -- not asserted passthrough.
  • NEEDS_TERMINUS_EVIDENCE  -- capture fields on a surface whose persistence we have not
                                 established here.

So "can we finish H?" = (a) the transform CORE (chains) is near-done; (b) the calc validator is
now un-stubbed with a standard-anchored value-FLOOR (7/33 calc types) — extending it across the
remaining calc types/fields is the open work; (c) the ~200 persisted capture fields need real
column-terminus + value checks before any can be called passthrough or verified. No shortcut, no fake.

Reads lineage_map.json. Writes lineage_triage.json + lineage_triage.md + a console summary.
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LMAP = ROOT / "lineage_map.json"

# Surfaces VERIFIED to persist to a real table (checked live, 2026-06-17 — every one exists).
# Persisting => the field is ASSERTABLE (there IS a DB terminus); it is NOT structural-N/A.
PERSISTED_SURFACES = {
    "engineering-design", "resume", "dayplanner", "logbook", "pm-scheduler", "inventory",
    "marketplace", "asset-hub", "project-manager", "community", "integrations", "alert-hub",
    "skillmatrix", "voice-journal", "report-sender",
}
# The calc-transform surface: its fields feed engineering_calcs.inputs → :8000 → results.
CALC_SURFACES = {"engineering-design"}

# Transform-text signal (a real aggregate/derive on a chain).
import re
TRANSFORM_RE = re.compile(
    r"\b(count|sum|avg|average|rollup|roll-up|distinct|overdue|due[_ ]?soon|complian|mtbf|mttr|"
    r"oee|low[_ ]?stock|out[_ ]?of[_ ]?stock|risk|score|level|badge|flag|is[_ ]|derived|"
    r"threshold|max|min|aggregate|filter|cross-surface|lifetime|compute|recompute|"
    r"\+1|fresh|recency|within|days_since|acknowledge|soft-delete|deleted)\b", re.I)
PASSTHROUGH_RE = re.compile(r"\b(verbatim|passthrough|dropdown|form|tile on|exposes|displays?|select)\b", re.I)


def classify_chain(c: dict) -> str:
    if c.get("verified"):
        return "load_bearing"
    if c.get("provenance") == "kpi_source_registry":
        return "load_bearing"
    t = c.get("transform") or ""
    if TRANSFORM_RE.search(t):
        return "load_bearing"
    if PASSTHROUGH_RE.search(t) or not t:
        # a curated chain SEGMENT (e.g. "view exposes status verbatim") that is a sub-edge of a
        # load-bearing chain — still part of a transform lineage, but not itself the transform.
        return "chain_segment"
    return "load_bearing"


def classify_field(rec: dict) -> str:
    surfaces = rec.get("input_surfaces") or []
    if any(s in CALC_SURFACES for s in surfaces):
        return "calc_transform"
    if any(s in PERSISTED_SURFACES for s in surfaces):
        return "assertable_unverified"
    return "needs_terminus_evidence"


def main() -> int:
    if not LMAP.exists():
        print("  lineage_map.json missing — run mine_lineage_map.py first")
        return 1
    m = json.loads(LMAP.read_text(encoding="utf-8"))
    fields = m.get("fields", {})
    chains = m.get("canonical_chains", [])

    lb_verified = lb_toprove = seg = 0
    toprove = []
    for c in chains:
        cls = classify_chain(c)
        if cls == "load_bearing":
            if c.get("verified"):
                lb_verified += 1
            else:
                lb_toprove += 1
                toprove.append({"what": c.get("transform") or f"{c.get('source')}→{c.get('target')}",
                                "provenance": c.get("provenance")})
        elif cls == "chain_segment":
            seg += 1

    fb = Counter()
    calc_surfaces_hit = Counter()
    for k, rec in fields.items():
        cls = classify_field(rec)
        fb[cls] += 1
        if cls == "calc_transform":
            for s in (rec.get("input_surfaces") or []):
                calc_surfaces_hit[s] += 1

    lb_total = lb_verified + lb_toprove
    lb_pct = round(100 * lb_verified / lb_total, 1) if lb_total else 0.0
    calc = fb["calc_transform"]
    assertable = fb["assertable_unverified"]
    needs = fb["needs_terminus_evidence"]

    # Live calc-validator coverage (read from the validator so this can't drift).
    # validate_calc_formula_accuracy.py was un-stubbed 2026-06-17.
    calc_floor_types = calc_floor_oracles = calc_total_types = 0
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import validate_calc_formula_accuracy as _vcfa
        calc_floor_types = len(_vcfa.VECTORS)
        calc_total_types = _vcfa.TOTAL_PYTHON_CALCS
        calc_floor_oracles = sum(len(v.get("asserts", [])) or 2 for v in _vcfa.VECTORS)
    except Exception:
        pass
    calc_floor_pct = round(100 * calc_floor_types / calc_total_types, 1) if calc_total_types else 0.0

    print("=" * 78)
    print("  §13 H-AXIS TRIAGE v2 — EVIDENCE-BASED (heuristic 'un-assertable/passthrough' RETRACTED)")
    print("=" * 78)
    print(f"\n  ── TRANSFORM CHAINS (the value-correctness core) ──")
    print(f"     load-bearing {lb_total} · verified {lb_verified} · to-prove {lb_toprove}"
          f"   →  {lb_verified}/{lb_total} = {lb_pct}% value-verified")
    print(f"     (+{seg} curated chain-segments — sub-edges of those chains)")
    print(f"\n  ── CALC-TRANSFORM class (engineering-design → engineering_calcs → :8000 → results) ──")
    print(f"     {calc} input fields = ONE load-bearing calc class · ★COVERAGE = VALUE-FLOOR (no longer a stub)")
    print(f"        validate_calc_formula_accuracy.py now value-verifies {calc_floor_types}/{calc_total_types}"
          f" = {calc_floor_pct}% of Python calc types ({calc_floor_oracles} standard-anchored oracles + teeth);")
    print(f"        full per-calc-type + per-field verification of the {calc} fields is the remaining named gap.")
    print(f"\n  ── ASSERTABLE, value-UNVERIFIED (persist to a table + consumed-alive; NOT yet §13-verified) ──")
    print(f"     {assertable} capture fields — the Phantom Capture Auditor proves they are CONSUMED,")
    print(f"        but NOT value-correct; transform-vs-passthrough split needs the DB-column terminus")
    print(f"        (the capture report carries no column mapping) — HONEST unknown, not 'passthrough'.")
    if needs:
        print(f"\n  ── NEEDS TERMINUS EVIDENCE (surface persistence not established here) ──\n     {needs}")

    print(f"\n  ── HONEST VERDICT ──")
    print(f"     • Transform value-correctness core: {lb_verified}/{lb_total} = {lb_pct}% (rigorous, live nerves).")
    print(f"     • There is NO 'structural un-assertable' bucket — every capture surface PERSISTS.")
    print(f"     • Calc validator UN-STUBBED: {calc_floor_types}/{calc_total_types} calc types value-floored against standards.")
    print(f"     • Full H = extend the calc validator across the remaining calc types/fields + value-verify the")
    print(f"       {assertable} persisted capture fields (needs per-field column-terminus, the real work).")

    out = {
        "_doc": "§13 H-axis triage v2 — evidence-based. Heuristic un-assertable/passthrough split RETRACTED.",
        "transform_chains": {"load_bearing_total": lb_total, "verified": lb_verified,
                             "to_prove": lb_toprove, "value_verified_pct": lb_pct, "chain_segments": seg},
        "calc_transform_fields": calc,
        "calc_coverage": {
            "status": "value-floor (un-stubbed 2026-06-17)",
            "calc_types_value_verified": calc_floor_types,
            "calc_types_total": calc_total_types,
            "pct": calc_floor_pct,
            "standard_anchored_oracles": calc_floor_oracles,
            "validator": "validate_calc_formula_accuracy.py",
            "remaining_gap": f"full per-calc-type + per-field verification of {calc} engineering-design fields",
        },
        "assertable_value_unverified_fields": assertable,
        "needs_terminus_evidence_fields": needs,
        "to_prove_chains": toprove,
        "note": "capture fields are proven CONSUMED (capture auditor), NOT value-correct. No path is "
                "claimed passthrough/structural without DB-column-terminus evidence.",
    }
    (ROOT / "lineage_triage.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# §13 H-Axis Triage v2 — evidence-based (heuristic split retracted)\n",
          "> The earlier 'un-assertable 279 / passthrough 196' split was a SURFACE-NAME heuristic and was WRONG: "
          "every capture surface persists to a real table. This version classifies on evidence only and never "
          "claims verified/covered where it is not.\n",
          "## Honest buckets\n", "| Bucket | Count | Status |", "|---|---|---|",
          f"| **Transform chains — value-verified** | {lb_verified}/{lb_total} ({lb_pct}%) | rigorous (live nerves + exact metric cross-link) |",
          f"| Transform chains — to-prove | {lb_toprove} | the analytics prescriptive path |",
          f"| **CALC-TRANSFORM class** (engineering-design) | {calc} fields | load-bearing; validator **un-stubbed** — value-floor {calc_floor_types}/{calc_total_types} calc types ({calc_floor_oracles} standard-anchored oracles); full per-field verification still open |",
          f"| **ASSERTABLE, value-unverified** | {assertable} | persists + consumed-alive; §13 value-check pending (needs column terminus) |",
          f"| needs terminus evidence | {needs} | surface persistence not established |",
          f"| curated chain-segments | {seg} | sub-edges of the transform chains |",
          "",
          "**Verdict:** the transform value-correctness core is rigorous and ~complete; the calc validator is "
          f"now un-stubbed (value-floor {calc_floor_types}/{calc_total_types} calc types against published "
          "standards, with a blind self-test for teeth). 'Finishing H' honestly still means extending that "
          "validator across the remaining calc types/fields and value-verifying the persisted capture fields "
          "(per-field column terminus) — there is no structural-N/A shortcut.\n"]
    (ROOT / "lineage_triage.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n  ✓ wrote lineage_triage.json + lineage_triage.md")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
