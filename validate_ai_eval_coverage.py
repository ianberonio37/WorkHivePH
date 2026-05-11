"""
AI Evaluation Coverage -- WorkHive Platform
=============================================
The missing Evaluation node from the Agentic RAG stack. WorkHive has 21
gates that check AI infrastructure (rate gates, PII, gateway routing,
memory integrity, etc.) but ZERO that check AI ANSWER QUALITY.

This gate is forward-looking: it ratchets adoption of an eval registry
without requiring the eval pipeline to be running. The shape:

  * `evals/canonical_questions.json` -- per-agent fixtures of
    {question, expected_keywords, expected_shape}
  * Each agent in ai-gateway AGENT_ROUTES needs ≥3 fixtures.
  * A cron job is registered to run evals daily/weekly.
  * Results land in `ai_quality_log` table (future migration).

Layer 1 -- Canonical-questions registry present                          [WARN]
  Either `evals/canonical_questions.json` exists OR a migration
  declares the `ai_eval_canonical_questions` table. Without one,
  no eval framework exists.

Layer 2 -- Per-agent fixture coverage                                    [WARN]
  Every agent in the ai-gateway AGENT_ROUTES registry should have
  at least MIN_FIXTURES_PER_AGENT canonical questions. Agents
  without fixtures cannot be regression-tested.

Layer 3 -- Eval cron job registered                                      [WARN]
  A pg_cron job (or scheduled-agents entry) should run evals on a
  recurring basis. Without it, the registry is decorative.

Layer 4 -- Eval runner edge fn exists + writes to ai_quality_log         [WARN]
  The cron registered in Layer 3 calls `/ai-eval-runner`. If that
  edge fn doesn't exist, the cron is a no-op (404 on each call) and
  ai_quality_log stays empty. This layer verifies the runner is
  present on disk and writes to the log table. Freshness of runs
  itself is best surfaced from the dashboard (validators can't hit
  live DB).

Skills consulted: ai-engineer (eval patterns, LLM-as-judge), architect
(ratchet vs blocker for forward-looking gates), qa-tester (golden-set
discipline transferred from feature testing to AI testing).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")
GATEWAY_FILE   = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
EVAL_REGISTRY_FILE = os.path.join("evals", "canonical_questions.json")
MIN_FIXTURES_PER_AGENT = 3

# Per-agent exemptions. Each entry needs a one-line justification.
# DEFERRED entries: agent is routed but fixtures are not yet written.
# Tracked in PRODUCTION_FIXES under the AI Evaluation Coverage entry.
EVAL_DEFERRED: dict[str, str] = {
    # 2026-05-11: 3 canonical fixtures per agent SHIPPED in
    # evals/canonical_questions.json. All 6 agents pass L2.
    # Closes PRODUCTION_FIXES #52 Phase A.
}

# L3 cron allowlist. 2026-05-11: ai_quality_log table + ai-eval-daily
# cron shipped in 20260511000006. Per-agent fixtures still need to be
# written into evals/canonical_questions.json (EVAL_DEFERRED entries below).
EVAL_CRON_DEFERRED = False


# Parse agents from ai-gateway AGENT_ROUTES.
AGENT_ROUTES_RE = re.compile(
    r"""const\s+AGENT_ROUTES\s*:\s*Record<string,\s*\{[^}]*\}>\s*=\s*\{(?P<body>[\s\S]*?)\n\};""",
)
ROUTE_KEY_RE = re.compile(r"""['"`](?P<agent>[a-z0-9_-]+)['"`]\s*:\s*\{""")


def parse_routed_agents() -> list[str]:
    src = read_file(GATEWAY_FILE) or ""
    m = AGENT_ROUTES_RE.search(src)
    if not m:
        return []
    return [rm.group("agent") for rm in ROUTE_KEY_RE.finditer(m.group("body"))]


def load_eval_registry() -> dict[str, list[dict]]:
    """Return {agent_id: [fixture, ...]}.

    Tries the JSON file first; if absent, falls back to scanning
    migrations for `INSERT INTO ai_eval_canonical_questions`.
    """
    out: dict[str, list[dict]] = defaultdict(list)
    if os.path.isfile(EVAL_REGISTRY_FILE):
        try:
            raw = json.load(open(EVAL_REGISTRY_FILE, encoding="utf-8"))
        except Exception:
            return out
        if isinstance(raw, dict):
            for agent, fixtures in raw.items():
                if isinstance(fixtures, list):
                    out[agent] = fixtures
        return out
    # Fallback: scan migrations for INSERTs into the eval table.
    insert_re = re.compile(
        r"""INSERT\s+INTO\s+(?:public\.)?ai_eval_canonical_questions
            \s*\([^)]*\)\s*VALUES\s*([\s\S]*?);""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in insert_re.finditer(sql):
            # Best-effort: count agent_id occurrences in the VALUES list.
            for am in re.finditer(r"""['"]([a-z0-9_-]+)['"]\s*,""", m.group(1)):
                out[am.group(1)].append({"source": path})
    return out


def eval_table_present() -> bool:
    """True if the migration set declares ai_eval_canonical_questions."""
    table_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?"?ai_eval_canonical_questions"?\s*\(""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if table_re.search(sql):
            return True
    return False


def eval_cron_present() -> bool:
    """True if any migration schedules an eval-related cron job."""
    needle_re = re.compile(
        r"""cron\.schedule\s*\(\s*['"]([^'"]*eval[^'"]*)['"]""",
        re.IGNORECASE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if needle_re.search(sql):
            return True
    return False


# -- Layer 1: Registry present --------------------------------------------

def check_registry_present() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    json_present  = os.path.isfile(EVAL_REGISTRY_FILE)
    table_present = eval_table_present()
    report.append({
        "json_present":  json_present,
        "table_present": table_present,
    })
    if json_present or table_present:
        return issues, report
    issues.append({
        "check": "registry_present", "skip": True,
        "reason": (
            f"No eval registry found. Create either "
            f"`{EVAL_REGISTRY_FILE}` (JSON, format: {{agent_id: [fixtures]}}) "
            f"or add a migration declaring the "
            f"`ai_eval_canonical_questions` table. Without a registry, "
            f"AI quality regressions are invisible until users complain."
        ),
    })
    return issues, report


# -- Layer 2: Per-agent fixture coverage ----------------------------------

def check_fixture_coverage() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    registry = load_eval_registry()
    routed = parse_routed_agents()
    for agent in routed:
        n = len(registry.get(agent, []))
        report.append({"agent": agent, "n_fixtures": n})
        if n >= MIN_FIXTURES_PER_AGENT:
            continue
        if agent in EVAL_DEFERRED:
            continue
        issues.append({
            "check": "fixture_coverage", "skip": True,
            "reason": (
                f"Agent '{agent}' has {n} canonical question(s) "
                f"(needs >={MIN_FIXTURES_PER_AGENT}). Add fixtures to "
                f"`{EVAL_REGISTRY_FILE}` under agent_id='{agent}', or "
                f"list '{agent}' in EVAL_DEFERRED with a justification "
                f"(e.g., 'not user-facing; no quality regression surface')."
            ),
        })
    return issues, report


# -- Layer 3: Eval cron job registered ------------------------------------

def check_cron_registered() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    present = eval_cron_present()
    report.append({
        "eval_cron_present": present,
        "deferred":          EVAL_CRON_DEFERRED,
    })
    if present:
        return issues, report
    if EVAL_CRON_DEFERRED:
        return issues, report
    issues.append({
        "check": "cron_registered", "skip": True,
        "reason": (
            f"No pg_cron job mentioning 'eval' found in migrations. "
            f"The registry is decorative without a recurring runner. "
            f"Schedule a daily job: `cron.schedule('ai-eval-daily', "
            f"'0 3 * * *', $$ SELECT net.http_post(...) $$);` "
            f"Or set EVAL_CRON_DEFERRED=True with a justification."
        ),
    })
    return issues, report


EVAL_RUNNER_FILE = os.path.join("supabase", "functions", "ai-eval-runner", "index.ts")


# -- Layer 4: Eval runner fn exists + writes ai_quality_log -------------

def check_quality_log() -> tuple[list[dict], list[dict]]:
    """Verify (a) ai_quality_log table exists, (b) ai-eval-runner edge fn
    exists, (c) the runner contains an insert into ai_quality_log.
    Without (b) or (c) the cron scheduled in L3 is decorative."""
    issues: list[dict] = []
    report: list[dict] = []
    # (a) table presence
    table_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?"?ai_quality_log"?\s*\(""",
        re.IGNORECASE | re.VERBOSE,
    )
    table_present = False
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if table_re.search(sql):
            table_present = True
            break
    # (b) runner fn present
    runner_present = os.path.isfile(EVAL_RUNNER_FILE)
    runner_writes_log = False
    if runner_present:
        src = read_file(EVAL_RUNNER_FILE) or ""
        runner_writes_log = bool(
            re.search(r"""\.from\(\s*['"]ai_quality_log['"]\s*\)\s*\.insert""", src)
        )
    report.append({
        "ai_quality_log_table_present": table_present,
        "runner_fn_present":            runner_present,
        "runner_writes_to_log":         runner_writes_log,
    })
    if not runner_present:
        issues.append({
            "check": "quality_log", "skip": True,
            "reason": (
                f"ai-eval-runner edge fn not found at "
                f"{EVAL_RUNNER_FILE}. The L3 cron calls this endpoint; "
                f"without it cron runs are 404s and ai_quality_log "
                f"never accumulates rows. Create the runner."
            ),
        })
    elif not runner_writes_log:
        issues.append({
            "check": "quality_log", "skip": True,
            "reason": (
                f"ai-eval-runner exists but does not insert into "
                f"ai_quality_log. The eval scores must be persisted for "
                f"the dashboard to surface regressions."
            ),
        })
    return issues, report


# -- Runner --------------------------------------------------------------

CHECK_NAMES = [
    "registry_present",
    "fixture_coverage",
    "cron_registered",
    "quality_log",
]
CHECK_LABELS = {
    "registry_present": "L1  Eval registry present (JSON file or migration table)       [WARN]",
    "fixture_coverage": "L2  Every routed agent has >=3 canonical fixtures              [WARN]",
    "cron_registered":  "L3  Eval cron job scheduled in migrations                       [WARN]",
    "quality_log":      "L4  ai-eval-runner fn exists + writes to ai_quality_log         [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAI Evaluation Coverage (4-layer)"))
    print("=" * 60)

    routed = parse_routed_agents()
    print(f"  {len(routed)} routed agent(s) (EVAL_DEFERRED={len(EVAL_DEFERRED)}).\n")

    l1_issues, l1_report = check_registry_present()
    l2_issues, l2_report = check_fixture_coverage()
    l3_issues, l3_report = check_cron_registered()
    l4_issues, l4_report = check_quality_log()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l2_report:
        print(f"\n{bold('PER-AGENT FIXTURE COVERAGE (informational)')}")
        print("  " + "-" * 56)
        for r in l2_report:
            print(f"  {r['agent']:<32}  fixtures={r['n_fixtures']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":         "ai_eval_coverage",
        "total_checks":      total,
        "passed":            n_pass,
        "warned":            n_warn,
        "failed":            n_fail,
        "n_routed_agents":   len(routed),
        "registry_present":  l1_report,
        "fixture_coverage":  l2_report,
        "cron_registered":   l3_report,
        "quality_log":       l4_report,
        "issues":            [i for i in all_issues if not i.get("skip")],
        "warnings":          [i for i in all_issues if i.get("skip")],
    }
    with open("ai_eval_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
