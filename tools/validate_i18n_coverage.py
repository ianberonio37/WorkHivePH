#!/usr/bin/env python3
"""validate_i18n_coverage.py — P11 i18n adoption scanner (bug-hunt denominator v2, 2026-07-17).

The platform localizes EN+FIL via `data-i="key"` attributes (static HTML) and `_t('key')` /
`WH_LANG` / the `wh-locale-change` re-render (JS strings). This gate measures per USER-FACING page
how adopted that shared i18n system is — the P11 dimension the per-page battery was missing.

It counts i18n MARKERS (`data-i=` + `_t(` + `whT(`) per page and classifies adoption:
  covered  >= 25 markers  ·  partial 5-24  ·  thin 1-4  ·  none 0
Internal / admin surfaces (founder-console) are EN-only by design -> listed EXEMPT, not a gap.

Heuristic v1 caveat: marker COUNT is a proxy for adoption, not an exact translated/total %. A page
with 0 markers genuinely has no i18n; the bands are for triage. A v2 could compute
translated-strings / total-visible-strings for a true %.

ADVISORY / non-blocking (always exits 0) — surfaces the P11 backlog + a platform adoption %, ratchets
as pages get localized. Self-test: --selftest (deterministic, no fs scan).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXCLUDE = ("node_modules", "remotion_scenes", "video_marketing_app", ".backup", "-test.")
# EN-only by design (internal admin / dev / utility surfaces) — not user-facing product, exempt from
# the user-facing i18n requirement (listed as exempt, not counted as a gap).
INTERNAL_EXEMPT = {
    "founder-console.html", "architecture.html", "design-system.html", "symbol-gallery.html",
    "validator-catalog.html", "llm-observability.html", "agentic-rag-observability.html",
    "offline-fallback.html", "promo-poster.html", "status.html",
}

MARKER_RE = re.compile(r"data-i(?:18n)?=|\b_t\(|\bwhT\(", re.I)
INFRA_RE = re.compile(r"WH_LANG|wh-locale-change|window\._t\b|function\s+_t\b", re.I)


def classify(markers: int) -> str:
    if markers >= 25:
        return "covered"
    if markers >= 5:
        return "partial"
    if markers >= 1:
        return "thin"
    return "none"


def scan_text(html: str) -> dict:
    markers = len(MARKER_RE.findall(html))
    return {"markers": markers, "infra": bool(INFRA_RE.search(html)), "verdict": classify(markers)}


def main() -> int:
    pages = [p for p in sorted(REPO.glob("*.html")) if not any(x in p.name for x in EXCLUDE)]
    rows, exempt = [], []
    for p in pages:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        r = scan_text(txt)
        (exempt if p.name in INTERNAL_EXEMPT else rows).append((p.name, r))
    userfacing = len(rows)
    covered = sum(1 for _, r in rows if r["verdict"] == "covered")
    partial = sum(1 for _, r in rows if r["verdict"] == "partial")
    thin = sum(1 for _, r in rows if r["verdict"] == "thin")
    none = sum(1 for _, r in rows if r["verdict"] == "none")
    adoption = round(100 * covered / userfacing) if userfacing else 0
    print("i18n coverage (P11 · EN/FIL adoption of the shared data-i/_t system)")
    print(f"  user-facing pages: {userfacing}  ·  covered: {covered}  partial: {partial}  "
          f"thin: {thin}  none: {none}  ·  adoption(covered/total): {adoption}%")
    gaps = [(n, r) for n, r in rows if r["verdict"] in ("thin", "none")]
    for n, r in sorted(gaps, key=lambda x: x[1]["markers"]):
        print(f"  ⚠ {n:<34} {r['markers']:>3} markers  ({r['verdict']}"
              f"{'' if r['infra'] else ', no i18n infra'})")
    if exempt:
        print(f"  exempt (EN-only by design): {', '.join(n for n, _ in exempt)}")
    if gaps:
        print("  FIX (lever ladder P5): adopt the shared data-i/_t system on the gap pages — "
              "it's the SAME shared component, not per-page translation. ADVISORY, ratchets.")
    return 0  # advisory


def selftest() -> int:
    fails = []
    covered = 'x' + (' data-i="k"' * 30) + '<script>WH_LANG;_t("y")</script>'
    if scan_text(covered)["verdict"] != "covered":
        fails.append("30 data-i + infra should be 'covered'")
    partial = ' data-i="a" data-i="b" _t("c") _t("d") _t("e") '
    if scan_text(partial)["verdict"] != "partial":
        fails.append(f"5 markers should be 'partial', got {scan_text(partial)['verdict']}")
    none = "<p>Plain page, no i18n at all.</p>"
    if scan_text(none)["verdict"] != "none":
        fails.append("0 markers should be 'none'")
    if scan_text(none)["infra"]:
        fails.append("a page with no infra should report infra=False")
    if fails:
        print("✗ validate_i18n_coverage selftest FAILED:")
        for f in fails:
            print("   - " + f)
        return 1
    print("✓ validate_i18n_coverage selftest passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
