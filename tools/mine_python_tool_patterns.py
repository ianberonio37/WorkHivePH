"""
Python Tool Pattern Miner -- WorkHive Platform
===============================================
L-1 Convention Mining for `tools/*.py` (Python scripts, ~74 files).
Mixed-purpose cluster: AI scripts, scrapers, seeders-of-seeders, helpers.
Patterns to surface: argparse vs sys.argv, dotenv loading, cp1252 stdout
guard, idempotency markers, retry / timeout discipline.

Lesson #14 applied: Python uses `#` line comments only (no block).
Lesson #15 doesn't apply here (Python imports are static).

Skills consulted: devops (script invocation, retry / timeout), data-
engineer (idempotency, dotenv discipline), ai-engineer (provider
chain mirror -- [[feedback-python-ai-chain-mirror]]).
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
TOOLS_DIR = ROOT / "tools"

PROMOTE_MIN_CONFORMANCE = 0.80
PROMOTE_MAX_OUTLIERS    = 8

# Skip these -- they're support files, not tools:
EXCLUDE_NAMES = {"__init__.py"}


def _strip_py_comments(text: str) -> str:
    """Python line-comment strip only. Triple-quoted strings can contain
    `#` chars that aren't comments -- a token-level scan would be more
    correct, but `#` rarely appears in non-comment code positions that
    would confuse our feature regexes."""
    return re.sub(r"^[ \t]*#[^\n]*$", "", text, flags=re.MULTILINE)


def extract_features(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_py_comments(raw)
    name = path.name
    nloc = len([ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")])

    f: dict = {"file": name, "nloc": nloc}

    # ---- File header --------------------------------------------------------
    f["has_module_docstring"]   = raw.lstrip().startswith('"""') or raw.lstrip().startswith("'''")
    f["has_shebang"]            = raw.startswith("#!")
    f["uses_future_annotations"] = "from __future__ import annotations" in code

    # ---- Entry-point guard --------------------------------------------------
    f["has_main_guard"]         = bool(re.search(r"""if\s+__name__\s*==\s*["']__main__["']""", code))
    f["defines_main"]           = bool(re.search(r"^def\s+main\s*\(", code, re.MULTILINE))

    # ---- Output discipline --------------------------------------------------
    # cp1252 stdout guard (WorkHive Windows-specific fix; [[feedback-console-encoding]]).
    f["has_cp1252_guard"]       = bool(re.search(r"sys\.stdout\s*=\s*io\.TextIOWrapper", code)) \
                                  or "PYTHONIOENCODING" in code

    # ---- Args ---------------------------------------------------------------
    f["uses_argparse"]          = "import argparse" in code or "from argparse" in code
    f["uses_sys_argv"]          = "sys.argv" in code

    # ---- Env --------------------------------------------------------------
    f["uses_dotenv"]            = "load_dotenv" in code or "dotenv" in code
    f["reads_env_directly"]     = bool(re.search(r"os\.environ", code)) or bool(re.search(r"os\.getenv\s*\(", code))

    # ---- HTTP / retry / timeout --------------------------------------------
    f["uses_requests_lib"]      = bool(re.search(r"\bimport\s+requests\b", code)) or "from requests" in code
    f["uses_httpx"]             = "httpx" in code
    f["passes_request_timeout"] = bool(re.search(r"timeout\s*=", code)) and \
                                  (("requests" in code) or ("httpx" in code))

    # ---- Idempotency / file IO ---------------------------------------------
    f["uses_pathlib"]           = "pathlib" in code or "from pathlib" in code
    f["uses_json_dump"]         = "json.dump" in code or "json.dumps" in code

    # ---- Logging discipline -------------------------------------------------
    f["uses_logging_module"]    = bool(re.search(r"\bimport\s+logging\b", code))
    f["has_print_calls"]        = bool(re.search(r"\bprint\s*\(", code))

    # ---- Subprocess discipline ---------------------------------------------
    f["uses_subprocess"]        = "subprocess" in code
    f["subprocess_has_timeout"] = bool(re.search(r"subprocess\.run\s*\([\s\S]{0,400}?\btimeout\s*=", code))

    # ---- AI chain mirror -- WorkHive-specific rule ([[feedback-python-ai-chain-mirror]])
    f["calls_ai_chain"]         = bool(re.search(r"\bcall_ai_chain\s*\(", code))
    f["bypasses_chain_with_openai"] = "import openai" in code or "from openai" in code
    f["bypasses_chain_with_anthropic"] = "import anthropic" in code or "from anthropic" in code

    return f


def mine() -> dict:
    files = sorted([
        p for p in TOOLS_DIR.glob("*.py")
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
        "promote_threshold": {"min_conformance": PROMOTE_MIN_CONFORMANCE, "max_outliers": PROMOTE_MAX_OUTLIERS},
        "proposals":   proposals,
        "conformance": conformance,
        "per_file":    rows,
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = []
    lines.append("# Python Tool Pattern Mining Report")
    lines.append("")
    lines.append(f"- Files scanned: **{report['summary']['files_scanned']}**")
    lines.append(f"- Features extracted: **{report['summary']['features_extracted']}**")
    lines.append(f"- Promotion threshold: >= {int(PROMOTE_MIN_CONFORMANCE*100)}% conformance, <= {PROMOTE_MAX_OUTLIERS} outliers")
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
    (ROOT / "python_tool_pattern_mining_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, ROOT / "python_tool_pattern_mining_report.md")
    print("Python Tool Pattern Miner")
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
