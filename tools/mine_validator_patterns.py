"""
Validator Pattern Miner -- WorkHive Platform
=============================================
L-1 Convention Mining for `validate_*.py` (~188 files). The miner mining
the miners' colleagues.

Most rules here will be near-100% conformance because the cluster is
highly homogeneous (every file follows the same skeleton). Sweet-spot
candidates therefore surface ONLY genuine outliers -- validators that
diverge from the established skeleton and may be missing key safety
mechanisms (cp1252 stdout guard, format_result usage, exit-code
discipline).

Lesson #14 applied: Python `#` line strip.

Skills consulted: qa-tester (validator skeleton, layer comments,
allowlist patterns), architect (validator-as-contract design).
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

# Homogeneous cluster -> only flag pronounced divergence.
PROMOTE_MIN_CONFORMANCE = 0.90
PROMOTE_MAX_OUTLIERS    = 12


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
    f["mentions_skills_consulted"] = bool(re.search(r"[Ss]kills?\s+consulted", raw[:2000]))
    f["mentions_layer_structure"]  = bool(re.search(r"Layer\s+1\s*--", raw)) or bool(re.search(r"L1\s+", raw))

    # ---- Imports / utilities -----------------------------------------------
    f["imports_validator_utils"] = bool(re.search(r"from\s+validator_utils\s+import", code))
    f["imports_format_result"]   = bool(re.search(r"from\s+validator_utils\s+import[^\n]*format_result", code))
    f["imports_read_file"]       = bool(re.search(r"from\s+validator_utils\s+import[^\n]*read_file", code))
    f["imports_wh_pages"]        = bool(re.search(r"from\s+wh_pages\s+import", code))

    # ---- Safety / portability ---------------------------------------------
    f["has_cp1252_stdout_guard"] = bool(re.search(r"sys\.stdout\s*=\s*io\.TextIOWrapper", code))
    f["uses_future_annotations"] = "from __future__ import annotations" in code

    # ---- Validator skeleton ------------------------------------------------
    f["has_check_names_const"]   = bool(re.search(r"\bCHECK_NAMES\s*=", code))
    f["has_check_labels_const"]  = bool(re.search(r"\bCHECK_LABELS\s*=", code))
    f["calls_format_result"]     = bool(re.search(r"\bformat_result\s*\(", code))
    f["defines_main"]            = bool(re.search(r"^def\s+main\s*\(", code, re.MULTILINE))
    f["has_main_guard"]          = bool(re.search(r"""if\s+__name__\s*==\s*["']__main__["']""", code))
    f["main_exits_with_code"]    = bool(re.search(r"sys\.exit\s*\(\s*main\s*\(\s*\)", code)) \
                                   or bool(re.search(r"return\s+\d+", code))

    # ---- Report write discipline -------------------------------------------
    expected_report = name.replace("validate_", "").replace(".py", "_report.json")
    f["writes_report_json"]      = bool(re.search(rf"['\"][^'\"]*{re.escape(expected_report)}['\"]", code)) \
                                   or bool(re.search(r"_report\.json", code))

    # ---- Allowlist convention ----------------------------------------------
    f["has_allowlist_constant"]  = bool(re.search(r"\bALLOWLIST\s*[:=]", code)) \
                                   or bool(re.search(r"\bDEFERRED\s*[:=]", code))

    # ---- Print / banner -----------------------------------------------------
    f["prints_header_banner"]    = bool(re.search(r"""print\s*\(\s*bold\s*\(|print\s*\(\s*['\"]={5,}""", code))

    # ---- Exit-code seriousness ---------------------------------------------
    f["returns_1_on_fail"]       = bool(re.search(r"return\s+1\b", code))
    f["returns_0_on_success"]    = bool(re.search(r"return\s+0\b", code))

    return f


def mine() -> dict:
    files = sorted(ROOT.glob("validate_*.py"))
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
                "outliers":      data["outliers"][:20],
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
    lines.append("# Validator Pattern Mining Report (Meta)")
    lines.append("")
    lines.append(f"- Files scanned: **{report['summary']['files_scanned']}** validate_*.py")
    lines.append(f"- Features extracted: **{report['summary']['features_extracted']}**")
    lines.append(f"- Promotion threshold (homogeneous cluster): >= {int(PROMOTE_MIN_CONFORMANCE*100)}% conformance, <= {PROMOTE_MAX_OUTLIERS} outliers")
    lines.append(f"- Promotion candidates: **{report['summary']['promotion_candidates']}**")
    lines.append("")
    lines.append("## Promotion candidates")
    lines.append("")
    lines.append("| Feature | Conformance | Outlier count |")
    lines.append("|---|---:|---:|")
    for p in report["proposals"]:
        lines.append(f"| `{p['feature']}` | {int(p['conformance']*100)}% | {p['outlier_count']} |")
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
    (ROOT / "validator_pattern_mining_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, ROOT / "validator_pattern_mining_report.md")
    print("Validator Pattern Miner (Meta)")
    print(f"  files scanned:        {report['summary']['files_scanned']}")
    print(f"  features extracted:   {report['summary']['features_extracted']}")
    print(f"  promotion candidates: {report['summary']['promotion_candidates']}")
    print()
    print("Top candidates:")
    for p in report["proposals"][:10]:
        print(f"  {int(p['conformance']*100):>3}%  {p['feature']:<32} outliers: {p['outlier_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
