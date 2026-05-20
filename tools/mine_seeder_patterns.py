"""
Seeder Pattern Miner -- WorkHive Platform
==========================================
L-1 Convention Mining for `test-data-seeder/seeders/*.py` (~41 files).

Seeders share strong conventions (wipe-then-reseed, hive isolation,
FK ordering) but the rules were never centrally codified. Mining
surfaces which seeders diverge from the consensus skeleton.

Lesson #14 applied: Python `#` line strip.

Skills consulted: data-engineer (idempotency, FK ordering), multitenant-
engineer (hive isolation), qa-tester (reset pattern, RESET_TABLES
participation -- [[feedback-catalog-tables]]).
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
SEEDERS_DIR = ROOT / "test-data-seeder" / "seeders"

PROMOTE_MIN_CONFORMANCE = 0.80
PROMOTE_MAX_OUTLIERS    = 6

EXCLUDE_NAMES = {"__init__.py"}


def _strip_py_comments(text: str) -> str:
    return re.sub(r"^[ \t]*#[^\n]*$", "", text, flags=re.MULTILINE)


def extract_features(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_py_comments(raw)
    name = path.name
    nloc = len([ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")])

    f: dict = {"file": name, "nloc": nloc}

    # ---- File header --------------------------------------------------------
    f["has_module_docstring"]   = raw.lstrip().startswith('"""') or raw.lstrip().startswith("'''")

    # ---- Seeder entry-point shape ------------------------------------------
    f["defines_seed_function"]  = bool(re.search(r"^def\s+seed\s*\(", code, re.MULTILINE))
    f["defines_main_function"]  = bool(re.search(r"^def\s+main\s*\(", code, re.MULTILINE))
    f["has_main_guard"]         = bool(re.search(r"""if\s+__name__\s*==\s*["']__main__["']""", code))

    # ---- Wipe-then-reseed pattern ------------------------------------------
    f["calls_delete"]           = bool(re.search(r"\.delete\s*\(\s*\)", code))
    f["calls_upsert"]           = bool(re.search(r"\.upsert\s*\(", code))
    f["calls_insert"]           = bool(re.search(r"\.insert\s*\(", code))

    # ---- Idempotency markers -----------------------------------------------
    f["mentions_reseed"]        = bool(re.search(r"reseed|re-seed|wipe", code, re.IGNORECASE))
    f["uses_on_conflict"]       = bool(re.search(r"on_conflict\s*=", code))

    # ---- Hive isolation discipline (multi-tenant rule) ---------------------
    f["accepts_hive_id_param"]  = bool(re.search(r"def\s+\w+\s*\([^)]*hive_id", code))
    f["scopes_query_to_hive"]   = bool(re.search(r"""\.eq\s*\(\s*["']hive_id["']""", code))

    # ---- Supabase client ---------------------------------------------------
    f["accepts_client_param"]   = bool(re.search(r"def\s+\w+\s*\([^)]*\bclient\b", code))
    f["calls_table_dot"]        = bool(re.search(r"\.table\s*\(\s*['\"]", code))

    # ---- Constants / catalog modules ---------------------------------------
    # Module-level constants (UPPERCASE_NAMES = [...] or = {...}).
    f["has_module_constants"]   = bool(re.search(r"^[A-Z_][A-Z0-9_]+\s*=\s*[\[\{]", code, re.MULTILINE))

    # ---- Randomization / variety -------------------------------------------
    f["uses_random_module"]     = bool(re.search(r"\bimport\s+random\b", code))
    f["uses_datetime"]          = "datetime" in code

    # ---- Logging / progress -------------------------------------------------
    f["has_print_progress"]     = bool(re.search(r"\bprint\s*\(", code))

    # ---- cp1252 stdout guard (seeders run on the same Windows box) -------
    f["has_cp1252_guard"]       = bool(re.search(r"sys\.stdout\s*=\s*io\.TextIOWrapper", code))

    # ---- Try/except discipline --------------------------------------------
    f["has_try_except"]         = bool(re.search(r"\btry\s*:", code) and re.search(r"\bexcept\b", code))

    return f


def mine() -> dict:
    if not SEEDERS_DIR.exists():
        return {"summary": {"files_scanned": 0, "features_extracted": 0, "promotion_candidates": 0},
                "proposals": [], "conformance": {}, "per_file": []}

    files = sorted([
        p for p in SEEDERS_DIR.glob("*.py")
        if p.is_file() and p.name not in EXCLUDE_NAMES
    ])
    rows = [extract_features(p) for p in files]
    feature_keys = [k for k in rows[0].keys() if k not in ("file", "nloc")] if rows else []

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
        "promote_threshold": {"min_conformance": PROMOTE_MIN_CONFORMANCE, "max_outliers": PROMOTE_MAX_OUTLIERS},
        "proposals":   proposals,
        "conformance": conformance,
        "per_file":    rows,
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = []
    lines.append("# Seeder Pattern Mining Report")
    lines.append("")
    lines.append(f"- Files scanned: **{report['summary']['files_scanned']}**")
    lines.append(f"- Features extracted: **{report['summary']['features_extracted']}**")
    lines.append(f"- Promotion threshold: >= {int(PROMOTE_MIN_CONFORMANCE*100)}% conformance, <= {PROMOTE_MAX_OUTLIERS} outliers")
    lines.append(f"- Promotion candidates: **{report['summary']['promotion_candidates']}**")
    lines.append("")
    lines.append("## Promotion candidates")
    lines.append("")
    lines.append("| Feature | Conformance | Outliers |")
    lines.append("|---|---:|---|")
    for p in report["proposals"]:
        lines.append(f"| `{p['feature']}` | {int(p['conformance']*100)}% | {', '.join(p['outliers'][:5]) + (' ...' if len(p['outliers']) > 5 else '')} |")
    lines.append("")
    lines.append("## Full conformance ranking")
    lines.append("")
    lines.append("| Feature | Conformance | Positive / Total |")
    lines.append("|---|---:|---|")
    ranked = sorted(report["conformance"].items(), key=lambda kv: -kv[1]["conformance"])
    for key, data in ranked:
        lines.append(f"| `{key}` | {int(data['conformance']*100)}% | {data['positive_count']} / {data['total']} |")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report = mine()
    (ROOT / "seeder_pattern_mining_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, ROOT / "seeder_pattern_mining_report.md")
    print("Seeder Pattern Miner")
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
