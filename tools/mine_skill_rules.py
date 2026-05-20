# audit-scope-allow: each rule in skill_rules_manifest.json declares its own scope (which file set to scan); per-rule scope, not platform-wide consumer scan.
"""
Skill-Rule Miner -- Layer -1.5 Convention Mining (WorkHive Platform)
======================================================================
Reads `skill_rules_manifest.json` and runs each rule against the
codebase. Unlike the cluster miners (which discover unwritten rules
from statistics), this miner enforces rules already DOCUMENTED in
SKILL.md files but never automatically checked.

Architecture:
  - Rules live in skill_rules_manifest.json (one place to edit).
  - Each rule declares its scope (which file set to scan), polarity
    (convention vs anti-pattern), and a regex pattern.
  - Optional `triggered_by` lets a rule apply only to files that
    contain another pattern (e.g., "pages using innerHTML must call
    escHtml").
  - Per-file-extension comment stripping (lesson #14): HTML strips
    only <!--...-->; JS/TS strips //... and block; SQL strips --... and
    block; Python strips #...

How to add a new rule:
  1. Find a concrete, mineable rule in a SKILL.md file
  2. Add a JSON object to skill_rules_manifest.json
  3. Re-run this miner -- no code change required

Skills consulted: security, mobile-maestro, designer, qa-tester,
frontend (the source manifests). architect (manifest design).

Output:
  - skill_rules_mining_report.json
  - skill_rules_mining_report.md
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
MANIFEST_PATH = ROOT / "skill_rules_manifest.json"

# Structured-rule format: any SKILL.md may include a section titled
# `## Auto-Mineable Rules` containing a fenced ```json block with a
# {"rules": [...]} object. The miner auto-loads those rules alongside
# the manifest, so new skills can ship enforceable rules without
# editing skill_rules_manifest.json. Convention defined 2026-05-18.
SKILLS_ROOT = Path.home() / ".claude" / "skills"
AUTO_MINE_HEADER_RE = re.compile(r"^##\s+Auto[- ]?Mineable\s+Rules\s*$", re.IGNORECASE | re.MULTILINE)
JSON_BLOCK_RE = re.compile(r"```json\s*\n([\s\S]*?)\n```", re.MULTILINE)

# Promotion sweet spot for skill rules. Slightly looser than cluster
# miners because skill-derived rules are higher-signal -- a documented
# rule with 70% conformance is still a real finding worth flagging.
PROMOTE_MIN_CONFORMANCE = 0.70
PROMOTE_MAX_OUTLIERS    = 10


# ---------------------------------------------------------------------------
# File-scope resolvers.
# ---------------------------------------------------------------------------

EXCLUDED_HTML = [
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"-test\.html$"),
]

EXCLUDED_JS = {"sw.js"}


def _html_pages() -> list[Path]:
    return sorted([
        p for p in ROOT.glob("*.html")
        if p.is_file() and not any(rx.search(p.name) for rx in EXCLUDED_HTML)
    ])


def _js_modules() -> list[Path]:
    return sorted([
        p for p in ROOT.glob("*.js")
        if p.is_file() and p.name not in EXCLUDED_JS
    ])


def _edge_fns() -> list[Path]:
    fn_root = ROOT / "supabase" / "functions"
    if not fn_root.exists():
        return []
    return sorted([
        p for p in fn_root.iterdir()
        if p.is_dir() and p.name != "_shared" and (p / "index.ts").exists()
    ])


def _migrations() -> list[Path]:
    m_root = ROOT / "supabase" / "migrations"
    return sorted(m_root.glob("*.sql")) if m_root.exists() else []


def _html_and_js() -> list[Path]:
    return _html_pages() + _js_modules()


SCOPE_RESOLVERS = {
    "html_pages":  _html_pages,
    "js_modules":  _js_modules,
    "edge_fns":    _edge_fns,
    "migrations":  _migrations,
    "html_and_js": _html_and_js,
}


# ---------------------------------------------------------------------------
# Comment strippers, indexed by file extension (lesson #14 applied).
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text)


def _strip_js_or_ts(text: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"^[ \t]*//[^\n]*$", "", out, flags=re.MULTILINE)
    return out


def _strip_sql(text: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"--[^\n]*", "", out)
    return out


STRIPPERS = {
    ".html": _strip_html,
    ".js":   _strip_js_or_ts,
    ".ts":   _strip_js_or_ts,
    ".sql":  _strip_sql,
}


def _read_and_strip(path: Path) -> str:
    # Edge fns are directories; load their index.ts. MUST be checked
    # BEFORE the read_text call, otherwise read_text raises
    # PermissionError on the directory itself (caught earlier in the
    # first run on 2026-05-18).
    if path.is_dir():
        index = path / "index.ts"
        if not index.exists():
            return ""
        raw = index.read_text(encoding="utf-8", errors="replace")
        suffix = ".ts"
    else:
        raw = path.read_text(encoding="utf-8", errors="replace")
        suffix = path.suffix

    stripper = STRIPPERS.get(suffix)
    return stripper(raw) if stripper else raw


def _file_display_name(path: Path) -> str:
    """For edge fns return the fn directory name (asset-brain-query),
    otherwise the basename."""
    if path.is_dir():
        return path.name
    return path.name


# ---------------------------------------------------------------------------
# Rule evaluation.
# ---------------------------------------------------------------------------

def _compile(pattern: str, flag_str: str) -> re.Pattern:
    flags = 0
    if "i" in (flag_str or ""):
        flags |= re.IGNORECASE
    if "m" in (flag_str or ""):
        flags |= re.MULTILINE
    return re.compile(pattern, flags)


def evaluate_rule(rule: dict, files: list[Path]) -> dict:
    pattern = _compile(rule["pattern"], rule.get("pattern_flags", ""))
    trigger = None
    if rule.get("triggered_by"):
        trigger = _compile(rule["triggered_by"], rule.get("pattern_flags", ""))

    # excluded_files: list of filenames (basenames) that are KNOWN-LEGIT
    # divergences. Each entry SHOULD be a {file, reason} object so the
    # rationale travels with the suppression. Plain strings also accepted
    # for back-compat. The miner counts these in `skipped_allowlisted` so
    # they remain visible without inflating violator counts.
    excluded_spec = rule.get("excluded_files") or []
    excluded_map: dict[str, str] = {}
    for entry in excluded_spec:
        if isinstance(entry, dict):
            excluded_map[entry.get("file", "")] = entry.get("reason", "(no reason given)")
        elif isinstance(entry, str):
            excluded_map[entry] = "(no reason given)"

    polarity = rule.get("polarity", "convention")
    in_scope = []
    skipped_no_trigger = []
    skipped_allowlisted = []
    positive = []
    negative = []

    for path in files:
        text = _read_and_strip(path)
        name = _file_display_name(path)

        # Allowlist takes precedence over trigger so the report shows
        # WHICH files are suppressed and WHY.
        if name in excluded_map:
            skipped_allowlisted.append({"file": name, "reason": excluded_map[name]})
            continue

        # Apply trigger gate.
        if trigger and not trigger.search(text):
            skipped_no_trigger.append(name)
            continue

        in_scope.append(name)
        match = bool(pattern.search(text))

        # Translate match to "compliant" based on polarity.
        if polarity == "convention":
            compliant = match
        else:  # anti_pattern
            compliant = not match

        (positive if compliant else negative).append(name)

    total_in_scope = len(in_scope)
    conformance = (len(positive) / total_in_scope) if total_in_scope else 1.0

    return {
        "rule_id":              rule["id"],
        "skill":                rule.get("skill", ""),
        "section":              rule.get("section", ""),
        "summary":              rule.get("summary", ""),
        "scope":                rule.get("scope", ""),
        "polarity":             polarity,
        "severity":             rule.get("severity", "info"),
        "rationale":            rule.get("rationale", ""),
        "files_in_scope":       total_in_scope,
        "skipped_no_trigger":   len(skipped_no_trigger),
        "skipped_allowlisted":  skipped_allowlisted,
        "compliant_count":      len(positive),
        "violating_count":      len(negative),
        "conformance":          round(conformance, 3),
        "violators":            negative,
    }


# ---------------------------------------------------------------------------
# Main pipeline.
# ---------------------------------------------------------------------------

def _load_skill_md_rules() -> tuple[list[dict], list[dict]]:
    """Scan SKILLS_ROOT/<skill>/SKILL.md for a `## Auto-Mineable Rules`
    section. Each section may contain a fenced ```json block with a
    `{"rules": [...]}` object. Returns (valid_rules, parse_errors).

    Each rule gets `skill` defaulted to the directory name and `section`
    defaulted to "Auto-Mineable Rules" if not provided.
    """
    valid, errors = [], []
    if not SKILLS_ROOT.exists():
        return valid, errors

    for skill_dir in sorted(SKILLS_ROOT.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")

        header_match = AUTO_MINE_HEADER_RE.search(text)
        if not header_match:
            continue

        # Find the first ```json...``` fence AFTER the header.
        block_match = JSON_BLOCK_RE.search(text, header_match.end())
        if not block_match:
            errors.append({"skill": skill_dir.name,
                           "error": "Found '## Auto-Mineable Rules' heading but no ```json fenced block after it."})
            continue

        try:
            data = json.loads(block_match.group(1))
        except json.JSONDecodeError as e:
            errors.append({"skill": skill_dir.name,
                           "error": f"JSON parse error in Auto-Mineable Rules: {e}"})
            continue

        rules = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(rules, list):
            errors.append({"skill": skill_dir.name,
                           "error": "Auto-Mineable Rules JSON has no `rules` array."})
            continue

        for r in rules:
            if not isinstance(r, dict):
                continue
            r.setdefault("skill",   skill_dir.name)
            r.setdefault("section", "Auto-Mineable Rules")
            r["_source"] = f"skill_md:{skill_dir.name}"
            valid.append(r)

    return valid, errors


def mine() -> dict:
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"Manifest not found: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_rules = manifest["rules"]
    # Tag manifest source so the report can show provenance.
    for r in manifest_rules:
        r.setdefault("_source", "manifest")

    # Phase-2 structured rules from SKILL.md files (Auto-Mineable Rules sections).
    skill_md_rules, skill_md_errors = _load_skill_md_rules()

    # Merge: manifest wins on id collision (manifest is curated, skill.md
    # is author-driven). Track each rule's source for the report.
    rules_by_id = {r["id"]: r for r in skill_md_rules if "id" in r}
    for r in manifest_rules:
        rules_by_id[r["id"]] = r  # manifest overrides
    rules = list(rules_by_id.values())

    results = []
    for rule in rules:
        scope_name = rule["scope"]
        resolver = SCOPE_RESOLVERS.get(scope_name)
        if not resolver:
            results.append({
                "rule_id":  rule["id"],
                "error":    f"Unknown scope: {scope_name}",
            })
            continue
        files = resolver()
        results.append(evaluate_rule(rule, files))

    # Promotion candidates -- documented rules with measurable drift.
    proposals = [
        r for r in results
        if "error" not in r
        and r["files_in_scope"] > 0
        and r["conformance"] < 1.0
        and r["conformance"] >= PROMOTE_MIN_CONFORMANCE
        and r["violating_count"] <= PROMOTE_MAX_OUTLIERS
    ]
    proposals.sort(key=lambda r: (-r["conformance"], r["violating_count"]))

    # Critical/high severity violations regardless of conformance band --
    # even ONE service_role key in frontend is a P0, not a "candidate".
    critical_violations = [
        r for r in results
        if "error" not in r
        and r["violating_count"] > 0
        and r["severity"] in ("critical", "high")
    ]
    critical_violations.sort(key=lambda r: (r["severity"], -r["violating_count"]))

    # Skill summary -- per-skill conformance roll-up.
    by_skill = defaultdict(lambda: {"rules": 0, "violators_total": 0, "skill_conformance_sum": 0.0})
    for r in results:
        if "error" in r:
            continue
        b = by_skill[r["skill"]]
        b["rules"] += 1
        b["violators_total"] += r["violating_count"]
        b["skill_conformance_sum"] += r["conformance"]
    skill_summary = {
        skill: {
            "rules_evaluated":     bucket["rules"],
            "violators_total":     bucket["violators_total"],
            "avg_conformance":     round(bucket["skill_conformance_sum"] / bucket["rules"], 3) if bucket["rules"] else 0.0,
        }
        for skill, bucket in sorted(by_skill.items())
    }

    # Source roll-up: how many rules came from manifest vs from skill.md
    # Auto-Mineable Rules sections. Helps measure adoption of the
    # structured-format convention.
    rules_by_source = defaultdict(int)
    for r in rules:
        rules_by_source[r.get("_source", "unknown")] += 1

    return {
        "summary": {
            "rules_evaluated":      len([r for r in results if "error" not in r]),
            "rules_with_errors":    len([r for r in results if "error" in r]),
            "promotion_candidates": len(proposals),
            "critical_violations":  len(critical_violations),
            "rules_by_source":      dict(rules_by_source),
            "skill_md_parse_errors": skill_md_errors,
        },
        "by_skill":              skill_summary,
        "promotion_candidates":  proposals,
        "critical_violations":   critical_violations,
        "all_results":           results,
        "promote_threshold": {
            "min_conformance": PROMOTE_MIN_CONFORMANCE,
            "max_outliers":    PROMOTE_MAX_OUTLIERS,
        },
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = []
    lines.append("# Skill-Rule Mining Report (Layer -1.5)")
    lines.append("")
    lines.append("Documented rules from `C:/Users/ILBeronio/.claude/skills/<skill>/SKILL.md` files,")
    lines.append("mined against the codebase. Source manifest: `skill_rules_manifest.json`.")
    lines.append("")
    lines.append(f"- Rules evaluated: **{report['summary']['rules_evaluated']}**")
    lines.append(f"- Critical / high-severity violations: **{report['summary']['critical_violations']}**")
    lines.append(f"- Promotion candidates (drift band): **{report['summary']['promotion_candidates']}**")
    src = report['summary'].get('rules_by_source', {})
    if src:
        src_str = ", ".join(f"{k}={v}" for k, v in src.items())
        lines.append(f"- Rules by source: {src_str}")
    parse_errs = report['summary'].get('skill_md_parse_errors', [])
    if parse_errs:
        lines.append(f"- **SKILL.md parse errors: {len(parse_errs)}** (see Parse Errors section below)")
    lines.append("")

    if parse_errs:
        lines.append("## SKILL.md parse errors")
        lines.append("")
        for e in parse_errs:
            lines.append(f"- `{e['skill']}`: {e['error']}")
        lines.append("")

    lines.append("## Per-skill roll-up")
    lines.append("")
    lines.append("| Skill | Rules | Avg conformance | Total violators |")
    lines.append("|---|---:|---:|---:|")
    for skill, b in report["by_skill"].items():
        lines.append(f"| {skill} | {b['rules_evaluated']} | {int(b['avg_conformance']*100)}% | {b['violators_total']} |")
    lines.append("")

    if report["critical_violations"]:
        lines.append("## Critical / high-severity violations -- act immediately")
        lines.append("")
        for r in report["critical_violations"]:
            lines.append(f"### `{r['rule_id']}` ({r['severity']})  -- {r['skill']} :: {r['section']}")
            lines.append(f"- **Rule:** {r['summary']}")
            lines.append(f"- **Conformance:** {int(r['conformance']*100)}%  ({r['compliant_count']} / {r['files_in_scope']})")
            lines.append(f"- **Violators ({r['violating_count']}):** {', '.join(r['violators'][:10])}" + (" ..." if len(r['violators']) > 10 else ""))
            lines.append(f"- **Why it matters:** {r['rationale']}")
            lines.append("")

    lines.append("## Promotion candidates (documented rules with measurable drift)")
    lines.append("")
    if not report["promotion_candidates"]:
        lines.append("_None today -- every documented rule is at 100% conformance, has zero scope, or sits below the promotion band._")
    else:
        lines.append("| Rule | Skill | Severity | Conformance | Violators |")
        lines.append("|---|---|---|---:|---|")
        for r in report["promotion_candidates"]:
            v = ", ".join(r["violators"][:5]) + (" ..." if len(r["violators"]) > 5 else "")
            lines.append(f"| `{r['rule_id']}` | {r['skill']} | {r['severity']} | {int(r['conformance']*100)}% | {v or '—'} |")
    lines.append("")

    lines.append("## All rules (full conformance ranking)")
    lines.append("")
    lines.append("| Rule | Skill | Conformance | Scope | Polarity |")
    lines.append("|---|---|---:|---|---|")
    ranked = sorted([r for r in report["all_results"] if "error" not in r], key=lambda r: r["conformance"])
    for r in ranked:
        lines.append(f"| `{r['rule_id']}` | {r['skill']} | {int(r['conformance']*100)}% ({r['compliant_count']}/{r['files_in_scope']}) | {r['scope']} | {r['polarity']} |")

    lines.append("")
    # Surface the documented-legit allowlist suppressions so they stay
    # visible -- silent suppressions decay into forgotten exceptions.
    allowlisted_rows = []
    for r in report["all_results"]:
        if "error" in r:
            continue
        for sup in r.get("skipped_allowlisted") or []:
            allowlisted_rows.append((r["rule_id"], sup["file"], sup["reason"]))
    if allowlisted_rows:
        lines.append("## Allowlisted suppressions (documented-legit divergences)")
        lines.append("")
        lines.append("| Rule | File | Reason |")
        lines.append("|---|---|---|")
        for rid, fname, reason in allowlisted_rows:
            lines.append(f"| `{rid}` | `{fname}` | {reason} |")
        lines.append("")

    lines.append("## How to extend")
    lines.append("")
    lines.append("Add a new rule:")
    lines.append("")
    lines.append("1. Open `skill_rules_manifest.json`")
    lines.append("2. Append a rule object (id, skill, section, summary, scope, polarity, pattern, rationale, severity)")
    lines.append("3. Re-run `python tools/mine_skill_rules.py`")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report = mine()
    (ROOT / "skill_rules_mining_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, ROOT / "skill_rules_mining_report.md")

    print("Skill-Rule Miner (Layer -1.5)")
    print(f"  rules evaluated:        {report['summary']['rules_evaluated']}")
    print(f"  critical/high violations: {report['summary']['critical_violations']}")
    print(f"  promotion candidates:   {report['summary']['promotion_candidates']}")
    print()
    if report["critical_violations"]:
        print("CRITICAL / HIGH violations:")
        for r in report["critical_violations"][:10]:
            print(f"  [{r['severity']:<8}] {r['rule_id']:<45} {r['violating_count']:>3} violators (conf {int(r['conformance']*100)}%)")
        print()
    if report["promotion_candidates"]:
        print("Promotion candidates (drift band):")
        for r in report["promotion_candidates"][:10]:
            print(f"  {int(r['conformance']*100):>3}%  {r['rule_id']:<45} {r['violating_count']:>3} violators")
    return 0


if __name__ == "__main__":
    sys.exit(main())
