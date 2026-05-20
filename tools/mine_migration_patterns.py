"""
SQL Migration Pattern Miner -- WorkHive Platform
=================================================
L-1 Convention Mining for `supabase/migrations/*.sql`. Largest cluster
(~145 files). Apply lesson #14 (language-specific comment-strip): SQL has
`--` line comments and `/* */` block comments. The pg-dump baseline
mixes both with unusual density.

Mining what's WORTH mining (avoiding overlap with existing validators):
existing gates cover RLS symmetry, cascade behaviour, jsonb drift,
index coverage, function security. THIS miner targets EMERGENT shape
rules: header convention, IF NOT EXISTS adoption, COMMENT ON adoption,
trigger placement, filename date format, transaction wrapping.

Skills consulted: architect (schema decisions, migration shape),
data-engineer (RLS / FK / index patterns), devops (migration apply
order, idempotency).
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
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

# Large cluster -> standard threshold.
PROMOTE_MIN_CONFORMANCE = 0.80
PROMOTE_MAX_OUTLIERS    = 8


def _strip_sql_comments(text: str) -> str:
    """SQL-language comment strip: `-- line` + `/* block */`. Per lesson
    #14, only strip the comment syntax SQL actually uses. Block-comment
    non-greedy match is acceptable here because SQL does not have regex
    literals or template strings that contain unpaired `/*` or `*/`."""
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"--[^\n]*", "", out)
    return out


# Filename convention: YYYYMMDDHHMMSS_name.sql (Supabase migrate convention).
DATE_FILENAME_RE = re.compile(r"^\d{14}_.+\.sql$")


def extract_features(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_sql_comments(raw)
    name = path.name
    nloc = len([ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")])

    f: dict = {"file": name, "nloc": nloc}

    # ---- Filename + header conventions -------------------------------------
    f["filename_dated"]        = bool(DATE_FILENAME_RE.match(name))
    f["has_banner_header"]     = bool(re.match(r"\s*--\s*={5,}", raw))
    f["has_header_comment"]    = raw.lstrip().startswith("--")

    # ---- Idempotency markers -----------------------------------------------
    f["uses_create_if_not_exists"]    = "CREATE TABLE IF NOT EXISTS" in raw.upper() or \
                                        bool(re.search(r"CREATE\s+(?:TABLE|INDEX|EXTENSION|SCHEMA|TYPE)\s+IF\s+NOT\s+EXISTS", raw, re.IGNORECASE))
    f["uses_create_or_replace"]       = bool(re.search(r"CREATE\s+OR\s+REPLACE\s+(FUNCTION|VIEW|TRIGGER)", raw, re.IGNORECASE))
    f["drops_before_create"]          = bool(re.search(r"DROP\s+(?:TABLE|FUNCTION|TRIGGER|POLICY)\s+IF\s+EXISTS", raw, re.IGNORECASE))

    # ---- Transaction wrapping ----------------------------------------------
    f["wraps_in_transaction"]  = bool(re.search(r"^\s*BEGIN\s*;", raw, re.MULTILINE)) and \
                                 bool(re.search(r"^\s*COMMIT\s*;", raw, re.MULTILINE))

    # ---- RLS pattern --------------------------------------------------------
    f["enables_rls"]           = bool(re.search(r"ALTER\s+TABLE\s+\S+\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY", code, re.IGNORECASE))
    f["creates_policy"]        = bool(re.search(r"CREATE\s+POLICY", code, re.IGNORECASE))

    # ---- Index / FK ---------------------------------------------------------
    f["creates_index"]         = bool(re.search(r"CREATE\s+(?:UNIQUE\s+)?INDEX", code, re.IGNORECASE))
    f["declares_foreign_key"]  = bool(re.search(r"FOREIGN\s+KEY|REFERENCES\s+\w+", code, re.IGNORECASE))
    f["has_on_delete_clause"]  = bool(re.search(r"ON\s+DELETE\s+(CASCADE|RESTRICT|SET\s+NULL|SET\s+DEFAULT|NO\s+ACTION)", code, re.IGNORECASE))

    # ---- Trigger / function security --------------------------------------
    f["creates_function"]      = bool(re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION", code, re.IGNORECASE))
    f["uses_security_definer"] = bool(re.search(r"SECURITY\s+DEFINER", code, re.IGNORECASE))
    f["sets_search_path"]      = bool(re.search(r"SET\s+search_path", code, re.IGNORECASE))
    f["creates_trigger"]       = bool(re.search(r"CREATE\s+TRIGGER", code, re.IGNORECASE))

    # ---- Documentation discipline -----------------------------------------
    f["has_comment_on_table"]  = bool(re.search(r"COMMENT\s+ON\s+TABLE", code, re.IGNORECASE))
    f["has_comment_on_column"] = bool(re.search(r"COMMENT\s+ON\s+COLUMN", code, re.IGNORECASE))

    # ---- Common column conventions ----------------------------------------
    f["uses_updated_at_col"]   = "updated_at" in code.lower()
    f["uses_created_at_col"]   = "created_at" in code.lower()
    f["uses_uuid_pk"]          = bool(re.search(r"\b(?:id\s+)?uuid\b[^,]*(?:PRIMARY\s+KEY|DEFAULT\s+(?:gen_random_uuid|uuid_generate))", code, re.IGNORECASE))

    # ---- Schema -------------------------------------------------------------
    f["targets_public_schema"] = bool(re.search(r"\bpublic\.\w+", code))

    return f


def mine() -> dict:
    if not MIGRATIONS_DIR.exists():
        return {"summary": {"files_scanned": 0, "features_extracted": 0, "promotion_candidates": 0},
                "proposals": [], "conformance": {}, "per_file": []}

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
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
    lines.append("# SQL Migration Pattern Mining Report")
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
    (ROOT / "migration_pattern_mining_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, ROOT / "migration_pattern_mining_report.md")
    print("SQL Migration Pattern Miner")
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
