"""
Hierarchical Period Summaries Validator (Phase 2 of AGENTIC_RAG_ROADMAP.md)
==========================================================================
Forward-only L0 ratchet locking the offline rollup that pre-digests
maintenance history into Daily → Weekly → Monthly → Quarterly → Yearly
summaries. This is the table the agentic-rag-loop Retriever pulls from
for any time-bound question instead of dumping raw logbook rows.

  H01  Migration creates canonical_period_summaries with all 5 levels CHECK
  H02  Migration enables RLS + has service-role-only insert/update
  H03  Edge function file exists
  H04  Edge fn declares all 5 levels (day/week/month/quarter/year)
  H05  Aggregator computes failure_count + mtbf_days + mttr_h + downtime_h
  H06  Aggregator filters to "Breakdown / Corrective" maintenance_type only
  H07  FREE-TIER ONLY (no paid Claude/OpenAI tier)
  H08  Uses callAI from _shared/ai-chain.ts
  H09  Hive-scoped reads (.eq("hive_id", ...))
  H10  Row cap enforced (.limit on logbook fetch)
  H11  Empty-period short-circuit (no LLM call when row_count == 0)
  H12  Upsert with onConflict on (hive_id, asset_tag, level, period_start)
  H13  4-place sync: config.toml registration
  H14  4-place sync: deploy-functions.ps1 line
  H15  4-place sync: validate_edge_contracts ALL_FUNCTIONS membership
  H16  4-place sync: validate_edge_contracts REQUIRED_FIELDS membership
  H17  No em dashes in any system prompt
  H18  logAICost called for the digest call
"""
from __future__ import annotations
import os, sys, re, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

EDGE_FN_PATH = os.path.join("supabase", "functions", "hierarchical-summarizer", "index.ts")
CONFIG_TOML  = os.path.join("supabase", "config.toml")
DEPLOY_PS1   = "deploy-functions.ps1"
EDGE_CONTRACT = "validate_edge_contracts.py"
MIGRATIONS    = os.path.join("supabase", "migrations")

PAID_MODELS = [r"\bhaiku\b", r"\bsonnet\b", r"\bopus\b", r"claude-3", r"claude-4", r"gpt-4"]


def _read_fn() -> str:
    return read_file(EDGE_FN_PATH) or ""


def check_migration() -> list[dict]:
    matches = glob.glob(os.path.join(MIGRATIONS, "*canonical_period_summaries*.sql"))
    issues = []
    if not matches:
        return [{"check": "migration", "reason": "No migration matching *canonical_period_summaries*.sql"}]
    src = read_file(matches[0]) or ""
    if "CREATE TABLE" not in src.upper() or "canonical_period_summaries" not in src:
        issues.append({"check": "migration", "reason": "Migration does not CREATE TABLE canonical_period_summaries"})
    for lvl in ("'day'", "'week'", "'month'", "'quarter'", "'year'"):
        if lvl not in src:
            issues.append({"check": "migration_levels", "reason": f"Missing level CHECK value: {lvl}"})
    if "ENABLE ROW LEVEL SECURITY" not in src.upper():
        issues.append({"check": "migration_rls", "reason": "Missing ENABLE ROW LEVEL SECURITY"})
    if "WITH CHECK (false)" not in src and "WITH CHECK ( false )" not in src:
        issues.append({"check": "migration_rls", "reason": "Insert policy must reject all non-service-role writes (WITH CHECK (false))"})
    return issues


def check_fn_file() -> list[dict]:
    if not os.path.isfile(EDGE_FN_PATH):
        return [{"check": "fn_file", "reason": f"{EDGE_FN_PATH} not found"}]
    return []


def check_levels_declared(src: str) -> list[dict]:
    if not re.search(r'LEVELS\s*=\s*\[\s*"day"\s*,\s*"week"\s*,\s*"month"\s*,\s*"quarter"\s*,\s*"year"', src):
        return [{"check": "levels_declared", "reason": "LEVELS const must list day/week/month/quarter/year in order"}]
    return []


def check_aggregator(src: str) -> list[dict]:
    issues = []
    for key in ("failure_count", "mtbf_days", "mttr_h", "downtime_h"):
        if key not in src:
            issues.append({"check": "aggregator", "reason": f"Aggregator output missing '{key}'"})
    return issues


def check_corrective_filter(src: str) -> list[dict]:
    if 'maintenance_type === "Breakdown / Corrective"' not in src:
        return [{"check": "corrective_filter", "reason": 'MTBF/MTTR aggregation must filter maintenance_type === "Breakdown / Corrective" per data-engineer skill'}]
    return []


def check_free_tier(src: str) -> list[dict]:
    issues = []
    low = src.lower()
    for pat in PAID_MODELS:
        if re.search(pat, low):
            issues.append({"check": "free_tier", "reason": f"Forbidden paid-model reference matched /{pat}/"})
    return issues


def check_uses_callai(src: str) -> list[dict]:
    if 'callAI' not in src:
        return [{"check": "uses_callai", "reason": "Must import + call callAI from _shared/ai-chain.ts"}]
    if re.search(r'fetch\(\s*["\']https?://api\.(groq|openai|anthropic|cerebras|sambanova|deepseek)\.com', src):
        return [{"check": "uses_callai", "reason": "Raw fetch() to provider URL detected — every LLM call must route through callAI"}]
    return []


def check_hive_scoping(src: str) -> list[dict]:
    if not re.search(r'\.eq\(\s*"hive_id"', src):
        return [{"check": "hive_scoping", "reason": '.eq("hive_id", ...) missing on logbook fetch'}]
    return []


def check_row_cap(src: str) -> list[dict]:
    if "ROW_CAP" not in src:
        return [{"check": "row_cap", "reason": "ROW_CAP constant missing"}]
    if not re.search(r"\.limit\(\s*ROW_CAP\s*\)", src):
        return [{"check": "row_cap", "reason": "Logbook fetch must apply .limit(ROW_CAP)"}]
    return []


def check_empty_short_circuit(src: str) -> list[dict]:
    # Look for "if (summary.row_count === 0)" or "row_count === 0" guard before callAI in buildDigest.
    if not re.search(r"row_count\s*===\s*0", src):
        return [{"check": "empty_short_circuit", "reason": "Empty period must short-circuit (skip LLM call when row_count === 0)"}]
    return []


def check_upsert_conflict(src: str) -> list[dict]:
    if 'onConflict' not in src:
        return [{"check": "upsert_conflict", "reason": "Upsert must specify onConflict for idempotent rollup"}]
    if 'hive_id,asset_tag,level,period_start' not in src.replace(' ', ''):
        return [{"check": "upsert_conflict", "reason": "onConflict must cover (hive_id, asset_tag, level, period_start) unique constraint"}]
    return []


def check_config_toml() -> list[dict]:
    src = read_file(CONFIG_TOML) or ""
    if "[functions.hierarchical-summarizer]" not in src:
        return [{"check": "config_toml", "reason": "[functions.hierarchical-summarizer] missing in supabase/config.toml"}]
    return []


def check_deploy_ps1() -> list[dict]:
    src = read_file(DEPLOY_PS1) or ""
    if "hierarchical-summarizer" not in src:
        return [{"check": "deploy_ps1", "reason": "deploy-functions.ps1 missing hierarchical-summarizer line"}]
    return []


def check_edge_contracts() -> list[dict]:
    src = read_file(EDGE_CONTRACT) or ""
    issues = []
    if '"hierarchical-summarizer"' not in src:
        issues.append({"check": "edge_contracts_all", "reason": "hierarchical-summarizer missing from ALL_FUNCTIONS"})
    if '"hierarchical-summarizer":' not in src:
        issues.append({"check": "edge_contracts_required", "reason": "hierarchical-summarizer missing from REQUIRED_FIELDS"})
    return issues


def check_no_em_dashes(src: str) -> list[dict]:
    prompts = re.findall(r"const\s+\w+_SYSTEM\s*=\s*`([^`]*)`", src, re.DOTALL)
    issues = []
    for i, p in enumerate(prompts):
        if "—" in p:
            issues.append({"check": "no_em_dashes", "reason": f"System prompt #{i} contains an em dash (U+2014)"})
    return issues


def check_cost_log(src: str) -> list[dict]:
    if 'logAICost' not in src:
        return [{"check": "cost_log", "reason": "logAICost not imported/called"}]
    return []


CHECKS = [
    ("migration",                      "H01-H02 Migration + 5 levels + RLS",                check_migration),
    ("fn_file",                        "H03 Edge fn file exists",                            check_fn_file),
    ("levels_declared",                "H04 5 levels declared (day/week/month/quarter/year)", lambda: check_levels_declared(_read_fn())),
    ("aggregator",                     "H05 Aggregator outputs failure_count + mtbf_days + mttr_h + downtime_h", lambda: check_aggregator(_read_fn())),
    ("corrective_filter",              "H06 MTBF/MTTR filtered to Breakdown/Corrective only", lambda: check_corrective_filter(_read_fn())),
    ("free_tier",                      "H07 FREE-TIER ONLY (no paid models)",                lambda: check_free_tier(_read_fn())),
    ("uses_callai",                    "H08 Uses callAI from _shared/ai-chain.ts",           lambda: check_uses_callai(_read_fn())),
    ("hive_scoping",                   "H09 Hive scoping on every fetch",                    lambda: check_hive_scoping(_read_fn())),
    ("row_cap",                        "H10 ROW_CAP enforced on logbook fetch",              lambda: check_row_cap(_read_fn())),
    ("empty_short_circuit",            "H11 Empty period skips LLM call (row_count === 0)",  lambda: check_empty_short_circuit(_read_fn())),
    ("upsert_conflict",                "H12 Upsert with onConflict on unique key",           lambda: check_upsert_conflict(_read_fn())),
    ("config_toml",                    "H13 4-place sync: config.toml",                       check_config_toml),
    ("deploy_ps1",                     "H14 4-place sync: deploy-functions.ps1",              check_deploy_ps1),
    ("edge_contracts",                 "H15-H16 4-place sync: validate_edge_contracts.py",   check_edge_contracts),
    ("no_em_dashes",                   "H17 No em dashes in system prompts",                 lambda: check_no_em_dashes(_read_fn())),
    ("cost_log",                       "H18 logAICost called for digest",                    lambda: check_cost_log(_read_fn())),
]


def main() -> int:
    print("\033[1m\nHierarchical Period Summaries Validator (Phase 2 of AGENTIC_RAG_ROADMAP.md)\033[0m")
    print("=" * 70)
    print(f"  Scanning {EDGE_FN_PATH}")
    all_issues = []
    keys = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}
    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)
    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
