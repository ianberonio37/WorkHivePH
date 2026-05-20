"""
Partial-Label Honesty Audit (Tier S — Layer -1.5 rendering correctness).
========================================================================

The Standards Alignment audit catches partials that aren't labelled
partial in the FORMULA contract. This audit catches the same OEE-class
bug at the UI layer: a page renders a partial-variant metric without
telling the user the result is NOT the full standard's number.

The OEE chip already shows "partial (A × Q)"; this audit ensures every
other partial metric (MTBF calendar-time, MTTR total-downtime, PM
compliance 30-day floor, risk score composite, P-F interval direct
display) carries the same honesty marker near every page that renders it.

How it works:
  1. Load formula_contracts.json. Collect formulas with partial_variant=true.
     For each, derive a set of display tokens (substrings likely to appear
     in id attributes for elements that render the metric).
  2. For each page in the canonical 29-page set: scan for those tokens
     in id="X" attributes. If found, check whether the page text near the
     anchor contains an honesty marker (the word "partial", or the
     formula's partial_reason phrasing, or the standard's "approximation"
     keyword).
  3. Flag every page that displays a partial metric without an honesty
     marker — these are OEE-class UI lies.

Output:
  - partial_label_honesty_report.json
  - partial_label_honesty_report.md

Exit code:
  0 = every page that displays a partial metric also renders the honesty
      marker near the value
  1 = at least one page renders a partial metric as if it were the full
      standard's number
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
FORMULAS_PATH = ROOT / "canonical" / "formula_contracts.json"
STANDARDS_PATH = ROOT / "canonical" / "standards.json"

# Same 29-page set as the discovery audit.
PAGES = [
    "hive.html", "logbook.html", "inventory.html", "pm-scheduler.html",
    "analytics.html", "analytics-report.html", "skillmatrix.html",
    "community.html", "public-feed.html", "marketplace.html",
    "marketplace-seller.html", "dayplanner.html", "engineering-design.html",
    "assistant.html", "report-sender.html", "platform-health.html",
    "project-manager.html", "integrations.html", "ph-intelligence.html",
    "project-report.html", "predictive.html", "ai-quality.html",
    "plant-connections.html", "achievements.html", "asset-hub.html",
    "shift-brain.html", "alert-hub.html", "audit-log.html",
    "voice-journal.html", "founder-console.html", "index.html",
]

# Per-formula display-token map. For each partial formula, the tokens listed
# here are id-attribute substrings likely to appear on a page that renders
# the metric. (We can't infer this purely from formula_id — pages name their
# tiles in their own conventions.)
PARTIAL_DISPLAY_TOKENS = {
    "mtbf_iso_14224":             ["mtbf"],
    "mttr_iso_14224":             ["mttr"],
    "pm_compliance_30d":          ["pm-overdue", "pm-compliance", "pm-pct"],
    "risk_score_v2_composite":    ["risk-score", "risk-pct", "composite-risk"],
    "oee_iso_22400_partial":      ["oee"],
    "pump_total_head_api_610":    ["pump-head", "tg-pump"],
    "pf_interval_days":           ["pf-pf", "pf-interval"],
}

# Words that count as an "honesty marker" near the displayed value.
HONESTY_RE = re.compile(
    r"\b(partial|approximation|calendar[-\s]time|total downtime|composite|coarser)\b",
    re.IGNORECASE,
)

# How much surrounding text to scan for an honesty marker (chars before+after the anchor).
WINDOW = 2000


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text)


def main() -> int:
    if not FORMULAS_PATH.exists():
        print(f"FAIL: {FORMULAS_PATH} missing")
        return 2
    formulas = {f["formula_id"]: f for f in json.loads(FORMULAS_PATH.read_text(encoding="utf-8")).get("formulas", []) if "formula_id" in f}

    partial_formulas = {fid: f for fid, f in formulas.items() if f.get("partial_variant")}

    findings = []
    page_results = []
    n_pages_with_honesty = 0
    n_pages_with_violation = 0

    for page_name in PAGES:
        page_path = ROOT / page_name
        if not page_path.exists():
            continue
        raw = page_path.read_text(encoding="utf-8", errors="replace")
        text = _strip_html_comments(raw)

        page_hits = []
        for fid, f in partial_formulas.items():
            tokens = PARTIAL_DISPLAY_TOKENS.get(fid, [])
            for tok in tokens:
                # Look for id="...<token>..." anchors
                pat = re.compile(r"""id=["']([a-z][\w-]*?""" + re.escape(tok) + r"""[\w-]*?)["']""", re.IGNORECASE)
                for m in pat.finditer(text):
                    anchor_id = m.group(1)
                    # Skip ids that themselves contain the word 'partial' — those are honest by construction
                    if "partial" in anchor_id.lower():
                        continue
                    # Scan window around the anchor for an honesty marker
                    start = max(0, m.start() - WINDOW)
                    end = min(len(text), m.end() + WINDOW)
                    window_text = text[start:end]
                    has_marker = HONESTY_RE.search(window_text) is not None
                    page_hits.append({
                        "anchor_id":   anchor_id,
                        "formula_id":  fid,
                        "token":       tok,
                        "has_honesty": has_marker,
                    })
                    if not has_marker:
                        findings.append({
                            "page":       page_name,
                            "anchor_id":  anchor_id,
                            "formula_id": fid,
                            "token":      tok,
                            "needs_label": f.get("partial_reason", "")[:200],
                        })

        if page_hits:
            if any(h["has_honesty"] for h in page_hits):
                n_pages_with_honesty += 1
            if any(not h["has_honesty"] for h in page_hits):
                n_pages_with_violation += 1
        page_results.append({"page": page_name, "hits": page_hits})

    report = {
        "summary": {
            "pages_scanned":           len([p for p in PAGES if (ROOT / p).exists()]),
            "partial_formulas":        len(partial_formulas),
            "pages_with_partial_display": n_pages_with_honesty + n_pages_with_violation,
            "pages_with_honesty":      n_pages_with_honesty,
            "pages_with_violation":    n_pages_with_violation,
            "total_violations":        len(findings),
        },
        "violations": findings,
    }
    (ROOT / "partial_label_honesty_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Markdown
    md = ["# Partial-Label Honesty Audit (Tier S rendering correctness)\n",
          "Every page that displays a partial-variant metric must render an",
          "honesty marker (the word `partial`, `approximation`, `calendar-time`,",
          "`total downtime`, etc.) near the value. Without it, users see the",
          "number as if it were the full standard's result — the OEE-class bug",
          "at the UI layer.\n",
          "## Summary\n",
          f"- Pages scanned:                    **{report['summary']['pages_scanned']}**",
          f"- Partial formulas tracked:         **{report['summary']['partial_formulas']}**",
          f"- Pages that display a partial:     **{report['summary']['pages_with_partial_display']}**",
          f"- Pages with at-least-one honesty marker: **{report['summary']['pages_with_honesty']}**",
          f"- Pages with at-least-one violation:      **{report['summary']['pages_with_violation']}**",
          f"- Total violations:                 **{report['summary']['total_violations']}**",
          ""]
    if findings:
        md.append(f"## ❌ Violations ({len(findings)})\n")
        md.append("| Page | Anchor ID | Formula | Why it's partial |")
        md.append("|---|---|---|---|")
        for v in findings:
            md.append(f"| `{v['page']}` | `{v['anchor_id']}` | `{v['formula_id']}` | {v['needs_label'][:120]} |")
        md.append("")
    (ROOT / "partial_label_honesty_report.md").write_text("\n".join(md), encoding="utf-8")

    # stdout
    s = report["summary"]
    print("Partial-Label Honesty Audit (Tier S rendering correctness)")
    print(f"  pages scanned:                  {s['pages_scanned']}")
    print(f"  partial formulas:               {s['partial_formulas']}")
    print(f"  pages displaying a partial:     {s['pages_with_partial_display']}")
    print(f"  pages with honesty marker:      {s['pages_with_honesty']}")
    print(f"  pages with violation:           {s['pages_with_violation']}")
    print(f"  total violations:               {s['total_violations']}")
    if findings:
        print()
        print("Violations (page → anchor → formula):")
        for v in findings[:10]:
            print(f"  ❌ {v['page']:<28} {v['anchor_id']:<28} → {v['formula_id']}")
        if len(findings) > 10:
            print(f"  ... +{len(findings) - 10} more")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
