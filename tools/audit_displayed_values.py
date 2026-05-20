"""
Displayed Values Audit (Tier S coverage — Layer -1.5).
======================================================

Scans every page in the canonical 29-page set for value-display sites
and cross-references each against canonical/formula_contracts.json.
The output is a per-surface punch list of "values rendered to users
that don't have a formula contract yet" — these are the OEE-class bug
candidates.

For each displayed value the audit tries to classify into:

  CONTRACTED   — display anchor matches a known formula_id (good)
  UNCONTRACTED — domain-meaningful metric label with no formula contract
                 (the gap class; needs a Tier-E formula contract)
  RAW          — element looks like a simple count/timestamp/list size
                 (counts, lengths, dates — no calc, no contract needed)
  UNKNOWN      — couldn't determine semantic identity from id/label/aria

Heuristics:

1. Find element ids matching display patterns: ending in -num, -count,
   -total, -pct, -avg, -score, -days, -hours, -level, -stat-*, -stat,
   sum-*, etc.
2. For each id, infer a metric token from the id stem (e.g. id="stat-mtbf"
   → token=mtbf).
3. Match the token (case-insensitive substring) against:
   - formula_id  → CONTRACTED
   - common metric vocab (MTBF, MTTR, OEE, ...) → UNCONTRACTED
   - count/total/sum/today/active stems → RAW
4. Anything else → UNKNOWN.

Output:
  - displayed_values_report.json
  - displayed_values_report.md (per-page punch list)

Exit code:
  0 always — informational. The report itself is the gate; the team
  works through the punch list over multiple sessions.
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent

# Canonical 29-page set (as specified by the user).
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

# id pattern that signals "this element will display a computed value"
# Widened 2026-05-20 to also catch: -bar, -tier, -trend, -txt, -label suffix,
# oh-stat-*, kpi-*, sum-* prefix patterns.
DISPLAY_ID_RE = re.compile(
    r"""<(?:span|div|td|strong|p)\s+[^>]*\bid=["']([a-z][\w-]*?(?:-(?:num|count|total|pct|avg|score|days|hours|level|val|value|stat|sum|min|max|rate|ratio|index|bar|tier|trend|txt|label|days|hours|earned|spent|rpn|xp)\b|stat-[a-z-]+|[a-z]+-stat\b|^(?:oh-|kpi-|sum-|amc-|count-|pulse-|welcome-|stat-)[a-z-]+))["']""",
    re.IGNORECASE,
)

# Metric vocabulary — keys are tokens we'll look for in the id stem.
# Value is `kind`: 'metric' (needs formula contract), 'raw' (count/timestamp),
# 'unknown' (catch-all).
METRIC_TOKENS = {
    # Core reliability metrics
    "mtbf": "metric", "mttr": "metric", "availability": "metric",
    "oee": "metric", "performance": "metric", "quality": "metric",
    "risk": "metric", "health": "metric",
    "compliance": "metric", "pm-overdue": "metric", "overdue": "metric",
    "rpn": "metric", "fmea": "metric", "weibull": "metric",
    "pf-interval": "metric", "pf-pf": "metric", "anomaly": "metric",
    # Engineering calc families
    "bearing-life": "metric", "pipe-pressure": "metric", "head": "metric",
    "torque": "metric", "thermal": "metric", "load": "metric",
    "flow": "metric", "head-loss": "metric", "npsh": "metric",
    "motor-power": "metric", "hvac": "metric",
    # tg-* are TOGGLE-GROUP INPUTS (radio-button selectors for calculator
    # parameters: number of electrodes, ASHRAE 62.1 outside-air %, L/G ratio,
    # bolt preload target). Not computed outputs — classify as raw.
    "tg-": "raw", "tg-eg": "raw", "tg-lg": "raw", "tg-oa": "raw", "tg-preload": "raw",
    # Gamification + adoption
    "xp": "metric", "level": "metric", "tier": "metric",
    "stair": "metric", "composite": "metric", "readiness": "metric",
    "adoption": "metric", "maturity": "metric", "ring-pct": "metric",
    # AI / cost
    "thumbs": "metric", "trust": "metric", "cost": "metric",
    "savings": "metric", "spend": "metric", "tokens": "metric",
    # Inventory / parts
    "reorder": "metric", "stockout": "metric", "consumption": "metric",
    "lead-time": "metric", "turnover": "metric",
    # Project EVM
    "spi": "metric", "cpi": "metric", "budget": "metric",
    "progress": "metric", "schedule": "metric",
    # Marketplace
    "earned": "metric", "rating": "metric", "dispute": "metric",
    # Skill / exam
    "exam": "metric", "result-score": "metric",
    # Raw display (no contract needed)
    "open-jobs": "raw", "open": "raw", "jobs-today": "raw",
    "members": "raw", "stat-members": "raw",
    "stock-issues": "raw", "low-stock": "raw",
    "closed-today": "raw", "pm-done-today": "raw",
    "today": "raw", "active-alerts": "raw", "alerts": "raw",
    "count": "raw", "total": "raw",
    "last-updated": "raw", "updated-at": "raw",
    # Hive invite / lookup codes (not computed values)
    "code-strip": "raw", "code-value": "raw", "code": "raw",
    # AMC stat tiles (raw counts from JSONB)
    "amc-stat": "raw",
    # Platform-health streak counter (raw count of consecutive clean runs)
    "streak": "raw",
    # Marketplace seller dashboard stat counters (raw aggregates)
    "pstat": "raw",
    # UI scaffolding (verdict text, progress labels, status bars, presence
    # indicators, connection labels, refresh tags, role badges, filter
    # toolbars, asset/sheet pickers, compare-tray strips, view-toggle
    # buttons). Caught by -bar / -label suffix in the regex but they're
    # rendered TEXT or visual scaffolding, not computed metric values.
    "-verdict-label": "raw", "verdict-label": "raw",
    "conn-label": "raw", "presence-bar": "raw", "status-bar": "raw",
    "refresh-label": "raw", "role-bar": "raw", "filter-bar": "raw",
    "asset-picker-label": "raw", "extras-toggle-label": "raw",
    "view-toggle-bar": "raw", "sheet-save-label": "raw",
    "compare-bar": "raw", "hive-name-label": "raw",
    # Single-value labels that are simple counters or trend indicators
    "profile-xp": "raw", "progress-label": "raw", "trend": "raw",
    "aicost-trend": "raw",
}


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text)


def _infer_metric_token(element_id: str) -> tuple[str, str]:
    """Returns (token, kind) where kind is metric|raw|unknown.

    Strategy: lowercase the id, strip common prefixes/suffixes, try each
    METRIC_TOKENS key as a substring match. Pick the longest-match key
    so 'pm-overdue' wins over 'pm' alone.
    """
    raw = element_id.lower()
    # Common cosmetic prefixes
    stripped = re.sub(r"^(oh-|stat-|wh-|kpi-|risk-|sum-|num-|count-|val-)", "", raw)
    best = ""
    for token in METRIC_TOKENS:
        if token in raw or token in stripped:
            if len(token) > len(best):
                best = token
    if best:
        return best, METRIC_TOKENS[best]
    return raw, "unknown"


def _load_formulas() -> set[str]:
    p = ROOT / "canonical" / "formula_contracts.json"
    if not p.exists():
        return set()
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {f.get("formula_id", "") for f in doc.get("formulas", []) if f.get("formula_id")}


# Token → formula_id aliases. These cover cases where the display anchor's
# id doesn't naturally contain the formula_id substring (e.g. "ring-pct"
# is the visual element of `platform_health_pct`; "result-score" is the
# rendered form of `skill_exam_score`).
TOKEN_ALIASES: dict[str, str] = {
    "ring-pct":     "platform_health_pct",
    "result-score": "skill_exam_score",
    "pf-pf":        "pf_interval_days",
    "pf-interval":  "pf_interval_days",
    "stair":        "hive_stair_composite",
    "composite":    "hive_stair_composite",
    "readiness":    "hive_stair_composite",
    "adoption":     "adoption_risk_score_v1",
    "earned":       "marketplace_seller_quality_score",  # marketplace earnings tile
    "health":       "platform_health_pct",
    "ring":         "platform_health_pct",
    "anomaly":      "z_score_anomaly_3sigma",
    "tier":         "skill_level_tier",
    "level":        "skill_level_tier",
}


def main() -> int:
    formula_ids = _load_formulas()
    # Build a lookup from token → formula_id (token = substring of formula_id
    # e.g. 'mtbf' matches 'mtbf_iso_14224')
    formula_index: dict[str, list[str]] = defaultdict(list)
    for fid in formula_ids:
        for token in METRIC_TOKENS:
            if token.replace("-", "_") in fid.replace("-", "_"):
                formula_index[token].append(fid)
    # Augment with explicit aliases (catches cases where the token doesn't
    # naturally appear as a substring of the formula_id).
    for tok, fid in TOKEN_ALIASES.items():
        if fid in formula_ids:
            formula_index[tok].append(fid)

    per_page: dict[str, dict] = {}
    grand = {"contracted": 0, "uncontracted": 0, "raw": 0, "unknown": 0}

    for page_name in PAGES:
        page_path = ROOT / page_name
        if not page_path.exists():
            continue
        text = _strip_html_comments(page_path.read_text(encoding="utf-8", errors="replace"))
        ids = list(set(DISPLAY_ID_RE.findall(text)))
        ids.sort()

        contracted, uncontracted, raw, unknown = [], [], [], []
        for eid in ids:
            token, kind = _infer_metric_token(eid)
            matches = formula_index.get(token, [])
            if matches:
                contracted.append({"id": eid, "token": token, "formula_ids": matches})
            elif kind == "metric":
                uncontracted.append({"id": eid, "token": token})
            elif kind == "raw":
                raw.append({"id": eid, "token": token})
            else:
                unknown.append({"id": eid, "token": token})

        per_page[page_name] = {
            "page":         page_name,
            "discovered":   len(ids),
            "contracted":   contracted,
            "uncontracted": uncontracted,
            "raw":          raw,
            "unknown":      unknown,
        }
        grand["contracted"]   += len(contracted)
        grand["uncontracted"] += len(uncontracted)
        grand["raw"]          += len(raw)
        grand["unknown"]      += len(unknown)

    report = {
        "summary": {
            "pages_scanned":         len([p for p in PAGES if (ROOT / p).exists()]),
            "total_display_anchors": sum(grand.values()),
            "contracted":            grand["contracted"],
            "uncontracted":          grand["uncontracted"],
            "raw":                   grand["raw"],
            "unknown":               grand["unknown"],
            "formula_ids_in_registry": len(formula_ids),
        },
        "by_page":   per_page,
    }
    (ROOT / "displayed_values_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # Markdown report
    md = ["# Displayed Values Audit (Tier S coverage)\n",
          "Scans every page for value-display anchors (element ids ending in",
          "`-num`, `-count`, `-pct`, `-score`, `-days`, etc.) and classifies",
          "each as contracted / uncontracted / raw / unknown.\n",
          "## Summary\n",
          f"- Pages scanned:           **{report['summary']['pages_scanned']}**",
          f"- Display anchors found:   **{report['summary']['total_display_anchors']}**",
          f"- Contracted ✅:           **{report['summary']['contracted']}** (anchor maps to a registered formula)",
          f"- **Uncontracted ⚠️:**     **{report['summary']['uncontracted']}** (domain-meaningful metric, no formula registered)",
          f"- Raw (counts/dates):      **{report['summary']['raw']}** (no contract needed)",
          f"- Unknown:                 **{report['summary']['unknown']}** (couldn't classify from id alone)",
          f"- Formula registry:        **{report['summary']['formula_ids_in_registry']}** entries",
          "",
          "## Per-page breakdown\n",
          "| Page | Anchors | Contracted | Uncontracted | Raw | Unknown |",
          "|---|---:|---:|---:|---:|---:|"]
    for p in PAGES:
        e = per_page.get(p)
        if not e: continue
        md.append(f"| `{p}` | {e['discovered']} | {len(e['contracted'])} | {len(e['uncontracted'])} | {len(e['raw'])} | {len(e['unknown'])} |")
    md.append("")

    # Top uncontracted tokens
    uncon_counter: dict[str, int] = defaultdict(int)
    for e in per_page.values():
        for item in e["uncontracted"]:
            uncon_counter[item["token"]] += 1
    top_uncon = sorted(uncon_counter.items(), key=lambda kv: -kv[1])
    if top_uncon:
        md.append("## Top uncontracted metric tokens (build formulas for these next)\n")
        md.append("| Token | Pages displaying it |")
        md.append("|---|---:|")
        for tok, n in top_uncon[:30]:
            md.append(f"| `{tok}` | {n} |")
        md.append("")

    # Per-page UNCONTRACTED detail (the punch list)
    md.append("## Per-page punch list — uncontracted displays\n")
    for p in PAGES:
        e = per_page.get(p)
        if not e or not e["uncontracted"]:
            continue
        md.append(f"### `{p}` ({len(e['uncontracted'])} uncontracted)")
        for item in e["uncontracted"][:20]:
            md.append(f"- `id=\"{item['id']}\"` · token=`{item['token']}`")
        if len(e["uncontracted"]) > 20:
            md.append(f"- ... +{len(e['uncontracted']) - 20} more")
        md.append("")

    (ROOT / "displayed_values_report.md").write_text("\n".join(md), encoding="utf-8")

    # stdout
    s = report["summary"]
    print("Displayed Values Audit (Tier S coverage)")
    print(f"  pages scanned:       {s['pages_scanned']}")
    print(f"  display anchors:     {s['total_display_anchors']}")
    print(f"  contracted:          {s['contracted']}")
    print(f"  uncontracted:        {s['uncontracted']}")
    print(f"  raw:                 {s['raw']}")
    print(f"  unknown:             {s['unknown']}")
    if top_uncon:
        print()
        print("Top uncontracted tokens (build formulas for these):")
        for tok, n in top_uncon[:8]:
            print(f"  {tok:<22} {n} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
