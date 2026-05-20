"""
AI Prompt Standards Audit (Tier B — Layer -1.5 grounding-correctness check).
==========================================================================

Every AI prompt template in edge fns + shared persona/voice modules that
MENTIONS a domain metric (MTBF, MTTR, OEE, etc.) should also CITE the
canonical standard the metric is registered under (per
canonical/standards.json + canonical/formula_contracts.json).

Without this, AI agents can drift away from their cited standard: a
prompt saying "MTBF is the average time between any failures" while the
underlying RPC computes "mean of inter-arrival intervals of corrective
entries only per ISO 14224 §9.3" will silently produce explanations
that contradict the dashboards.

What this auditor does:

  1. Collects every prompt-template-like string from supabase/functions
     (any string assigned to systemPrompt / userPrompt / system_prompt
     or passed as the first arg to callAI / callGroq / generateContent)
  2. Scans each prompt body for metric keyword mentions (MTBF, MTTR, OEE,
     PM compliance, risk score, ...)
  3. For each (prompt, metric) hit, checks whether the prompt cites the
     metric's registered short_name (e.g. "ISO 14224:2016")
  4. Flags prompts that mention a metric WITHOUT citing its standard
     — these are candidates for grounding drift.

This is informational (no exit-1 default); the report is the punch list
for tightening AI grounding.

Output:
  - ai_prompt_standards_report.json
  - ai_prompt_standards_report.md
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
STANDARDS_PATH = ROOT / "canonical" / "standards.json"
FORMULAS_PATH  = ROOT / "canonical" / "formula_contracts.json"
FUNCTIONS_DIR  = ROOT / "supabase" / "functions"


# Map metric keyword -> formula_id (which then resolves to a standard via
# formula_contracts.json -> standards.json). Tolerate common phrasings.
METRIC_KEYWORDS = {
    r"\bMTBF\b":                    "mtbf_iso_14224",
    r"\bMTTR\b":                    "mttr_iso_14224",
    r"\bOEE\b":                     "oee_iso_22400",
    r"overall equipment effective": "oee_iso_22400",
    r"\bPM compliance\b":           "pm_compliance_30d",
    r"\bpreventive maintenance compliance\b": "pm_compliance_30d",
    r"\brisk score\b":              "risk_score_v2_composite",
    r"\bcomposite risk\b":          "risk_score_v2_composite",
}

# What kinds of prompt-string contexts we look for. Matches the way the
# platform's edge fns actually compose prompts (systemPrompt + userPrompt
# template literals or string assignments).
PROMPT_CONTEXTS_RE = re.compile(
    r"""(?P<key>system_prompt|systemPrompt|user_prompt|userPrompt|prompt)\s*[:=]\s*[`'\"]""",
    re.IGNORECASE,
)


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    text = re.sub(r"^[ \t]*//[^\n]*$", "", text, flags=re.MULTILINE)
    return text


def _collect_edge_fn_files() -> list[Path]:
    out = []
    if not FUNCTIONS_DIR.exists():
        return out
    for fn_dir in sorted(FUNCTIONS_DIR.iterdir()):
        if not fn_dir.is_dir() or fn_dir.name.startswith("_"):
            continue
        idx = fn_dir / "index.ts"
        if idx.exists():
            out.append(idx)
    # Also scan shared persona / ai-chain
    for name in ("persona.ts", "ai-chain.ts"):
        p = FUNCTIONS_DIR / "_shared" / name
        if p.exists():
            out.append(p)
    return out


def _find_prompt_bodies(text: str) -> list[tuple[int, str]]:
    """Yield (line_no, body) for each prompt template literal we can
    extract. We grab text between matching backticks/quotes following a
    prompt-context marker. Approximate but good enough for grounding hints.
    """
    bodies: list[tuple[int, str]] = []
    for m in PROMPT_CONTEXTS_RE.finditer(text):
        quote = text[m.end() - 1]
        if quote not in ("`", "'", '"'):
            continue
        # Find matching closing quote, allowing the standard backslash escapes
        i = m.end()
        depth = 0
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if quote == "`":
                # template literal can contain ${...} expressions; skip them
                if ch == "$" and i + 1 < len(text) and text[i + 1] == "{":
                    depth += 1
                    i += 2
                    continue
                if ch == "}" and depth > 0:
                    depth -= 1
                    i += 1
                    continue
            if ch == quote and depth == 0:
                # end of literal
                body = text[m.end():i]
                line_no = text.count("\n", 0, m.start()) + 1
                bodies.append((line_no, body))
                break
            i += 1
    return bodies


def main() -> int:
    if not STANDARDS_PATH.exists() or not FORMULAS_PATH.exists():
        print("FAIL: standards.json or formula_contracts.json missing")
        return 2
    standards = {s["standard_id"]: s for s in json.loads(STANDARDS_PATH.read_text(encoding="utf-8")).get("standards", [])}
    formulas  = {f["formula_id"]: f for f in json.loads(FORMULAS_PATH.read_text(encoding="utf-8")).get("formulas", [])}

    files = _collect_edge_fn_files()
    findings = []
    metric_hits = 0
    standards_cited = 0
    metric_uncited = 0
    files_scanned = 0

    for p in files:
        files_scanned += 1
        text = _strip_js_comments(p.read_text(encoding="utf-8", errors="replace"))
        bodies = _find_prompt_bodies(text)
        if not bodies:
            continue
        for line_no, body in bodies:
            for pat, fid in METRIC_KEYWORDS.items():
                if not re.search(pat, body, re.IGNORECASE):
                    continue
                metric_hits += 1
                f = formulas.get(fid) or {}
                sid = f.get("standard_id", "")
                std = standards.get(sid) or {}
                short_name = std.get("short_name", "")
                if not short_name:
                    continue
                # Does the prompt body cite the short_name (or a recognisable substring)?
                cited = (short_name in body) or (sid.replace("_", " ").lower() in body.lower())
                if cited:
                    standards_cited += 1
                else:
                    metric_uncited += 1
                    findings.append({
                        "file":        p.relative_to(ROOT).as_posix(),
                        "line":        line_no,
                        "metric_hit":  pat,
                        "formula_id":  fid,
                        "should_cite": short_name,
                        "snippet":     body.strip().replace("\n", " ")[:160],
                    })

    report = {
        "summary": {
            "files_scanned":   files_scanned,
            "metric_hits":     metric_hits,
            "standards_cited": standards_cited,
            "metric_uncited":  metric_uncited,
        },
        "findings": findings,
    }

    (ROOT / "ai_prompt_standards_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    md = ["# AI Prompt Standards Audit (Tier B grounding check)\n",
          "Edge-fn prompts that mention a registered metric should cite the",
          "metric's canonical standard short_name. Without that, AI",
          "explanations drift from the deterministic calc's contract.\n",
          "## Summary\n",
          f"- Files scanned:      **{report['summary']['files_scanned']}**",
          f"- Metric mentions:    **{report['summary']['metric_hits']}**",
          f"- Cite the standard:  **{report['summary']['standards_cited']}** ✅",
          f"- Mention without cite: **{report['summary']['metric_uncited']}** ⚠️",
          ""]
    if findings:
        md.append(f"## Mentions missing standard citation ({len(findings)})\n")
        md.append("| File | Line | Metric | Should cite | Snippet |")
        md.append("|---|---:|---|---|---|")
        for r in findings[:40]:
            md.append(f"| `{r['file']}` | {r['line']} | `{r['metric_hit']}` | `{r['should_cite']}` | {r['snippet'][:80].replace('|', '\\|')} |")
        if len(findings) > 40:
            md.append(f"| ... +{len(findings) - 40} more | | | | |")
    (ROOT / "ai_prompt_standards_report.md").write_text("\n".join(md), encoding="utf-8")

    print("AI Prompt Standards Audit (Tier B grounding)")
    print(f"  files scanned:       {report['summary']['files_scanned']}")
    print(f"  metric mentions:     {report['summary']['metric_hits']}")
    print(f"  cite the standard:   {report['summary']['standards_cited']}")
    print(f"  uncited mentions:    {report['summary']['metric_uncited']}")
    # Informational — always pass; the report is the punch list
    return 0


if __name__ == "__main__":
    sys.exit(main())
