#!/usr/bin/env python3
"""
classify_display_ladder.py  --  Phase E of the INTERACTIVE_LINEAGE_ROADMAP.

Classifies every on-screen display onto Gartner's analytics ladder:

    Descriptive  -> "what happened / what is"      (counts, totals, current state)
    Diagnostic   -> "why did it happen"            (root cause, downtime, overdue, gaps)
    Predictive   -> "what will happen"             (risk, MTBF, days-until-failure, forecast)
    Prescriptive -> "what should I do about it"    (recommended action, reorder, priority)

This is the grounding scaffold for Phase E. Two products:
  1. Every display carries a ladder rung -> the analytics 4-phase engine becomes
     the literal grounding spine for displays on EVERY page (not just analytics).
  2. A rung is GROUNDED only if its anchor resolves to a canonical source (Phase B,
     status RESOLVED*). An ungrounded predictive/prescriptive tile is a display that
     CLAIMS a higher rung than its data can back -> flagged as a residual to fix.

Reuse-first: composes Phase B's resolved anchors verbatim (no new page parsing).
  IN : display_anchor_sources.json   [tools/resolve_display_anchors.py]
  OUT: display_ladder.json + display_ladder.md
Run: python tools/classify_display_ladder.py
"""
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_JSON = os.path.join(ROOT, "display_anchor_sources.json")
OUT_JSON = os.path.join(ROOT, "display_ladder.json")
OUT_MD = os.path.join(ROOT, "display_ladder.md")

RESOLVED_STATUSES = ("RESOLVED", "RESOLVED_KPI", "RESOLVED_JS", "RESOLVED_VERIFIED")

# Keyword rules, most-actionable first. The first family that matches the
# (page, id, token, formula-name, formula-inputs) haystack wins; default is
# descriptive (a plain count/total/current-state read).
RUNGS = [
    ("prescriptive", [
        "recommend", "suggest", "advice", "advis", "action", "next_step", "nextstep",
        "next-step", "priority", "prioriti", "staging", "reorder", "restock", "to_order",
        "playbook", "should", "prescri", "assign", "approve", "dispatch",
    ]),
    # Forward-looking ONLY: predicts a FUTURE state. A risk/forecast/anomaly/P-F
    # number says "what will happen". (A health/quality SCORE is a CURRENT-condition
    # assessment -> diagnostic, not predictive — see below.)
    ("predictive", [
        "predict", "risk", "forecast", "mtbf", "days_until", "days-until", "until_failure",
        "weibull", "p_f", "p-f", "pf_interval", "failure_prob", "probabilit", "anomaly",
        "z-score", "z_score", "projected", "eta", "decay", "remaining_life", "rul",
        "due_soon", "due-soon", "stall_risk", "churn",
    ]),
    # "Why / what is the condition": condition scores (health, quality), failure
    # analysis (downtime, MTTR, root-cause, repeat), and gap/breach states.
    ("diagnostic", [
        "health", "quality", "condition", "root_cause", "root-cause", "rootcause",
        "fault", "downtime", "overdue", "breach", "gap", "variance", "deviation",
        "repeat", "failure_freq", "failure-freq", "noncomplian", "non_complian",
        "compliance", "mttr", "mean_time_to_repair", "consequence", "stockout",
        "low_stock", "out_of_stock",
    ]),
]
DESCRIPTIVE = "descriptive"


def classify(anchor):
    """Return the ladder rung for one Phase-B anchor."""
    parts = [
        str(anchor.get("page", "")),
        str(anchor.get("id", "")),
        str(anchor.get("token", "")),
    ]
    src = anchor.get("source") or {}
    for hop in (src.get("chain") or []):
        parts.append(str(hop.get("formula_id", "")))
        parts.append(str(hop.get("name", "")))
        parts.append(str(hop.get("metric", "")))
        for inp in (hop.get("inputs") or []):
            parts.append(str(inp))
    hay = " ".join(parts).lower()
    # predictive.html as a page is forward-looking by charter -> bias its
    # un-obvious tiles toward predictive (still overridden by a prescriptive hit).
    page_is_predictive = anchor.get("page") == "predictive.html"
    for rung, kws in RUNGS:
        if any(k in hay for k in kws):
            return rung
    if page_is_predictive:
        return "predictive"
    return DESCRIPTIVE


def main():
    data = json.load(open(IN_JSON, encoding="utf-8"))
    anchors = data["anchors"]

    rows = []
    for a in anchors:
        # UI chrome (a control/label/counter with no data provenance) is NOT a data
        # display — exclude it from the ladder denominator so grounded-% is honest.
        if a.get("status") == "EXCLUDED_CHROME":
            continue
        src = a.get("source") or {}
        # Honor a Read-verified bind's analyst-assigned rung over the keyword guess
        # (the verifier saw the render site + meaning); else fall back to keyword rules.
        rung = src.get("rung") if (src.get("via") == "verified_bind" and src.get("rung") in
                                   ("descriptive", "diagnostic", "predictive", "prescriptive")) else classify(a)
        grounded = a.get("status") in RESOLVED_STATUSES
        rows.append({
            "page": a.get("page"),
            "id": a.get("id"),
            "token": a.get("token"),
            "rung": rung,
            "grounded": grounded,
            "source_via": (src.get("via") if grounded else None),
        })

    total = len(rows)
    by_rung = defaultdict(int)
    grounded_by_rung = defaultdict(int)
    for r in rows:
        by_rung[r["rung"]] += 1
        if r["grounded"]:
            grounded_by_rung[r["rung"]] += 1
    grounded_total = sum(1 for r in rows if r["grounded"])
    # Ungrounded predictive/prescriptive = a display claiming a higher rung than
    # its data can back (the residual Phase E must close).
    ungrounded_high = [r for r in rows
                       if not r["grounded"] and r["rung"] in ("predictive", "prescriptive")]

    per_page = defaultdict(lambda: defaultdict(int))
    for r in rows:
        per_page[r["page"]][r["rung"]] += 1

    out = {
        "_doc": "Display ladder classification (Phase E). Each display anchor tagged on Gartner's "
                "Descriptive->Diagnostic->Predictive->Prescriptive ladder. grounded = anchor resolves "
                "to a canonical source (Phase B RESOLVED*). Ungrounded predictive/prescriptive tiles "
                "claim a higher rung than their data backs = residual to fix.",
        "totals": {
            "displays": total,
            "by_rung": dict(by_rung),
            "grounded": grounded_total,
            "grounded_pct": round(100 * grounded_total / total, 1) if total else 0,
            "grounded_by_rung": dict(grounded_by_rung),
            "ungrounded_high_rung": len(ungrounded_high),
        },
        "displays": rows,
        "ungrounded_high_rung": ungrounded_high,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    order = ["descriptive", "diagnostic", "predictive", "prescriptive"]
    lines = ["# Display Ladder — Phase E (where on the analytics ladder is each display?)\n"]
    lines.append("_Generated by `tools/classify_display_ladder.py`._\n")
    lines.append(f"- Displays classified: **{total}**")
    for rung in order:
        n = by_rung.get(rung, 0)
        g = grounded_by_rung.get(rung, 0)
        lines.append(f"  - **{rung.capitalize()}**: {n} ({g} grounded to canonical source)")
    lines.append(f"- Grounded to a canonical source: **{grounded_total}** ({out['totals']['grounded_pct']}%)")
    lines.append(f"- **Ungrounded predictive/prescriptive** (claims a rung its data can't back): "
                 f"**{len(ungrounded_high)}** — Phase E residual\n")

    if ungrounded_high:
        lines.append("## Ungrounded high-rung displays (fix these)\n")
        lines.append("| Page | Display | Token | Rung |")
        lines.append("|---|---|---|---|")
        for r in ungrounded_high:
            lines.append(f"| {r['page']} | `{r['id']}` | {r['token']} | {r['rung']} |")
        lines.append("")

    lines.append("## Per-page ladder mix\n")
    lines.append("| Page | Desc | Diag | Pred | Presc |")
    lines.append("|---|--:|--:|--:|--:|")
    for page in sorted(per_page):
        m = per_page[page]
        lines.append(f"| {page} | {m.get('descriptive',0)} | {m.get('diagnostic',0)} "
                     f"| {m.get('predictive',0)} | {m.get('prescriptive',0)} |")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"[display_ladder] {total} displays classified -> {OUT_JSON}")
    print(f"  by rung: " + ", ".join(f"{k}={by_rung.get(k,0)}" for k in order))
    print(f"  grounded: {grounded_total}/{total} ({out['totals']['grounded_pct']}%) "
          f"· ungrounded high-rung: {len(ungrounded_high)}")


if __name__ == "__main__":
    main()
