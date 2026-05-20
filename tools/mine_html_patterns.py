# audit-scope-allow: docstring states scope is root-level *.html only; subdirectory pages (feedback/, learn/) are different page types that don't share the root pattern cluster.
"""
HTML Page Pattern Miner -- WorkHive Platform
============================================
L-1 Convention Mining for HTML pages. Companion to mine_edge_patterns.py.

Mines every root-level *.html (excluding backups + test pages) for emergent
structural patterns and flags outliers in the same sweet-spot band
(>= 80% conformance, <= 6 outliers).

Output is PROPOSALS, not gate failures. Human reviews each, then either:
  (a) writes a strict Layer 0 validator from the outlier list, or
  (b) allowlists the outliers as legit exceptions (e.g., marketplace
      checkout pages don't need a verdict card; landing pages don't
      load offline-banner.js).

This is the SECOND cluster targeted by Convention Mining (after edge fns).
Running it proves the L-1 layer generalises beyond a single homogeneous
cluster.

Skills consulted: frontend (script include order, escHtml convention),
designer (Plain-Read UX Contract: verdict + chips + details toggle),
seo-content (meta tags, OG, JSON-LD), mobile-maestro (viewport, manifest,
theme-color), security (hive membership gating, signin redirect).
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

# Promotion thresholds (same as edge miner so results are comparable).
PROMOTE_MIN_CONFORMANCE = 0.80
PROMOTE_MAX_OUTLIERS    = 6

# Pages to skip:
#   - *.backup*.html         (historical snapshots)
#   - *-test.html            (test harness pages, not user-facing)
#   - index-*-test.html      (variant tests)
EXCLUDE_PATTERNS = [
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"-test\.html$"),
]


def _is_excluded(name: str) -> bool:
    return any(p.search(name) for p in EXCLUDE_PATTERNS)


def _strip_comments(html: str) -> str:
    """Strip ONLY HTML comments. Earlier version also stripped C-style
    /* ... */ blocks (a holdover from the edge-fn miner) which incorrectly
    matched `/*` characters appearing in JS regex literals or template
    strings inside <script> tags -- swallowing legitimate <script src=...>
    declarations. HTML comments are the only form of comment that
    legitimately occurs at the HTML-structural layer."""
    return re.sub(r"<!--[\s\S]*?-->", "", html)


def _loads_script(code: str, basename: str) -> bool:
    """Match <script src="...foo.js..."> in any form (defer, type=module,
    leading slash, query string)."""
    safe = re.escape(basename)
    return bool(re.search(rf"""<script\b[^>]*\bsrc=["'][^"']*{safe}\b""", code, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Feature extractor: one row per page.
# ---------------------------------------------------------------------------

def extract_features(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_comments(raw)
    page = path.name

    f: dict = {"page": page, "size_kb": round(len(raw) / 1024, 1)}

    # ---- HTML structure -----------------------------------------------------
    f["has_doctype_html"]    = bool(re.search(r"<!DOCTYPE\s+html\s*>", raw, re.IGNORECASE))
    f["has_lang_attr"]       = bool(re.search(r"""<html\b[^>]*\blang=["']""", code, re.IGNORECASE))
    f["has_meta_charset"]    = bool(re.search(r"""<meta\b[^>]*charset=""", code, re.IGNORECASE))
    f["has_meta_viewport"]   = bool(re.search(r"""<meta\b[^>]*name=["']viewport""", code, re.IGNORECASE))
    f["has_title_tag"]       = bool(re.search(r"<title>[^<]+</title>", code, re.IGNORECASE))

    # ---- SEO / AEO ----------------------------------------------------------
    f["has_meta_description"] = bool(re.search(r"""<meta\b[^>]*name=["']description""", code, re.IGNORECASE))
    f["has_canonical_link"]   = bool(re.search(r"""<link\b[^>]*rel=["']canonical""", code, re.IGNORECASE))
    f["has_meta_robots"]      = bool(re.search(r"""<meta\b[^>]*name=["']robots""", code, re.IGNORECASE))
    f["has_og_title"]         = bool(re.search(r"""<meta\b[^>]*property=["']og:title""", code, re.IGNORECASE))
    f["has_og_description"]   = bool(re.search(r"""<meta\b[^>]*property=["']og:description""", code, re.IGNORECASE))
    f["has_og_image"]         = bool(re.search(r"""<meta\b[^>]*property=["']og:image""", code, re.IGNORECASE))
    f["has_twitter_card"]     = bool(re.search(r"""<meta\b[^>]*name=["']twitter:card""", code, re.IGNORECASE))
    f["has_jsonld_schema"]    = bool(re.search(r"""<script\b[^>]*type=["']application/ld\+json""", code, re.IGNORECASE))

    # ---- PWA scaffolding ----------------------------------------------------
    f["has_manifest_link"]    = bool(re.search(r"""<link\b[^>]*rel=["']manifest""", code, re.IGNORECASE))
    f["has_theme_color"]      = bool(re.search(r"""<meta\b[^>]*name=["']theme-color""", code, re.IGNORECASE))

    # ---- Platform JS includes (universal baseline) --------------------------
    f["loads_utils_js"]            = _loads_script(code, "utils.js")
    f["loads_nav_hub_js"]          = _loads_script(code, "nav-hub.js")

    # ---- Platform JS includes (extended -- vary by page type) ---------------
    f["loads_wh_ga4_js"]           = _loads_script(code, "wh-ga4.js")
    f["loads_wh_help_js"]          = _loads_script(code, "wh-help.js")
    f["loads_wh_persona_js"]       = _loads_script(code, "wh-persona.js")
    f["loads_wh_tts_js"]           = _loads_script(code, "wh-tts.js")
    f["loads_floating_ai_js"]      = _loads_script(code, "floating-ai.js")
    f["loads_search_overlay_js"]   = _loads_script(code, "search-overlay.js")
    f["loads_maturity_gate_js"]    = _loads_script(code, "maturity-gate.js")
    f["loads_offline_banner_js"]   = _loads_script(code, "offline-banner.js")
    f["loads_wh_capture_validate"] = _loads_script(code, "wh-capture-validate.js")

    # Service worker registration (inline script OR include).
    f["registers_service_worker"] = bool(
        re.search(r"navigator\.serviceWorker\.register\s*\(", code)
    )

    # ---- Supabase / data layer ---------------------------------------------
    f["loads_supabase_cdn"]   = bool(re.search(r"""<script\b[^>]*src=["'][^"']*@supabase/supabase-js""", code, re.IGNORECASE))
    f["uses_createclient"]    = bool(re.search(r"\bcreateClient\s*\(", code))

    # ---- Conventions on JS inside the page ---------------------------------
    f["uses_eschtml_binding"] = bool(re.search(r"\bconst\s+e\s*=\s*escHtml\b", code))
    f["calls_eschtml"]        = bool(re.search(r"\bescHtml\s*\(", code))

    # ---- Hive gating / auth -------------------------------------------------
    f["validates_hive_membership"] = bool(re.search(r"\bvalidateHiveMembership\s*\(", code))
    f["handles_signin_redirect"]   = bool(re.search(r"""['"]\?signin=|signinRedirect\b""", code))
    f["has_empty_state_anchor"]    = bool(re.search(r"""id=["']empty-state["']|class=["'][^"']*\bempty-state\b""", code))

    # ---- Plain-Read UX Contract -- verdict / chip / details ---------------
    # First-run lesson: the codebase uses BARE `class="verdict"` (no wh-
    # prefix) and `id="wh-source-chip"` (id, not class). Earlier regex
    # missed both, producing 0% conformance on patterns that actually
    # ship widely. Fixed to match either pattern.
    f["has_verdict_card"]    = bool(re.search(
        r"""(?:class|id)=["'][^"']*\b(?:wh-verdict|verdict-card|verdict-label|verdict)\b""",
        code
    ))
    f["has_source_chip"]     = bool(re.search(
        r"""(?:class|id)=["'][^"']*\bwh-source-chip\b""",
        code
    ))
    f["has_details_toggle"]  = bool(re.search(r"<details[\s>]", code, re.IGNORECASE))

    # ---- Tailwind dependency -----------------------------------------------
    f["uses_tailwind_cdn"]  = bool(re.search(r"""cdn\.tailwindcss\.com""", code))

    # ---- Accessibility ------------------------------------------------------
    f["has_h1"]             = bool(re.search(r"<h1\b", code, re.IGNORECASE))
    f["has_main_landmark"]  = bool(re.search(r"<main\b", code, re.IGNORECASE))

    return f


# ---------------------------------------------------------------------------
# Mining pipeline.
# ---------------------------------------------------------------------------

def mine() -> dict:
    pages = sorted([
        p for p in ROOT.glob("*.html")
        if p.is_file() and not _is_excluded(p.name)
    ])
    rows = [extract_features(p) for p in pages]
    feature_keys = [k for k in rows[0].keys() if k not in ("page", "size_kb")]

    conformance = {}
    for key in feature_keys:
        positive = [r for r in rows if r[key]]
        negative = [r for r in rows if not r[key]]
        pct = len(positive) / len(rows) if rows else 0
        conformance[key] = {
            "positive_count": len(positive),
            "negative_count": len(negative),
            "total":          len(rows),
            "conformance":    round(pct, 3),
            "outliers":       [r["page"] for r in negative],
            "positives":      [r["page"] for r in positive],
        }

    proposals = []
    for key, data in conformance.items():
        rate_correct = data["conformance"]
        outliers = data["outliers"]
        if rate_correct >= PROMOTE_MIN_CONFORMANCE and 0 < len(outliers) <= PROMOTE_MAX_OUTLIERS:
            proposals.append({
                "feature":       key,
                "conformance":   round(rate_correct, 3),
                "outlier_count": len(outliers),
                "outliers":      outliers,
            })
    proposals.sort(key=lambda p: (-p["conformance"], p["outlier_count"]))

    return {
        "summary": {
            "pages_scanned":        len(rows),
            "features_extracted":   len(feature_keys),
            "promotion_candidates": len(proposals),
        },
        "promote_threshold": {
            "min_conformance": PROMOTE_MIN_CONFORMANCE,
            "max_outliers":    PROMOTE_MAX_OUTLIERS,
        },
        "proposals":   proposals,
        "conformance": conformance,
        "per_page":    rows,
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = []
    lines.append("# HTML Page Pattern Mining Report")
    lines.append("")
    lines.append(f"- Pages scanned: **{report['summary']['pages_scanned']}** (backups + test pages excluded)")
    lines.append(f"- Features extracted: **{report['summary']['features_extracted']}**")
    lines.append(f"- Promotion threshold: >= {int(PROMOTE_MIN_CONFORMANCE*100)}% conformance, <= {PROMOTE_MAX_OUTLIERS} outliers")
    lines.append(f"- Promotion candidates: **{report['summary']['promotion_candidates']}**")
    lines.append("")
    lines.append("## Promotion candidates (sweet spot)")
    lines.append("")
    lines.append("Emergent conventions ready to graduate. For each: decide if the")
    lines.append("outliers are real gaps or legitimate exceptions for that page type.")
    lines.append("")
    lines.append("| Feature | Conformance | Outliers |")
    lines.append("|---|---:|---|")
    for p in report["proposals"]:
        lines.append(f"| `{p['feature']}` | {int(p['conformance']*100)}% | {', '.join(p['outliers']) or '—'} |")
    lines.append("")
    lines.append("## Full conformance ranking")
    lines.append("")
    lines.append("| Feature | Conformance | Positive / Total |")
    lines.append("|---|---:|---|")
    ranked = sorted(report["conformance"].items(), key=lambda kv: -kv[1]["conformance"])
    for key, data in ranked:
        lines.append(f"| `{key}` | {int(data['conformance']*100)}% | {data['positive_count']} / {data['total']} |")
    lines.append("")
    lines.append("## How to act on this report")
    lines.append("")
    lines.append("1. Open a promotion candidate.")
    lines.append("2. Look at the outlier pages -- are they legit exceptions for their page type")
    lines.append("   (e.g., marketplace checkout doesn't need a verdict card)?")
    lines.append("3a. **Real rule, real gaps** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.")
    lines.append("3b. **Page-type-specific rule** -> write the validator with the outlier pages allowlisted.")
    lines.append("3c. **Accidental pattern** -> drop it; not a real rule.")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    report = mine()
    json_path = ROOT / "html_pattern_mining_report.json"
    md_path   = ROOT / "html_pattern_mining_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, md_path)

    print(f"HTML Page Pattern Miner")
    print(f"  pages scanned:        {report['summary']['pages_scanned']}")
    print(f"  features extracted:   {report['summary']['features_extracted']}")
    print(f"  promotion candidates: {report['summary']['promotion_candidates']}")
    print(f"  report (json):        {json_path.name}")
    print(f"  report (md):          {md_path.name}")
    print()
    print("Top 10 candidates (sweet spot):")
    for p in report["proposals"][:10]:
        olist = ", ".join(p["outliers"][:4]) + (" ..." if len(p["outliers"]) > 4 else "")
        print(f"  {int(p['conformance']*100):>3}%  {p['feature']:<32} outliers: {olist}")


if __name__ == "__main__":
    main()
