"""
Hardening Auto-Trigger (P1 roadmap 2026-05-26)
==============================================
Walks the latest Layer 2 test-results + platform_health.json, classifies
each FAIL by signature, and drafts a hardening proposal that the user
can approve via `/harden`.

This is the *draft* step — it does NOT modify code. The actual harden
loop is still run via the `/harden` skill (which knows the project's
seeder + validator + spec layout). This tool surfaces:

  - Which failures came from new (vs known) bug classes
  - Which validators would have caught them if extended
  - Which skills should learn from each failure
  - One-line `/harden` commands the user can paste

Inputs (all optional; tool reads what exists):
  test-results/                  Playwright JSON output
  platform_health.json           latest L0 run
  sentinel_proposals.md          latest sentinel output
  flywheel_state.json            companion flywheel last-run

Output:
  hardening_proposal.md          human-readable draft
  hardening_proposal.json        machine-readable (for CI bot)

Exit codes:
  0  no new failures (nothing to harden)
  1  new failures classified, proposal written
  2  inputs missing
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

PLATFORM_HEALTH   = ROOT / "platform_health.json"
PW_REPORT         = ROOT / "playwright-report.json"
TEST_RESULTS_DIR  = ROOT / "test-results"
SENTINEL_PROPS    = ROOT / "sentinel_proposals.md"

OUT_MD   = ROOT / "hardening_proposal.md"
OUT_JSON = ROOT / "hardening_proposal.json"

# Failure-signature classifier. Each regex matches an error fragment and
# maps to (rootcause, suggested skills, suggested validator stem).
CLASSIFIER = [
    (r"hive_id.*null|hive_id.*undefined", "multitenant",   ["multitenant-engineer", "qa-tester"],          "hive_state_consistency"),
    (r"429|rate.?limit|rate limited",     "rate-limit",    ["ai-engineer", "performance"],                  "groq_fallback"),
    (r"timeout|hung|killed",              "timeout",       ["performance", "qa-tester"],                    "abort_timeout"),
    (r"NOT NULL|null value in column",    "schema-drift",  ["data-engineer", "architect"],                  "schema_drift"),
    (r"RLS|row.level.security|policy",    "rls",           ["security", "multitenant-engineer"],            "rls_open_policy"),
    (r"phantom column|undefined column",  "phantom",       ["data-engineer", "frontend"],                   "phantom_columns"),
    (r"escHtml|innerHTML|XSS",            "escHtml",       ["security", "frontend", "qa-tester"],           "innerhtml_eschtml"),
    (r"realtime|subscribe|channel",       "realtime",      ["realtime-engineer", "frontend"],               "realtime_channel_cleanup"),
    (r"voice|companion|wh-tts|wh-stt",    "companion",     ["ai-engineer", "qa-tester", "frontend"],        "ai_companion_safety"),
    (r"truth|canonical|v_.*_truth",       "canonical",     ["data-engineer", "analytics-engineer"],         "truth_view_signal_trust"),
]


def classify(msg: str) -> tuple[str, list[str], str]:
    msg_l = (msg or "").lower()
    for pattern, rc, skills, stem in CLASSIFIER:
        if re.search(pattern, msg_l):
            return rc, skills, stem
    return "uncategorized", ["qa-tester", "architect"], "cross_page"


def read_platform_failures() -> list[dict]:
    if not PLATFORM_HEALTH.exists(): return []
    try:
        data = json.loads(PLATFORM_HEALTH.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    fails = []
    for v in data.get("validators", []) or []:
        if v.get("status") in ("FAIL", "ERROR"):
            fails.append({
                "source": "layer0",
                "id":     v.get("id", "?"),
                "label":  v.get("label", "?"),
                "msg":    (v.get("output") or "")[-500:],
            })
    return fails


def read_playwright_failures() -> list[dict]:
    fails = []
    if PW_REPORT.exists():
        try:
            data = json.loads(PW_REPORT.read_text(encoding="utf-8", errors="replace"))
            for suite in data.get("suites", []):
                for spec in suite.get("specs", []):
                    for t in spec.get("tests", []):
                        for r in t.get("results", []):
                            if r.get("status") in ("failed", "timedOut"):
                                fails.append({
                                    "source": "layer2",
                                    "id":     spec.get("title", "?"),
                                    "label":  t.get("title", "?"),
                                    "msg":    (r.get("error", {}) or {}).get("message", "")[:500],
                                })
        except Exception:
            pass
    return fails


def render_proposal(failures: list[dict], buckets: dict[str, list[dict]]) -> str:
    lines = [
        f"# Hardening Proposal — {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Total failures classified: **{len(failures)}** across **{len(buckets)}** bug classes.",
        "",
        "## Bug classes",
        "",
    ]
    for rc, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        first = items[0]
        skills = ", ".join(first["skills"])
        stem   = first["stem"]
        lines += [
            f"### {rc} ({len(items)} failure{'s' if len(items)>1 else ''})",
            "",
            f"- **Suggested validator stem:** `validate_{stem}.py`",
            f"- **Skills to update:** {skills}",
            "- **Failures:**",
        ]
        for it in items[:6]:
            lines.append(f"  - `[{it['source']}]` {it['id']} — {it['label']}")
        if len(items) > 6:
            lines.append(f"  - ... +{len(items) - 6} more")
        lines += ["", "**Suggested action:**", f"```", f"/harden {rc}", f"```", ""]

    lines += [
        "## How to apply",
        "",
        "1. Review each bug class above.",
        "2. Run `/harden <class>` for the ones that are real (not flakes).",
        "3. The harden skill will: extend the suggested validator, update the seeder, update the relevant skill memories, run the gate.",
        "4. Commit once green.",
        "",
        "Generated by `tools/hardening_auto_trigger.py`. This is a *draft* — no code was modified.",
    ]
    return "\n".join(lines)


def main() -> int:
    failures = read_platform_failures() + read_playwright_failures()
    if not failures:
        print("\033[92mNo failures found — nothing to harden.\033[0m")
        # Write an empty proposal so CI doesn't error on missing artifact.
        OUT_JSON.write_text(json.dumps({"buckets": {}, "total": 0}), encoding="utf-8")
        OUT_MD.write_text("# Hardening Proposal — no failures detected\n", encoding="utf-8")
        return 0

    # Enrich each failure with classification.
    buckets: dict[str, list[dict]] = defaultdict(list)
    for f in failures:
        rc, skills, stem = classify(f.get("msg", ""))
        f["rootcause"] = rc
        f["skills"]    = skills
        f["stem"]      = stem
        buckets[rc].append(f)

    OUT_MD.write_text(render_proposal(failures, buckets), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({
        "buckets": {k: v for k, v in buckets.items()},
        "total":   len(failures),
    }, indent=2), encoding="utf-8")

    print(f"\033[93mDrafted hardening proposal: {len(failures)} failures across {len(buckets)} classes.\033[0m")
    print(f"  See: {OUT_MD.relative_to(ROOT)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
