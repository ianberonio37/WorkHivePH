#!/usr/bin/env python3
"""
validate_analytics_ufai_scoreboard.py — THE ANTI-DRIFT LOCK for ANALYTICS_UFAI_ROADMAP.md

Ian, 2026-07-15: "lay it out here and lock it so that you wont drift away."

The scoreboard in ANALYTICS_UFAI_ROADMAP.md says analytics.html is at 97.2% (44/45 dims
measured). A doc alone drifts: the next edit silently un-does a fix and the number keeps
claiming 100%. This gate re-asserts the STATIC invariant behind every dim that was driven
to 100%, so a regression turns a gate RED instead of quietly falsifying the roadmap.

WHAT THIS GATE CAN AND CANNOT DO (read before trusting it):
  - It asserts the CODE-SIDE invariant of each dim (the CSS rule, the ISO8601 arg, the
    data-i wiring, the h2 headings). If the invariant is gone, the dim CANNOT still be at
    100%, so the gate fails.
  - It CANNOT re-measure the LIVE numbers (axe 0, CLS 0.005, INP 64ms, contrast 453/453,
    tap-targets 0/52). Those need a browser. They are measured by ufai_battery.js via
    Playwright MCP and recorded in the roadmap; this gate guards the code that produced
    them. Live re-measure = `__UFAI.sweepAll()` per BATTERY_ARCHITECTURE.md.
  - Value-accuracy (pillar X1 / the number being TRUE) is guarded separately + hermetically
    by tools/validate_analytics_correctness.py (8 vectors, 4/4 phases).

Exit 0 = every invariant intact. Exit 1 = a scored dim regressed.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "analytics.html"
UTILS = ROOT / "utils.js"
LEARN = ROOT / "learn-link.js"
ANALYTICS_PY = ROOT / "python-api" / "analytics"
ML_PY = ROOT / "python-api" / "ml" / "feature_engineering.py"

FAILS: list[str] = []
OKS: list[str] = []


def check(dim: str, ok: bool, detail: str) -> None:
    (OKS if ok else FAILS).append(f"{dim:<6} {detail}")


def main() -> int:
    html = HTML.read_text(encoding="utf-8", errors="ignore")
    utils = UTILS.read_text(encoding="utf-8", errors="ignore")
    learn = LEARN.read_text(encoding="utf-8", errors="ignore")

    # ── X1 CORRECTNESS: mixed ISO precision must never be NaT-dropped ────────
    # The 99.4% data-loss bug. EVERY to_datetime on a Postgres column needs
    # format="ISO8601" (pandas >=2.0 infers one format and coerces the rest).
    dt_sites, dt_bad = 0, []
    for py in sorted(ANALYTICS_PY.glob("*.py")) + [ML_PY]:
        if not py.exists():
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "to_datetime(" in line and "#" not in line.split("to_datetime")[0]:
                dt_sites += 1
                if 'format="ISO8601"' not in line:
                    dt_bad.append(f"{py.name}:{i}")
    check("X1", dt_sites > 0 and not dt_bad,
          f'to_datetime sites ISO8601-safe: {dt_sites - len(dt_bad)}/{dt_sites}'
          + (f' -- UNSAFE: {", ".join(dt_bad)}' if dt_bad else ''))

    # ── I1 CLS: the three async blocks must stay reserved ────────────────────
    check("I1", "#wh-source-chip { min-height: 62px" in html,
          "#wh-source-chip reserved (empty <p> filled by JS -> 0->62px)")
    check("I1", re.search(r"\.verdict\s*\{[^}]*min-height:\s*72px", html) is not None,
          ".verdict min-height:72px (loading copy was TALLER than final)")
    check("I1", re.search(r"\.action-card\s*\{[^}]*min-height:\s*168px", html) is not None,
          ".action-card min-height:168px (CTA revealed late)")
    # the interaction-CLS fix: the Predictive-only button must NOT sit in the shared header
    hdr = html.split('<div class="phase-tabs"')[0]
    check("I1", 'id="recompute-risk-btn"' not in hdr,
          "recompute-risk-btn NOT in the shared header row (it wrapped 96->148px = 0.173 CLS)")

    # ── F1 touch targets ────────────────────────────────────────────────────
    check("F1", re.search(r"\.list-with-showall \.list-search\s*\{[^}]*min-height:\s*44px", html) is not None,
          ".list-search min-height:44px (was 38 -> rendered 42)")
    check("F1", "min-width:44px;min-height:44px" in learn,
          "learn-link dismiss x is 44x44 (was 28x28 -- shared chrome, every page)")
    check("F1", "min-height:44px" in learn.split("var x =")[0],
          "learn-link guide <a> min-height:44px (was 29px tall)")

    # ── C4 tabular numerals ─────────────────────────────────────────────────
    check("C4", "font-variant-numeric:tabular-nums" in html.replace(" ", ""),
          "analytics KPI heroes + table .num are tabular")
    check("C4", "font-variant-numeric:tabular-nums" in utils.replace(" ", ""),
          "shared renderKpiTile value is tabular")

    # ── Q1 reduced motion ───────────────────────────────────────────────────
    check("Q1", "prefers-reduced-motion" in html,
          "analytics ships its OWN motion-reduced variant")

    # ── N1 i18n ─────────────────────────────────────────────────────────────
    n_datai = len(re.findall(r"data-i=", html))
    check("N1", n_datai >= 25, f"static [data-i] nodes: {n_datai} (>=25)")
    check("N1", "window.WH_LANG" in html and "window.setLang" in html and "window._anFIL" in html,
          "WH_LANG + setLang + FIL dict present")
    check("N1", "if (window.WH_LANG === 'fil') window.setLang('fil');" in html,
          "sync-on-load (a returning FIL user must not see mixed EN/FIL)")
    check("N1", "addEventListener('click', function(){ window.setLang(b.dataset.lang); })"
          .replace(" ", "") in html.replace(" ", ""),
          "lang toggle wired via addEventListener, NOT inline onclick (CSP ratchet)")

    # ── A2 / F2 headings (axe CANNOT catch this: no headings = nothing to mis-order) ──
    n_h2 = len(re.findall(r'<h2 class="card-title"', html))
    check("A2", n_h2 >= 25, f"result-card titles are real <h2>: {n_h2} (>=25)")
    check("A2", '<h2 style="margin:0;font:inherit;color:inherit;">' in utils,
          "renderKpiTile heading WRAPS the button (ARIA accordion; h2-in-button is invalid)")

    # ── E1 dataviz ──────────────────────────────────────────────────────────
    check("E1", "i === 0 ? '#f87171'" not in html,
          "Pareto bars are NOT coloured by RANK (recolor-on-filter anti-pattern)")
    check("E1", "cumulative_pct ?? 0) <= 80" in html,
          "Pareto colours by the REAL 80% rule (a property of the datum)")
    check("E1", html.count("autorange: 'reversed'") >= 2,
          "pareto + health charts read WORST-FIRST (Plotly puts data[0] at the BOTTOM)")

    # ── L1 honest design ────────────────────────────────────────────────────
    check("L1", "No 80/20 concentration" in html,
          "Pareto tells the truth when the data has no 80/20 concentration")

    # ── R1 8-pt rhythm ──────────────────────────────────────────────────────
    check("R1", "margin-top:-4px" not in html,
          "no ad-hoc negative margin (the -4px that broke the 8-pt grid)")

    # ── C1 + CROSS-PAGE KPI TIER PARITY (Ian: "extend it all so they are harmonious") ──
    # ONE canonical KPI number tier platform-wide: 1.5rem standard + .simple-card.hero
    # clamp for the ONE key metric. renderKpiTile shipped a THIRD size (1.9rem) which
    # inverted analytics' hierarchy (detail 30px LOUDER than the summary 24px).
    check("C1", "font-size:1.9rem" not in utils.replace(" ", ""),
          "renderKpiTile is NOT a third KPI size (1.9rem inverted detail-vs-summary)")
    check("C1", "font-size:1.5rem;font-weight:800;line-height:1.15;color:${c.text};font-variant-numeric:tabular-nums;"
          .replace(" ", "") in utils.replace(" ", ""),
          "renderKpiTile renders the canonical 1.5rem tier + tabular")
    # Every page that INLINES the primitive (no <link> to components.css) must MATCH the
    # canonical tier -- these 6 cannot inherit it, so drift here is invisible until a user
    # sees two sizes for one number. (ai-quality was 1.8rem, plant-connections 1.4rem.)
    INLINE_KPI_PAGES = ["analytics.html", "alert-hub.html", "hive.html",
                        "pm-scheduler.html", "ai-quality.html", "plant-connections.html"]
    tier_re = re.compile(r"\.simple-card \.sc-hero\s*\{[^}]*font-size:\s*1\.5rem[^}]*tabular-nums", re.S)
    off_tier = []
    for name in INLINE_KPI_PAGES:
        f = ROOT / name
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"<link[^>]*components\.css", txt):
            continue  # inherits the canonical; a local copy is not required
        if not tier_re.search(txt):
            off_tier.append(name)
    check("C1", not off_tier,
          f"inline-KPI pages all match the canonical 1.5rem+tabular tier"
          + (f" -- OFF-TIER: {', '.join(off_tier)}" if off_tier else f" ({len(INLINE_KPI_PAGES)} pages)"))
    check("C4", "font-variant-numeric:tabular-nums" in (ROOT / "components.css").read_text(
              encoding="utf-8", errors="ignore").replace(" ", ""),
          "the CANONICAL .sc-hero carries tabular-nums (so the 11 linking pages inherit it)")

    # ── PAGE 2: analytics-report.html (the print/PDF deliverable) ───────────
    rep = (ROOT / "analytics-report.html").read_text(encoding="utf-8", errors="ignore")
    check("C4", "font-variant-numeric: tabular-nums" in rep,
          "[report] doc tables + KPI values are tabular (a print report IS columns of numbers)")
    check("F2", 'class="table-wrap" role="group" tabindex="0"' in rep,
          "[report] scrollable tables are keyboard-reachable (axe scrollable-region-focusable, SC 2.1.1)")
    # Match the DECLARATION, not the surrounding prose: the first cut of this check
    # scanned a 220-char window and tripped on the code COMMENT that explains the fix
    # (it names #a78bfa). A validator that reads comments reports on documentation, not
    # on behaviour -- strip comments, then read the actual `color:` in the rule.
    _logo_rule = ""
    _m = re.search(r"\.doc-panel \.doc-logo\s*\{(.*?)\}", rep, re.S)
    if _m:
        _logo_rule = re.sub(r"/\*.*?\*/", "", _m.group(1), flags=re.S)
    _logo_color = (re.search(r"color:\s*(#[0-9a-fA-F]{3,6})", _logo_rule) or [None, ""])[1]
    check("C2", bool(_logo_color) and _logo_color.lower() != "#a78bfa",
          f"[report] .doc-logo ink is {_logo_color or 'MISSING'} -- not the dark-shell lilac (~2.6:1 on white print)")
    check("C2", "color:#888" not in rep,
          "[report] muted captions are not #888 (3.54:1 on white)")
    check("C2", "function _segInk(" in rep and "color:' + _segInk(s.color)" in rep,
          "[report] stacked-bar ink is picked from segment luminance, not hard-coded white")
    check("I1", "scrollbar-gutter: stable" in rep,
          "[report] scrollbar gutter reserved (its mid-flight arrival slid the aurora = 0.12 CLS)")
    check("N1", "window._arFIL" in rep and "if (window.WH_LANG === 'fil') window.setLang('fil');" in rep,
          "[report] honours the platform-wide wh_lang on load (cross-page mixed-locale bug)")

    # ── report ──────────────────────────────────────────────────────────────
    print("  Analytics UFAI scoreboard lock -- ANALYTICS_UFAI_ROADMAP.md")
    print("  " + "-" * 54)
    for o in OKS:
        print(f"    ok {o}")
    for f in FAILS:
        print(f"    XX {f}")
    print("  " + "-" * 54)
    total = len(OKS) + len(FAILS)
    print(f"  invariants: {len(OKS)}/{total} intact")
    if FAILS:
        print(f"\n  FAIL -- {len(FAILS)} scored dim(s) regressed. The roadmap's 97.2% is now a LIE.")
        print("  Fix the code or re-measure and update ANALYTICS_UFAI_ROADMAP.md honestly.")
        return 1
    print("  PASS -- every scored dim's code-side invariant is intact.")
    print("  (Live numbers -- axe/CLS/INP/contrast/tap -- re-measure via __UFAI.sweepAll();")
    print("   value-accuracy via tools/validate_analytics_correctness.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
