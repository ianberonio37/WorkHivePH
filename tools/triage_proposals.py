"""
Triage skill_rules_proposals.json -- score each LLM-proposed rule by:
  - severity (critical/high prioritized)
  - dedup vs manifest
  - regex compiles
  - what conformance % it produces when run against its scope
  - has triggered_by (more specific) vs no trigger (broader, riskier)

Output: ranked list of top candidates ready to merge, plus the ones to
reject. Human picks final inclusion -- this script does NOT auto-merge.
"""
from __future__ import annotations
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mine_skill_rules import SCOPE_RESOLVERS, _read_and_strip  # noqa: E402

ROOT          = Path(__file__).resolve().parent.parent
PROPOSALS     = ROOT / "skill_rules_proposals.json"
MANIFEST      = ROOT / "skill_rules_manifest.json"
TRIAGE_OUT    = ROOT / "skill_rules_triage_report.md"


def _compile(pattern: str, flag_str: str = "") -> re.Pattern | None:
    try:
        flags = 0
        if "i" in (flag_str or ""): flags |= re.IGNORECASE
        if "m" in (flag_str or ""): flags |= re.MULTILINE
        return re.compile(pattern, flags)
    except re.error:
        return None


def evaluate_rule(rule: dict) -> dict:
    """Run the rule's pattern against its scope, return match stats."""
    pattern = _compile(rule.get("pattern", ""), rule.get("pattern_flags", ""))
    trigger = _compile(rule.get("triggered_by", ""), rule.get("pattern_flags", "")) if rule.get("triggered_by") else None
    scope_name = rule.get("scope")
    resolver = SCOPE_RESOLVERS.get(scope_name)

    out = {"compiles": pattern is not None, "scope_valid": resolver is not None}
    if not pattern or not resolver:
        return out

    files = resolver()
    if not files:
        out["files_in_scope"] = 0
        return out

    in_scope_count = 0
    matched_count  = 0
    for path in files:
        text = _read_and_strip(path)
        if trigger and not trigger.search(text):
            continue
        in_scope_count += 1
        if pattern.search(text):
            matched_count += 1

    out["files_in_scope"]   = in_scope_count
    out["matched_count"]    = matched_count
    out["match_rate"]       = round(matched_count / in_scope_count, 3) if in_scope_count else 0

    polarity = rule.get("polarity", "convention")
    if polarity == "convention":
        out["conformance"] = out["match_rate"]
    else:  # anti_pattern -- compliant = NOT matching
        out["conformance"] = round(1 - out["match_rate"], 3)
    return out


def score(rule: dict, ev: dict) -> tuple[int, str]:
    """Return (score, reason). Higher = better candidate.
    Negative score = reject."""
    if not ev.get("compiles"):
        return (-10, "regex does not compile")
    if not ev.get("scope_valid"):
        return (-10, "unknown scope")
    if ev.get("files_in_scope", 0) == 0:
        return (-5, "no files in scope (or trigger matches nothing)")
    # All-or-nothing patterns produce a useless rule.
    conf = ev.get("conformance", 0)
    if conf in (0.0, 1.0):
        return (-3, f"conformance is {conf} -- pattern is all-or-nothing, not useful as a drift detector")

    sev = rule.get("severity", "info")
    sev_score = {"critical": 30, "high": 20, "medium": 10, "low": 3, "info": 1}.get(sev, 0)

    # Prefer rules with explicit triggered_by (more targeted, less noisy).
    trigger_bonus = 5 if rule.get("triggered_by") else 0

    # Sweet-spot conformance band (some drift but not everywhere).
    if 0.5 <= conf <= 0.95:
        sweetspot_bonus = 8
    elif 0.2 <= conf < 0.5 or 0.95 < conf < 1.0:
        sweetspot_bonus = 4
    else:
        sweetspot_bonus = 0

    # Penalty for very short patterns (almost certainly too broad).
    pat_len = len(rule.get("pattern", ""))
    short_penalty = -10 if pat_len < 10 else (-3 if pat_len < 20 else 0)

    return (sev_score + trigger_bonus + sweetspot_bonus + short_penalty,
            f"sev={sev}({sev_score}) trigger={'y' if rule.get('triggered_by') else 'n'}({trigger_bonus}) sweetspot({sweetspot_bonus}) patlen={pat_len}({short_penalty})")


def main() -> int:
    proposals = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    manifest  = json.loads(MANIFEST.read_text(encoding="utf-8"))
    existing_ids = {r["id"] for r in manifest["rules"]}

    all_rules = []
    for run in proposals["runs"]:
        for r in run.get("rules", []):
            if r.get("id") in existing_ids:
                continue  # dedup against manifest
            ev = evaluate_rule(r)
            s, reason = score(r, ev)
            r["_eval"] = ev
            r["_score"] = s
            r["_reason"] = reason
            all_rules.append(r)

    all_rules.sort(key=lambda r: -r["_score"])

    accepted = [r for r in all_rules if r["_score"] >= 25]
    borderline = [r for r in all_rules if 15 <= r["_score"] < 25]
    rejected = [r for r in all_rules if r["_score"] < 15]

    print(f"AI Extraction Triage Report")
    print(f"  total proposals (after manifest-dedup): {len(all_rules)}")
    print(f"  accepted (score >= 25):                 {len(accepted)}")
    print(f"  borderline (15-24):                     {len(borderline)}")
    print(f"  rejected (< 15):                        {len(rejected)}")
    print()
    print("Top 20 accepted candidates:")
    for r in accepted[:20]:
        ev = r["_eval"]
        conf = ev.get("conformance", "n/a")
        files = ev.get("files_in_scope", "n/a")
        print(f"  [{r['_score']:>3}] {r['id']:<60}  {r.get('severity',''):<8}  conf={conf}  files={files}")

    # Write a markdown report
    lines = ["# AI Extraction Triage Report", ""]
    lines.append(f"**Total proposals scored:** {len(all_rules)}")
    lines.append(f"**Accepted (score >= 25):** {len(accepted)}")
    lines.append(f"**Borderline (15-24):** {len(borderline)}")
    lines.append(f"**Rejected (< 15):** {len(rejected)}")
    lines.append("")
    lines.append("## Accepted -- ready to merge into manifest")
    lines.append("")
    lines.append("| Score | Rule ID | Sev | Conf | Files | Reason |")
    lines.append("|---:|---|---|---:|---:|---|")
    for r in accepted:
        ev = r["_eval"]
        conf = ev.get("conformance", "?")
        files = ev.get("files_in_scope", "?")
        sev = r.get("severity", "?")
        lines.append(f"| {r['_score']} | `{r['id']}` | {sev} | {conf} | {files} | {r.get('summary','')[:80]} |")
    lines.append("")
    lines.append("## Borderline -- review individually")
    lines.append("")
    for r in borderline[:30]:
        ev = r["_eval"]
        lines.append(f"- `{r['id']}` (score {r['_score']}, conf {ev.get('conformance','?')}): {r.get('summary','')[:100]}")
    TRIAGE_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nFull report: {TRIAGE_OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
