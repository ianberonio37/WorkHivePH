"""
Multi-Scenario-Per-Rule Sentinel (P1 roadmap 2026-05-26)
=========================================================
v0.5 sentinel achieved 100% behavioral coverage — every rule has ≥1 test.
This sentinel raises the bar: TIER 1 validators must have ≥2 tests per
rule (happy path + at least one edge case), so a single brittle assertion
isn't the only thing standing between a bug and prod.

Definition of TIER 1: any validator listed in TIER_1 below. Currently
hand-curated; future work can pull from SEVERITY_RANK == "blocker" once
all validators declare severity.

For each TIER 1 rule with <2 test names anchored to it, this sentinel
writes a proposal to sentinel_drafts.md so the user can pick which edge
scenario to author.

Inputs:
  SENTINEL_REGISTRY.json
  tests/*.spec.ts                 (greps for `test('<check_name>: ...'`)
  validate_*.py                   (greps for CHECK_NAMES = [...])

Exit codes:
  0  every TIER 1 rule has ≥2 anchored tests
  1  one or more TIER 1 rules have <2 anchored tests (proposals written)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
DRAFTS = ROOT / "sentinel_drafts.md"
REPORT = ROOT / "sentinel_multi_scenario_report.json"

# Hand-curated TIER 1 validators — these are the rules whose failure is
# customer-visible within minutes. Expand over time.
TIER_1 = {
    "truth_view_signal_trust",
    "truth_view_contract",
    "envelope_conformance",
    "health_endpoint",
    "render_budget",
    "rls_open_policy",
    "rls_readiness",
    "hive_state_consistency",
    "hive_quota",
    "auth_boundary",
    "tenant_boundary",
    "phantom_columns",
    "phantom_captures",
    "edge_response_contract",
    "groq_fallback",
    "ai_chain_mirror",
    "ai_companion_safety",
    "canonical_anchor",
    "canonical_sources",
}

TEST_NAME_RE = re.compile(r"""test\(\s*['"`]([a-z0-9_]+):""", re.IGNORECASE)
CHECK_NAMES_RE = re.compile(r"^CHECK_NAMES\s*=\s*\[([^\]]+)\]", re.MULTILINE)


def collect_validator_rules() -> dict[str, list[str]]:
    """Return {validator_id: [check_name, ...]} for every TIER 1 validator."""
    out: dict[str, list[str]] = {}
    for py in sorted(ROOT.glob("validate_*.py")):
        stem = py.stem.replace("validate_", "")
        if stem not in TIER_1: continue
        text = py.read_text(encoding="utf-8", errors="replace")
        m = CHECK_NAMES_RE.search(text)
        if not m:
            # If the validator hasn't declared CHECK_NAMES, treat its stem
            # as the single check name (matches sentinel v0.5 behavior).
            out[stem] = [stem]
            continue
        raw = m.group(1)
        # Strip Python `# ...` comments before splitting on commas so the
        # validator's inline `# L1` / `# L2` notes don't leak into check_name
        # entries. Then strip per-name surrounding whitespace + quotes.
        cleaned = re.sub(r"#[^\n]*", "", raw)
        names = [n.strip().strip("'").strip('"').strip() for n in cleaned.split(",") if n.strip()]
        out[stem] = [n for n in names if n and not n.startswith("#")]
    return out


def collect_test_anchors() -> dict[str, list[str]]:
    """Return {check_name: [test_title, ...]} aggregated across all spec files."""
    out: dict[str, list[str]] = defaultdict(list)
    if not TESTS_DIR.exists(): return out
    for spec in sorted(TESTS_DIR.glob("journey-*.spec.ts")):
        text = spec.read_text(encoding="utf-8", errors="replace")
        for m in TEST_NAME_RE.finditer(text):
            cn = m.group(1).lower()
            out[cn].append(spec.name)
    return out


def main() -> int:
    rules     = collect_validator_rules()
    anchors   = collect_test_anchors()

    gaps = []
    for vid, names in rules.items():
        for name in names:
            hits = anchors.get(name.lower(), [])
            if len(hits) < 2:
                gaps.append({
                    "validator": vid,
                    "check":     name,
                    "anchors":   hits,
                    "shortfall": 2 - len(hits),
                })

    REPORT.write_text(json.dumps({"gaps": gaps, "tier_1_count": len(rules)}, indent=2), encoding="utf-8")

    if not gaps:
        print("\033[92mPASS: every TIER 1 rule has ≥2 anchored tests.\033[0m")
        return 0

    # Append a drafts section.
    lines = [
        "",
        "# Multi-Scenario Sentinel — proposed edge scenarios",
        "",
        f"{len(gaps)} TIER 1 rule(s) currently have <2 anchored tests:",
        "",
    ]
    for g in gaps:
        lines += [
            f"## `{g['check']}` (validator: `{g['validator']}`)",
            f"- Current anchors: {g['anchors'] or 'NONE'}",
            f"- Suggested second scenario:",
            f"  - **Edge:** add a test that exercises the FAILURE path of `{g['check']}`",
            f"  - **File:** `tests/journey-{g['validator'].replace('_', '-')}.spec.ts`",
            f"  - **Pattern:**",
            f"    ```ts",
            f"    test('{g['check']}: rejects when invariant violated', async ({{ whPage }}) => {{",
            f"      // seed a violation, navigate, assert the surface degrades safely",
            f"    }});",
            f"    ```",
            "",
        ]

    # Atomically append to sentinel_drafts.md (create if missing).
    existing = DRAFTS.read_text(encoding="utf-8") if DRAFTS.exists() else ""
    DRAFTS.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")
    print(f"\033[93mFAIL: {len(gaps)} TIER 1 rule(s) need a second test. Drafts appended to sentinel_drafts.md.\033[0m")
    return 1


if __name__ == "__main__":
    sys.exit(main())
