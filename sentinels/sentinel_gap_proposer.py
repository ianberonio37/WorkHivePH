"""sentinel_gap_proposer.py - v1 of Sentinel Architecture.

Reads the gap list from v0 (sentinel_coverage_report.json) and bundles each
gap into a prompt-ready context block. Output: sentinel_proposals.md - a
markdown report where each gap section contains:

  - Validator filename + label + checks
  - Excerpt of validator source (so the LLM sees the actual rule)
  - Likely related HTML page (so the LLM sees the surface to test)
  - A pre-formatted LLM prompt ready to paste into /sentinel-review

v1 is deterministic. No LLM call - pure context bundling. The LLM call
happens in v2 (/sentinel-review slash command) which consumes this file.

See SENTINEL_ARCHITECTURE.md.
"""

import sys
import json
import re
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_REPORT = ROOT / "sentinel_coverage_report.json"
PROPOSALS_FILE = ROOT / "sentinel_proposals.md"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

MAX_VALIDATOR_EXCERPT_LINES = 80
MAX_HTML_EXCERPT_LINES = 60


def find_related_html(tokens: list) -> Path | None:
    """Look for <token>.html at project root that matches any validator token."""
    for token in tokens:
        candidates = [
            ROOT / f"{token}.html",
            ROOT / f"{token.replace('_', '-')}.html",
        ]
        for path in candidates:
            if path.exists():
                return path
    return None


def find_reference_spec(tokens: list) -> Path | None:
    """Look for an existing tests/journey-<token>.spec.ts to use as a pattern reference."""
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return None
    for token in tokens:
        for prefix in ("journey-", ""):
            candidate = tests_dir / f"{prefix}{token}.spec.ts"
            if candidate.exists():
                return candidate
    return None


def read_excerpt(path: Path, max_lines: int) -> str:
    """Read first N lines of a file, safely."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"(could not read {path.name}: {e})"
    lines = src.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n# ... ({len(lines) - max_lines} more lines)"
    return "\n".join(lines)


def extract_validator_rules(src: str) -> list:
    """Pull the rule-describing comments out of a validator source."""
    rules = []
    for m in re.finditer(
        r'#\s*[─-]+\s*Check\s*\d*[:\s]\s*([^\n]+)', src
    ):
        rules.append(m.group(1).strip())
    if not rules:
        for m in re.finditer(r'#\s*Check[^\n]+:\s*([^\n]+)', src, re.IGNORECASE):
            rules.append(m.group(1).strip())
    return rules


def build_prompt(gap: dict, validator_src: str, html_path: Path | None,
                 reference_spec: Path | None) -> str:
    """Build the LLM prompt block for one gap."""
    checks = gap.get("checks", [])
    label = gap.get("label", "")
    file_name = gap["file"]

    lines = [
        f"You are extending Layer 2 of the WorkHive platform.",
        f"",
        f"Layer 0 has a validator `{file_name}` that enforces: {label}",
        f"",
        f"Validator checks (each is a rule the platform must obey):",
    ]
    for c in checks:
        lines.append(f"  - {c}")
    if not checks:
        lines.append("  - (no named checks - see validator source for rules)")

    lines.append("")
    if html_path:
        lines.append(
            f"The likely surface to test is `{html_path.name}`. Read it for selectors, form IDs, and routes."
        )
    else:
        lines.append(
            "No obvious HTML surface matches this validator. It may be backend-only - if so, propose a DB-level integration test instead of a Playwright UI scenario, or mark as 'infrastructure (no Layer 2 proposal)'."
        )

    if reference_spec:
        lines.append(
            f"Use `tests/{reference_spec.name}` as a pattern reference (imports, fixtures, helpers)."
        )
    else:
        lines.append(
            "No reference spec for this topic. Follow the canonical Layer 2 pattern: import from `./_fixtures` + `./_helpers`, use `whPage` fixture, `testMarker` for DB cleanup, and `adminClient` for DB-level verification."
        )

    lines.append("")
    lines.append("Propose ONE Playwright scenario that exercises the most important untested rule.")
    lines.append("Output a single `test(...)` block. No prose.")

    return "\n".join(lines)


def render_gap_section(gap: dict, idx: int) -> str:
    """Render one full markdown section for a gap."""
    file_name = gap["file"]
    label = gap.get("label", "")
    tokens = gap.get("tokens", [])
    checks = gap.get("checks", [])

    validator_path = ROOT / file_name
    validator_src = validator_path.read_text(encoding="utf-8", errors="ignore") \
        if validator_path.exists() else ""
    validator_rules = extract_validator_rules(validator_src)
    validator_excerpt = read_excerpt(validator_path, MAX_VALIDATOR_EXCERPT_LINES) \
        if validator_path.exists() else "(source not found)"

    html_path = find_related_html(tokens)
    html_excerpt = ""
    if html_path:
        html_excerpt = read_excerpt(html_path, MAX_HTML_EXCERPT_LINES)

    reference_spec = find_reference_spec(tokens)

    prompt_block = build_prompt(gap, validator_src, html_path, reference_spec)

    parts = []
    parts.append(f"## Gap #{idx}: `{file_name}`\n")
    parts.append(f"**Label:** {label}  ")
    parts.append(f"**Tokens:** `{', '.join(tokens) if tokens else '(none)'}`  ")
    parts.append(f"**Checks ({len(checks)}):** {', '.join(checks) if checks else '_(no named checks)_'}  ")
    parts.append(f"**Likely surface:** {html_path.name if html_path else '_no HTML match - possibly infrastructure_'}  ")
    parts.append(f"**Pattern reference:** {reference_spec.name if reference_spec else '_no journey spec for this topic_'}\n")

    if validator_rules:
        parts.append("### Validator rules\n")
        for r in validator_rules:
            parts.append(f"- {r}")
        parts.append("")

    parts.append("<details><summary>Validator source excerpt</summary>\n")
    parts.append("```python")
    parts.append(validator_excerpt)
    parts.append("```\n</details>\n")

    if html_excerpt:
        parts.append(f"<details><summary>HTML surface excerpt - {html_path.name}</summary>\n")
        parts.append("```html")
        parts.append(html_excerpt)
        parts.append("```\n</details>\n")

    parts.append("### LLM prompt\n")
    parts.append("```")
    parts.append(prompt_block)
    parts.append("```\n")

    parts.append("---\n")
    return "\n".join(parts)


def render_check_gap_section(validator: dict, uncovered_checks: list, idx: int) -> str:
    """v1.4 - render a section for a validator showing each uncovered CHECK
    as a separate proposal target. The check name is the anchor: future tests
    should name the test after the check so the sentinel can match it."""
    file_name = validator["file"]
    label = validator.get("label", "")
    tokens = validator.get("tokens", [])
    covered = validator.get("covered_checks", [])
    matched_html = validator.get("matched_html") or "(no html match)"

    candidates = [t for t in tokens if t]
    html_path = find_related_html(candidates)
    reference_spec = find_reference_spec(candidates)

    parts = []
    parts.append(f"## Validator #{idx}: `{file_name}`  -  {len(uncovered_checks)} check(s) untested\n")
    parts.append(f"**Label:** {label[:100]}  ")
    parts.append(f"**Likely surface:** {matched_html}  ")
    parts.append(f"**Reference pattern:** "
                 f"{reference_spec.name if reference_spec else '_no journey spec for this topic_'}  ")
    if covered:
        parts.append(f"**Already covered ({len(covered)}):** "
                     f"`{'`, `'.join(c for c in covered if not c.startswith('(structural'))[:200]}`\n")
    else:
        parts.append("**Already covered:** _none_\n")

    parts.append(f"### Uncovered checks ({len(uncovered_checks)})\n")
    parts.append("Each line is one rule that needs a Playwright scenario. The check name")
    parts.append("(in backticks) MUST appear in the test() name so the next sentinel run")
    parts.append("matches the new scenario to the rule.\n")
    for check in uncovered_checks:
        parts.append(f"- `{check}`")
    parts.append("")

    parts.append("### LLM prompt\n")
    prompt_lines = [
        f"You are extending Layer 2 of the WorkHive platform.",
        f"",
        f"Validator `{file_name}` (target: `{matched_html}`) declares {len(uncovered_checks)}",
        f"rules that have NO Playwright test exercising them:",
    ]
    for c in uncovered_checks:
        prompt_lines.append(f"  - {c}")
    prompt_lines.append("")
    if html_path:
        prompt_lines.append(
            f"Read `{html_path.name}` for selectors, form IDs, routes."
        )
    if reference_spec:
        prompt_lines.append(
            f"Match the canonical pattern in `tests/{reference_spec.name}` "
            f"(imports from './_fixtures' + './_helpers', uses whPage + testMarker)."
        )
    else:
        prompt_lines.append(
            "No journey spec exists for this topic yet. Create "
            f"`tests/journey-{validator['tokens'][0] if validator['tokens'] else 'topic'}.spec.ts` "
            "following the canonical pattern."
        )
    prompt_lines.append("")
    prompt_lines.append("Propose ONE test() block per check above. Each test()'s name MUST")
    prompt_lines.append("start with the check name (e.g. `test('approval_channel_events: ...', ...)`)")
    prompt_lines.append("so the next sentinel run automatically marks the check as covered.")

    parts.append("```")
    parts.append("\n".join(prompt_lines))
    parts.append("```\n")

    parts.append("---\n")
    return "\n".join(parts)


def main():
    print()
    print(f"{BOLD}SENTINEL - GAP PROPOSER (v1){RESET}")
    print("─" * 60)

    if not COVERAGE_REPORT.exists():
        print(f"  {RED}sentinel_coverage_report.json not found.{RESET}")
        print(f"  Run `python sentinels/sentinel_coverage_map.py` first.")
        return 1

    report = json.loads(COVERAGE_REPORT.read_text(encoding="utf-8"))
    coverage_all = report.get("coverage", [])
    gaps = report.get("gaps", [])
    summary = report.get("summary", {})

    per_page_all = [c for c in coverage_all if c.get("category") == "per-page"]
    platform_wide_gaps = [g for g in gaps if g.get("category") == "platform-wide"]
    infra_gaps = [g for g in gaps if g.get("category") == "infrastructure"
                  or g.get("is_infrastructure", False)]

    check_gaps_by_validator = []
    total_uncovered_checks = 0
    for v in per_page_all:
        uncovered = [c for c in v.get("uncovered_checks", [])
                     if not c.startswith("(structural")]
        if uncovered:
            check_gaps_by_validator.append({"validator": v, "uncovered_checks": uncovered})
            total_uncovered_checks += len(uncovered)

    print(f"  Reading coverage from {COVERAGE_REPORT.name}")
    print(f"  Per-page validators with uncovered checks: {len(check_gaps_by_validator)}")
    print(f"  Total uncovered checks (CHECK-level gaps): {total_uncovered_checks}")
    print(f"  Platform-wide (will list):                  {len(platform_wide_gaps)}")
    print(f"  Infrastructure (will list):                 {len(infra_gaps)}")
    print()

    if not check_gaps_by_validator:
        print(f"  {GREEN}No check-level gaps! Every per-page check has a test.{RESET}")
        PROPOSALS_FILE.write_text(
            "# Sentinel Proposals\n\nNo check-level gaps. Behavioral coverage is 100%.\n",
            encoding="utf-8",
        )
        return 0

    md_lines = [
        "# Sentinel Proposals (v1.4 - check-level)",
        "",
        f"Generated for {total_uncovered_checks} uncovered CHECK(s) across "
        f"{len(check_gaps_by_validator)} per-page validators. Each check is one rule",
        "the platform should obey - and currently no Playwright spec exercises it.",
        "",
        f"**Check coverage:** {summary.get('check_coverage_pct', '?')}% "
        f"({summary.get('covered_per_page_checks', '?')} of {summary.get('total_per_page_checks', '?')} per-page checks - HONEST behavioral coverage)",
        f"**Topic coverage:** {summary.get('effective_coverage_pct', '?')}% "
        f"({summary.get('per_page_covered', '?')} of {summary.get('per_page_validators', '?')} per-page validators - loose, validator-level)",
        f"**Raw coverage:** {summary.get('validator_coverage_pct', '?')}% "
        f"({summary.get('covered_validators', '?')} of {summary.get('total_validators', '?')} validators)",
        "",
        "Each section below groups uncovered checks by validator. Use the per-check",
        "list as your test backlog - one scenario per check, not one scenario per",
        "validator. The check-name itself is the test-name anchor: include it in",
        "the new test() name so the next sentinel run picks up the match.",
        "",
        "Platform-wide and Infrastructure gaps are listed at the bottom for",
        "transparency - they don't need Playwright scenarios.",
        "",
        "---",
        "",
        "## Per-page CHECK-level gaps (the test backlog)",
        "",
    ]

    skipped_no_tokens = 0
    proposed = 0
    for i, entry in enumerate(check_gaps_by_validator, start=1):
        v = entry["validator"]
        if not v.get("tokens"):
            skipped_no_tokens += 1
            continue
        md_lines.append(render_check_gap_section(v, entry["uncovered_checks"], i))
        proposed += 1
        if i % 10 == 0:
            print(f"    bundled {i} / {len(check_gaps_by_validator)}")

    # Keep per_page_gaps for the footer summary (validators with ALL checks uncovered)
    per_page_gaps = [g for g in gaps if g.get("category") == "per-page"]

    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"## Platform-wide gaps ({len(platform_wide_gaps)})")
    md_lines.append("")
    md_lines.append("These validators scan ALL pages (LIVE_PAGES list, glob, etc.). Layer 0")
    md_lines.append("is the right enforcement layer because writing a Playwright scenario per")
    md_lines.append("page would just duplicate the validator with 50x the runtime.")
    md_lines.append("")
    for g in platform_wide_gaps:
        checks_n = len(g.get("checks", []))
        check_label = f"{checks_n} checks" if checks_n else "no named checks"
        md_lines.append(f"- `{g['file']}` ({check_label}) - {g.get('label', '')[:80]}")
    md_lines.append("")
    md_lines.append(f"## Infrastructure gaps ({len(infra_gaps)})")
    md_lines.append("")
    md_lines.append("These validators have no UI surface - they enforce backend / schema /")
    md_lines.append("edge function / configuration rules. Layer 0 is the right enforcement")
    md_lines.append("layer; no Playwright scenario is needed.")
    md_lines.append("")
    for g in infra_gaps:
        checks_n = len(g.get("checks", []))
        check_label = f"{checks_n} checks" if checks_n else "no named checks"
        md_lines.append(f"- `{g['file']}` ({check_label}) - {g.get('label', '')[:80]}")
    md_lines.append("")
    md_lines.append(f"_Generated {proposed} per-page proposal bundles. "
                    f"Skipped {skipped_no_tokens} with no extractable tokens. "
                    f"Tagged {len(platform_wide_gaps)} platform-wide and "
                    f"{len(infra_gaps)} infrastructure._")

    PROPOSALS_FILE.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"  {GREEN}Wrote {proposed} proposal bundles -> {PROPOSALS_FILE.name}{RESET}")
    if skipped_no_tokens:
        print(f"  {YELLOW}Skipped {skipped_no_tokens} gaps (no extractable tokens){RESET}")
    print()
    print(f"  Next: invoke `/sentinel-review` to have Claude draft scenarios from this file.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
