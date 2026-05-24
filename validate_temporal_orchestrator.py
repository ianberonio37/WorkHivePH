"""
Temporal RAG Orchestrator Validator (Phase 3 of AGENTIC_RAG_ROADMAP.md)
======================================================================
Forward-only L0 ratchet for the supervisor-worker temporal-RAG fan-out.

  T01  Edge fn file exists
  T02  decompose() function defined
  T03  3 granularities present (year/quarter/month)
  T04  Auto-granularity heuristic (3yr threshold + 6mo threshold)
  T05  MAX_PERIODS cap (<= 12)
  T06  MAX_PARALLEL cap (<= 5)
  T07  runBounded helper for bounded concurrency
  T08  Reads canonical_period_summaries (Phase 2 dependency)
  T09  Sub-agent + fold each call callAI
  T10  Sub-agent uses taskProfile=temporal_subagent (Phase 4 wired)
  T11  Fold uses taskProfile=temporal_fold (Phase 4 wired)
  T12  FREE-TIER ONLY (no paid model names)
  T13  Hive scoping on canonical_period_summaries fetch
  T14  Rate limit enforced BEFORE sub-agent fan-out
  T15  4-place sync: config.toml + deploy + edge_contracts ALL + REQUIRED
  T16  logAICost called for both sub-agent and fold
  T17  No em dashes in system prompts
"""
from __future__ import annotations
import os, sys, re

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FN_PATH = os.path.join("supabase", "functions", "temporal-rag-orchestrator", "index.ts")
CONFIG_TOML = os.path.join("supabase", "config.toml")
DEPLOY_PS1  = "deploy-functions.ps1"
EDGE_CONTRACT = "validate_edge_contracts.py"

PAID = [r"\bhaiku\b", r"\bsonnet\b", r"\bopus\b", r"claude-3", r"claude-4", r"gpt-4"]


def _read() -> str:
    return read_file(FN_PATH) or ""


def check_file_exists() -> list[dict]:
    if not os.path.isfile(FN_PATH):
        return [{"check": "file_exists", "reason": f"{FN_PATH} not found"}]
    return []


def check_decompose(src: str) -> list[dict]:
    if not re.search(r"function\s+decompose\s*\(", src):
        return [{"check": "decompose", "reason": "decompose() function missing"}]
    return []


def check_granularities(src: str) -> list[dict]:
    issues = []
    for g in ('"year"', '"quarter"', '"month"'):
        if g not in src:
            issues.append({"check": "granularities", "reason": f"Missing granularity {g}"})
    return issues


def check_auto_heuristic(src: str) -> list[dict]:
    # Match year-threshold (3*365 days)  AND  half-year threshold (180 days)
    has_3y  = re.search(r"3\s*\*\s*365", src) is not None
    has_180 = re.search(r"\b180\b", src) is not None
    if not (has_3y and has_180):
        return [{"check": "auto_heuristic", "reason": "Granularity='auto' must reference both 3*365 (year cutoff) and 180 (quarter cutoff) day thresholds"}]
    return []


def check_max_periods(src: str) -> list[dict]:
    m = re.search(r"MAX_PERIODS\s*=\s*(\d+)", src)
    if not m: return [{"check": "max_periods", "reason": "MAX_PERIODS constant missing"}]
    n = int(m.group(1))
    if n > 12: return [{"check": "max_periods", "reason": f"MAX_PERIODS = {n} exceeds 12 (TPM safety cap)"}]
    return []


def check_max_parallel(src: str) -> list[dict]:
    m = re.search(r"MAX_PARALLEL\s*=\s*(\d+)", src)
    if not m: return [{"check": "max_parallel", "reason": "MAX_PARALLEL constant missing"}]
    n = int(m.group(1))
    if n > 5: return [{"check": "max_parallel", "reason": f"MAX_PARALLEL = {n} exceeds 5 (TPM contention safety)"}]
    return []


def check_runbounded(src: str) -> list[dict]:
    if "runBounded" not in src:
        return [{"check": "runbounded", "reason": "runBounded helper missing — concurrent fan-out must be bounded"}]
    return []


def check_reads_summaries(src: str) -> list[dict]:
    if "canonical_period_summaries" not in src:
        return [{"check": "reads_summaries", "reason": "Must read from canonical_period_summaries (Phase 2 dependency)"}]
    return []


def check_callai_used(src: str) -> list[dict]:
    if "callAI" not in src:
        return [{"check": "callai_used", "reason": "callAI not imported/used"}]
    count = len(re.findall(r"\bawait\s+callAI\s*\(", src))
    if count < 2:
        return [{"check": "callai_used", "reason": f"Only {count} callAI invocations — need at least 2 (sub-agent + fold)"}]
    return []


def check_sub_taskprofile(src: str) -> list[dict]:
    if not re.search(r'taskProfile\s*:\s*"temporal_subagent"', src):
        return [{"check": "sub_taskprofile", "reason": 'Sub-agent callAI must pass taskProfile: "temporal_subagent"'}]
    return []


def check_fold_taskprofile(src: str) -> list[dict]:
    if not re.search(r'taskProfile\s*:\s*"temporal_fold"', src):
        return [{"check": "fold_taskprofile", "reason": 'Fold callAI must pass taskProfile: "temporal_fold"'}]
    return []


def check_free_tier(src: str) -> list[dict]:
    low = src.lower()
    issues = []
    for pat in PAID:
        if re.search(pat, low):
            issues.append({"check": "free_tier", "reason": f"Forbidden paid-model substring matched /{pat}/"})
    return issues


def check_hive_scoping(src: str) -> list[dict]:
    if not re.search(r'\.eq\(\s*"hive_id"', src):
        return [{"check": "hive_scoping", "reason": '.eq("hive_id", ...) missing on canonical_period_summaries fetch'}]
    return []


def check_rate_limit_first(src: str) -> list[dict]:
    if "checkRateLimit" not in src:
        return [{"check": "rate_limit", "reason": "checkRateLimit missing — no per-hive cap on fan-out"}]
    rl_pos = re.search(r"\bawait\s+checkRateLimit\s*\(", src)
    fan_pos = re.search(r"\bawait\s+runBounded\s*\(", src)
    if not rl_pos or not fan_pos or rl_pos.start() > fan_pos.start():
        return [{"check": "rate_limit", "reason": "checkRateLimit must be called BEFORE runBounded fan-out"}]
    return []


def check_4place_sync() -> list[dict]:
    cfg = read_file(CONFIG_TOML) or ""
    dep = read_file(DEPLOY_PS1) or ""
    ec  = read_file(EDGE_CONTRACT) or ""
    issues = []
    if "[functions.temporal-rag-orchestrator]" not in cfg:
        issues.append({"check": "sync_config", "reason": "config.toml missing [functions.temporal-rag-orchestrator]"})
    if "temporal-rag-orchestrator" not in dep:
        issues.append({"check": "sync_deploy", "reason": "deploy-functions.ps1 missing temporal-rag-orchestrator line"})
    if '"temporal-rag-orchestrator"' not in ec:
        issues.append({"check": "sync_ec_all", "reason": "validate_edge_contracts.py ALL_FUNCTIONS missing temporal-rag-orchestrator"})
    if '"temporal-rag-orchestrator":' not in ec:
        issues.append({"check": "sync_ec_required", "reason": "validate_edge_contracts.py REQUIRED_FIELDS missing temporal-rag-orchestrator"})
    return issues


def check_cost_log(src: str) -> list[dict]:
    if "logAICost" not in src:
        return [{"check": "cost_log", "reason": "logAICost not called"}]
    if len(re.findall(r"\blogAICost\s*\(", src)) < 2:
        return [{"check": "cost_log", "reason": "logAICost called fewer than 2 times — need sub-agent + fold"}]
    return []


def check_no_em_dashes(src: str) -> list[dict]:
    prompts = re.findall(r"const\s+\w+_SYSTEM\s*=\s*`([^`]*)`", src, re.DOTALL)
    issues = []
    for i, p in enumerate(prompts):
        if "—" in p:
            issues.append({"check": "no_em_dashes", "reason": f"System prompt #{i} contains an em dash"})
    return issues


CHECKS = [
    ("file_exists",       "T01 Edge fn file exists",                              check_file_exists),
    ("decompose",         "T02 decompose() function defined",                     lambda: check_decompose(_read())),
    ("granularities",     "T03 year + quarter + month granularities supported",   lambda: check_granularities(_read())),
    ("auto_heuristic",    "T04 Auto-granularity (3yr + 6mo thresholds)",          lambda: check_auto_heuristic(_read())),
    ("max_periods",       "T05 MAX_PERIODS cap <= 12",                            lambda: check_max_periods(_read())),
    ("max_parallel",      "T06 MAX_PARALLEL cap <= 5",                            lambda: check_max_parallel(_read())),
    ("runbounded",        "T07 runBounded helper for bounded concurrency",        lambda: check_runbounded(_read())),
    ("reads_summaries",   "T08 Reads canonical_period_summaries (Phase 2 dep)",   lambda: check_reads_summaries(_read())),
    ("callai_used",       "T09 callAI invoked at least 2x (sub-agent + fold)",    lambda: check_callai_used(_read())),
    ("sub_taskprofile",   "T10 Sub-agent uses taskProfile=temporal_subagent",     lambda: check_sub_taskprofile(_read())),
    ("fold_taskprofile",  "T11 Fold uses taskProfile=temporal_fold",              lambda: check_fold_taskprofile(_read())),
    ("free_tier",         "T12 FREE-TIER ONLY (no paid model names)",             lambda: check_free_tier(_read())),
    ("hive_scoping",      "T13 Hive scoping on summaries fetch",                  lambda: check_hive_scoping(_read())),
    ("rate_limit",        "T14 Rate limit BEFORE fan-out",                        lambda: check_rate_limit_first(_read())),
    ("sync",              "T15 4-place sync (config + deploy + ec all/required)", check_4place_sync),
    ("cost_log",          "T16 logAICost for both sub-agent and fold",            lambda: check_cost_log(_read())),
    ("no_em_dashes",      "T17 No em dashes in system prompts",                   lambda: check_no_em_dashes(_read())),
]


def main() -> int:
    print("\033[1m\nTemporal RAG Orchestrator Validator (Phase 3 of AGENTIC_RAG_ROADMAP.md)\033[0m")
    print("=" * 70)
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
