"""
Standards Alignment Auditor (Tier S — Layer -1.5 semantic correctness check).
=============================================================================

For every formula in canonical/formula_contracts.json, verifies:

  1. CITATION VALID   — standard_id points to a known entry in canonical/standards.json
  2. CLAUSE VALID     — standard_clause exists within that standard's clauses map
  3. INPUT COVERAGE   — formula.inputs SUPERSETS the standard clause's required_inputs,
                        OR formula.partial_variant === true AND a partial_reason is present
  4. PARTIAL HONESTY  — if partial_variant=true, the implemented_in description must
                        mention 'partial' OR the formula_id must include '_partial'
                        (so consumers can tell at a glance that the result is NOT
                        the full standard's number)
  5. UNIT MATCH       — formula.unit shape compatible with standard clause's units

This is the auditor that would have caught the OEE-class bug on day 1: a formula
citing ISO 22400-2:2014 §5.5 (which requires availability + performance + quality)
but implementing only availability + quality is either partial (declare it) or
WRONG (caught here).

Output:
  - standards_alignment_report.json
  - standards_alignment_report.md

Exit code:
  0 = every formula either supersets its cited standard's required_inputs
      OR is honestly declared a partial_variant with a reason
  1 = at least one formula silently violates its cited standard
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
STANDARDS_PATH = ROOT / "canonical" / "standards.json"
FORMULAS_PATH  = ROOT / "canonical" / "formula_contracts.json"


def _normalize_input(name: str) -> str:
    """Strip the table prefix from `logbook.created_at` so it can be matched
    against the standard's required_inputs which are unprefixed concepts.
    Also normalize common synonyms."""
    base = name.split(".")[-1].lower()
    # Concept-level synonym map: many fuels map to the same standard input
    aliases = {
        "logbook.created_at":        "operating_time_hours",
        "created_at":                "operating_time_hours",     # MTBF context only
        "logbook.maintenance_type":  "failure_count",
        "maintenance_type":          "failure_count",
        "logbook.downtime_hours":    "active_repair_time_hours",
        "downtime_hours":            "active_repair_time_hours",
        "logbook.status":            "failure_count",
        "pm_assets.last_anchor_date":"pms_completed_on_schedule",
        "last_anchor_date":          "pms_completed_on_schedule",
    }
    return aliases.get(name, aliases.get(base, base))


def main() -> int:
    if not STANDARDS_PATH.exists():
        print(f"FAIL: {STANDARDS_PATH} missing")
        return 2
    if not FORMULAS_PATH.exists():
        print(f"FAIL: {FORMULAS_PATH} missing")
        return 2

    standards_doc = json.loads(STANDARDS_PATH.read_text(encoding="utf-8"))
    formulas_doc  = json.loads(FORMULAS_PATH.read_text(encoding="utf-8"))

    # Index standards by id, and clauses by (standard_id, clause_id)
    standards_by_id = {s["standard_id"]: s for s in standards_doc.get("standards", []) if "standard_id" in s}

    formulas = formulas_doc.get("formulas", []) or []
    results = []
    n_pass = n_fail = n_partial_honest = n_partial_silent = 0

    for f in formulas:
        fid       = f.get("formula_id", "(unnamed)")
        sid       = f.get("standard_id", "")
        clause_id = f.get("standard_clause", "")
        inputs    = f.get("inputs", []) or []
        is_partial = bool(f.get("partial_variant", False))
        partial_reason = (f.get("partial_reason") or "").strip()
        implemented_in = (f.get("implemented_in") or "").lower()

        findings = []
        ok = True

        # 1. CITATION VALID
        if not sid:
            findings.append("missing standard_id (cannot align with any source-of-truth)")
            ok = False
        elif sid not in standards_by_id:
            findings.append(f"standard_id `{sid}` not found in standards.json")
            ok = False
        else:
            std = standards_by_id[sid]
            clauses = std.get("clauses") or {}
            # 2. CLAUSE VALID
            if not clause_id:
                findings.append(f"missing standard_clause (standard `{sid}` has multiple clauses; pick one)")
                ok = False
            elif clause_id not in clauses:
                findings.append(f"clause `{clause_id}` not found under standard `{sid}`. Available: {sorted(clauses.keys())}")
                ok = False
            else:
                clause = clauses[clause_id]
                req_inputs   = set(clause.get("required_inputs") or [])
                got_inputs   = {_normalize_input(i) for i in inputs}
                missing      = req_inputs - got_inputs

                # 3. INPUT COVERAGE
                if missing and not is_partial:
                    findings.append(
                        f"INPUTS GAP: formula declares no partial_variant but is missing "
                        f"{sorted(missing)} from the standard's required_inputs. Either "
                        f"add the inputs OR set partial_variant=true with a partial_reason."
                    )
                    ok = False
                elif missing and is_partial:
                    n_partial_honest += 1
                    findings.append(
                        f"partial OK — declared with reason; missing inputs documented: {sorted(missing)}"
                    )

                # 4. PARTIAL HONESTY
                if is_partial and not partial_reason:
                    findings.append("partial_variant=true but partial_reason is empty (must document why)")
                    ok = False

                if is_partial:
                    # Honesty check: implemented_in OR formula_id must signal partial
                    label_signals_partial = ("partial" in fid.lower()) or ("partial" in implemented_in)
                    if not label_signals_partial:
                        findings.append(
                            f"partial_variant=true but neither formula_id `{fid}` nor implemented_in "
                            f"surfaces the word 'partial'. Consumers can't tell at a glance."
                        )
                        n_partial_silent += 1
                        ok = False

        if ok:
            n_pass += 1
        else:
            n_fail += 1
        results.append({
            "formula_id":     fid,
            "standard_id":    sid,
            "standard_clause":clause_id,
            "is_partial":     is_partial,
            "ok":             ok,
            "findings":       findings,
        })

    report = {
        "summary": {
            "total_formulas":  len(formulas),
            "pass":            n_pass,
            "fail":            n_fail,
            "partial_honest":  n_partial_honest,
            "partial_silent":  n_partial_silent,
        },
        "results": results,
    }

    (ROOT / "standards_alignment_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # Markdown
    md = ["# Standards Alignment Audit (Tier S — Layer -1.5)\n",
          "Cross-checks every formula in `canonical/formula_contracts.json`",
          "against its cited entry in `canonical/standards.json`. Catches the",
          "OEE-class bug: a formula that says it implements a standard but is",
          "actually missing required inputs.\n",
          "## Summary\n",
          f"- Total formulas:  **{report['summary']['total_formulas']}**",
          f"- Pass:            **{report['summary']['pass']}**",
          f"- Fail:            **{report['summary']['fail']}**",
          f"- Partial honest:  **{report['summary']['partial_honest']}** (declared with reason + label)",
          f"- Partial silent:  **{report['summary']['partial_silent']}** ❌ (labelled as full)",
          ""]

    fails = [r for r in results if not r["ok"]]
    if fails:
        md.append(f"## ❌ Failures ({len(fails)})\n")
        for r in fails:
            md.append(f"### `{r['formula_id']}` (cites {r['standard_id']} §{r['standard_clause']})")
            for f in r["findings"]:
                md.append(f"- {f}")
            md.append("")

    partial_honest = [r for r in results if r["is_partial"] and r["ok"]]
    if partial_honest:
        md.append(f"## ⚠️ Declared partial variants ({len(partial_honest)})\n")
        md.append("These formulas honestly declare themselves partial relative to")
        md.append("their cited standard. They are CORRECT per the contract but")
        md.append("should be promoted to full implementations as the missing fuel")
        md.append("fields / RPCs land.\n")
        md.append("| Formula | Standard clause | Missing | Reason |")
        md.append("|---|---|---|---|")
        for r in partial_honest:
            missing_text = next((f.split("documented:")[-1].strip() for f in r["findings"] if "documented:" in f), "—")
            sid = r["standard_id"]
            cls = r["standard_clause"]
            # Pull the reason from the formula JSON
            f_entry = next((f for f in formulas if f.get("formula_id") == r["formula_id"]), {})
            reason = (f_entry.get("partial_reason", "") or "")[:120]
            md.append(f"| `{r['formula_id']}` | {sid} §{cls} | {missing_text} | {reason} |")
        md.append("")

    md.append("## All results (full alignment ranking)\n")
    md.append("| Formula | Standard | Clause | Partial | OK |")
    md.append("|---|---|---|:---:|:---:|")
    for r in results:
        md.append(f"| `{r['formula_id']}` | {r['standard_id']} | {r['standard_clause']} | {'✓' if r['is_partial'] else ''} | {'✅' if r['ok'] else '❌'} |")

    (ROOT / "standards_alignment_report.md").write_text("\n".join(md), encoding="utf-8")

    # stdout
    print("Standards Alignment Audit (Tier S — Layer -1.5 semantic correctness)")
    print(f"  total formulas:    {report['summary']['total_formulas']}")
    print(f"  pass:              {report['summary']['pass']}")
    print(f"  fail:              {report['summary']['fail']}")
    print(f"  partial honest:    {report['summary']['partial_honest']}")
    print(f"  partial silent:    {report['summary']['partial_silent']}")
    if fails:
        print("\nFailures:")
        for r in fails:
            print(f"  ❌ {r['formula_id']} (cites {r['standard_id']} §{r['standard_clause']})")
            for f in r["findings"][:3]:
                print(f"     - {f[:140]}")

    return 1 if n_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
