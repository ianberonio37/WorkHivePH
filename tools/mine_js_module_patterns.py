"""
JS Shared Module Pattern Miner -- WorkHive Platform
====================================================
L-1 Convention Mining for root-level *.js shared modules (utils.js,
nav-hub.js, wh-*.js, etc.). Third cluster after edge fns and HTML pages.

Each module is a small file every page can pick up off the shared rack.
No formal rules were ever written about how to build one; the patterns
that emerged across 25 modules are mined here.

Lesson #14 applied: JS-language comment strip (`//` line + `/* */` block).
Lesson #15 applied: This is the cluster that ANSWERS the runtime-injection
blind spot from the HTML miner -- nav-hub.js etc. dynamically inject
other scripts. The `injects_script_tag` feature surfaces that pattern.

Skills consulted: frontend (IIFE / window-namespace / idempotent loader
conventions), security (escHtml as XSS defence), performance (lazy load
pattern), mobile-maestro (script load order).
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

# Small cluster -> tighter sweet-spot band (per the lesson noted to the user).
PROMOTE_MIN_CONFORMANCE = 0.85
PROMOTE_MAX_OUTLIERS    = 3

# Skip these -- not framework modules:
#   - sw.js                 (service worker, has its own rules)
EXCLUDE_NAMES = {"sw.js"}


def _strip_js_comments(text: str) -> str:
    """JS-language comment strip: `//...` line + `/* ... */` block.
    Per lesson #14, the block stripper would corrupt HTML files but is
    correct here since these are pure JS files. The non-greedy block
    pattern is still risky around regex literals -- we accept that as
    the residual error budget for this cluster."""
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"^[ \t]*//[^\n]*$", "", out, flags=re.MULTILINE)
    return out


def extract_features(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_js_comments(raw)
    name = path.name
    nloc = len([ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("//")])

    f: dict = {"file": name, "nloc": nloc}

    # ---- File header / metadata --------------------------------------------
    f["has_jsdoc_header"]    = raw.lstrip().startswith("/**") or raw.lstrip().startswith("/*")
    f["has_capability_tag"]  = bool(re.search(r"//\s*capability\s*:", raw))

    # ---- Module shape -------------------------------------------------------
    # IIFE wrapper: `(function () { ... })()` or arrow variant.
    f["wraps_in_iife"]       = bool(re.search(r"\(\s*(?:function\s*\(|\(\s*\)\s*=>)", code[:500]))
    f["uses_strict_mode"]    = "'use strict'" in code or '"use strict"' in code

    # ---- Namespace discipline ----------------------------------------------
    # Anchor to window.<name> assignments.
    f["exports_via_window"]  = bool(re.search(r"\bwindow\.\w+\s*=", code))
    # WorkHive convention: window._whSomething or window.WHName or window.workhive*
    f["uses_wh_namespace"]   = bool(re.search(r"\bwindow\.(?:_wh|WH|workhive)", code, re.IGNORECASE))

    # ---- Idempotent load guard ---------------------------------------------
    # if (window._whX) return; or document.querySelector('[data-...]') check
    f["has_idempotent_guard"] = bool(re.search(r"if\s*\(\s*window\.\w+\s*\)\s*\{?\s*return", code)) \
        or bool(re.search(r"document\.querySelector\s*\(\s*['\"]\[data-", code))

    # ---- Dynamic script injection (the runtime-injection pattern itself) ---
    f["injects_script_tag"]   = bool(re.search(r"document\.createElement\s*\(\s*['\"]script['\"]", code))

    # ---- Platform helpers used ---------------------------------------------
    f["uses_eschtml"]         = bool(re.search(r"\bescHtml\s*\(", code))
    f["uses_get_db"]          = bool(re.search(r"\bwindow\.getDb\s*\(", code)) or bool(re.search(r"\bgetDb\s*\(", code))
    f["calls_create_client"]  = bool(re.search(r"\bsupabase\.createClient\s*\(", code))

    # ---- Logging discipline -------------------------------------------------
    # console.log prefixed with [<filename-stem>]
    stem = path.stem
    f["logs_with_module_prefix"] = bool(
        re.search(rf"""console\.(log|warn|error|info)\s*\(\s*['"]\[?{re.escape(stem)}""", code)
    )
    f["has_any_console_log"]  = bool(re.search(r"console\.(log|warn|error|info)\s*\(", code))

    # ---- Lifecycle ----------------------------------------------------------
    f["listens_dom_ready"]    = bool(re.search(r"DOMContentLoaded|document\.readyState", code))

    # ---- Error handling -----------------------------------------------------
    f["has_try_catch"]        = bool(re.search(r"\btry\s*\{", code) and re.search(r"\bcatch\s*[({]", code))

    # ---- Localstorage / state ----------------------------------------------
    f["uses_localstorage"]    = bool(re.search(r"\blocalStorage\.", code))

    return f


def mine() -> dict:
    files = sorted([
        p for p in ROOT.glob("*.js")
        if p.is_file() and p.name not in EXCLUDE_NAMES
    ])
    rows = [extract_features(p) for p in files]
    feature_keys = [k for k in rows[0].keys() if k not in ("file", "nloc")]

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
            "outliers":       [r["file"] for r in negative],
            "positives":      [r["file"] for r in positive],
        }

    proposals = []
    for key, data in conformance.items():
        if data["conformance"] >= PROMOTE_MIN_CONFORMANCE and 0 < len(data["outliers"]) <= PROMOTE_MAX_OUTLIERS:
            proposals.append({
                "feature":       key,
                "conformance":   data["conformance"],
                "outlier_count": len(data["outliers"]),
                "outliers":      data["outliers"],
            })
    proposals.sort(key=lambda p: (-p["conformance"], p["outlier_count"]))

    return {
        "summary": {
            "files_scanned":        len(rows),
            "features_extracted":   len(feature_keys),
            "promotion_candidates": len(proposals),
        },
        "promote_threshold": {
            "min_conformance": PROMOTE_MIN_CONFORMANCE,
            "max_outliers":    PROMOTE_MAX_OUTLIERS,
        },
        "proposals":   proposals,
        "conformance": conformance,
        "per_file":    rows,
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = []
    lines.append("# JS Shared Module Pattern Mining Report")
    lines.append("")
    lines.append(f"- Files scanned: **{report['summary']['files_scanned']}** ({len(EXCLUDE_NAMES)} excluded: {sorted(EXCLUDE_NAMES)})")
    lines.append(f"- Features extracted: **{report['summary']['features_extracted']}**")
    lines.append(f"- Promotion threshold (small cluster): >= {int(PROMOTE_MIN_CONFORMANCE*100)}% conformance, <= {PROMOTE_MAX_OUTLIERS} outliers")
    lines.append(f"- Promotion candidates: **{report['summary']['promotion_candidates']}**")
    lines.append("")
    lines.append("## Promotion candidates")
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
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report = mine()
    (ROOT / "js_module_pattern_mining_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, ROOT / "js_module_pattern_mining_report.md")
    print("JS Shared Module Pattern Miner")
    print(f"  files scanned:        {report['summary']['files_scanned']}")
    print(f"  features extracted:   {report['summary']['features_extracted']}")
    print(f"  promotion candidates: {report['summary']['promotion_candidates']}")
    print()
    print("Top candidates:")
    for p in report["proposals"][:10]:
        olist = ", ".join(p["outliers"][:4])
        print(f"  {int(p['conformance']*100):>3}%  {p['feature']:<28} outliers: {olist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
