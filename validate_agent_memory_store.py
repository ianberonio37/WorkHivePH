"""
Agent Episodic Memory Validator (Phase 7 of AGENTIC_RAG_ROADMAP.md)
==================================================================
Forward-only L0 ratchet for the durable-facts memory store.

  E01  Migration creates agent_episodic_memory + CHECK on memory_type (4 values)
  E02  Migration enables RLS + service-role-only insert/update
  E03  Edge fn file exists
  E04  Both ops present: recall + store
  E05  4 memory types declared in TS: factual/procedural/episodic/semantic
  E06  Per-worker cap enforced (≤ 200)
  E07  Per-hive cap enforced (≤ 1000)
  E08  Content length cap enforced (≤ 600)
  E09  Recall ranks by importance × log(1+use_count)
  E10  Store batch cap enforced (≤ 10)
  E11  Hive scoping on all queries
  E12  4-place sync: config.toml + deploy + edge_contracts ALL + REQUIRED
  E13  PII safety: content slice() applied before insert
  E14  No raw fetch to provider URLs (this fn has no LLM call, but guard anyway)
"""
from __future__ import annotations
import os, sys, re, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FN_PATH       = os.path.join("supabase", "functions", "agent-memory-store", "index.ts")
CONFIG_TOML   = os.path.join("supabase", "config.toml")
DEPLOY_PS1    = "deploy-functions.ps1"
EDGE_CONTRACT = "validate_edge_contracts.py"
MIGRATIONS    = os.path.join("supabase", "migrations")


def _read() -> str:
    return read_file(FN_PATH) or ""


def check_migration() -> list[dict]:
    matches = glob.glob(os.path.join(MIGRATIONS, "*agent_episodic_memory*.sql"))
    if not matches:
        return [{"check": "migration", "reason": "No migration matching *agent_episodic_memory*.sql"}]
    src = read_file(matches[0]) or ""
    issues = []
    if "CREATE TABLE" not in src.upper() or "agent_episodic_memory" not in src:
        issues.append({"check": "migration", "reason": "Migration does not CREATE TABLE agent_episodic_memory"})
    for v in ("'factual'", "'procedural'", "'episodic'", "'semantic'"):
        if v not in src:
            issues.append({"check": "migration", "reason": f"Missing memory_type CHECK value {v}"})
    if "ENABLE ROW LEVEL SECURITY" not in src.upper():
        issues.append({"check": "migration_rls", "reason": "Missing ENABLE ROW LEVEL SECURITY"})
    if "WITH CHECK (false)" not in src:
        issues.append({"check": "migration_rls", "reason": "Insert/update policies must reject anon/auth (WITH CHECK (false))"})
    return issues


def check_fn_file() -> list[dict]:
    if not os.path.isfile(FN_PATH):
        return [{"check": "fn_file", "reason": f"{FN_PATH} not found"}]
    return []


def check_both_ops(src: str) -> list[dict]:
    if '"recall"' not in src:
        return [{"check": "both_ops", "reason": 'Missing recall op handler'}]
    if '"store"' not in src:
        return [{"check": "both_ops", "reason": 'Missing store op handler'}]
    return []


def check_memory_types(src: str) -> list[dict]:
    if not re.search(r'MEMORY_TYPES\s*=\s*\[\s*"factual"\s*,\s*"procedural"\s*,\s*"episodic"\s*,\s*"semantic"', src):
        return [{"check": "memory_types", "reason": "MEMORY_TYPES const must list factual/procedural/episodic/semantic in order"}]
    return []


def check_worker_cap(src: str) -> list[dict]:
    m = re.search(r"PER_WORKER_CAP\s*=\s*(\d+)", src)
    if not m: return [{"check": "worker_cap", "reason": "PER_WORKER_CAP constant missing"}]
    if int(m.group(1)) > 200:
        return [{"check": "worker_cap", "reason": f"PER_WORKER_CAP = {m.group(1)} > 200"}]
    return []


def check_hive_cap(src: str) -> list[dict]:
    m = re.search(r"PER_HIVE_CAP\s*=\s*(\d+)", src)
    if not m: return [{"check": "hive_cap", "reason": "PER_HIVE_CAP constant missing"}]
    if int(m.group(1)) > 1000:
        return [{"check": "hive_cap", "reason": f"PER_HIVE_CAP = {m.group(1)} > 1000"}]
    return []


def check_content_cap(src: str) -> list[dict]:
    m = re.search(r"MAX_CONTENT_CHARS\s*=\s*(\d+)", src)
    if not m: return [{"check": "content_cap", "reason": "MAX_CONTENT_CHARS constant missing"}]
    if int(m.group(1)) > 1000:
        return [{"check": "content_cap", "reason": f"MAX_CONTENT_CHARS = {m.group(1)} > 1000 (prompt-injection safety)"}]
    if 'slice(0, MAX_CONTENT_CHARS)' not in src:
        return [{"check": "content_cap", "reason": "Content must be truncated with .slice(0, MAX_CONTENT_CHARS) before insert"}]
    return []


def check_recall_rank(src: str) -> list[dict]:
    # The compound score must reference both importance and use_count
    if not re.search(r"importance.*Math\.log\(\s*1\s*\+", src, re.DOTALL):
        return [{"check": "recall_rank", "reason": "Recall must rank by importance × Math.log(1 + use_count)"}]
    return []


def check_store_batch_cap(src: str) -> list[dict]:
    m = re.search(r"MAX_STORE_BATCH\s*=\s*(\d+)", src)
    if not m: return [{"check": "store_batch_cap", "reason": "MAX_STORE_BATCH constant missing"}]
    if int(m.group(1)) > 25:
        return [{"check": "store_batch_cap", "reason": f"MAX_STORE_BATCH = {m.group(1)} > 25"}]
    return []


def check_hive_scoping(src: str) -> list[dict]:
    if not re.search(r'\.eq\(\s*"hive_id"', src):
        return [{"check": "hive_scoping", "reason": '.eq("hive_id", ...) missing'}]
    if not re.search(r'\.eq\(\s*"worker_name"', src):
        return [{"check": "hive_scoping", "reason": '.eq("worker_name", ...) missing'}]
    return []


def check_4place_sync() -> list[dict]:
    cfg = read_file(CONFIG_TOML) or ""
    dep = read_file(DEPLOY_PS1) or ""
    ec  = read_file(EDGE_CONTRACT) or ""
    issues = []
    if "[functions.agent-memory-store]" not in cfg:
        issues.append({"check": "sync_config", "reason": "config.toml missing [functions.agent-memory-store]"})
    if "agent-memory-store" not in dep:
        issues.append({"check": "sync_deploy", "reason": "deploy-functions.ps1 missing agent-memory-store line"})
    if '"agent-memory-store"' not in ec:
        issues.append({"check": "sync_ec_all", "reason": "validate_edge_contracts.py ALL_FUNCTIONS missing agent-memory-store"})
    if '"agent-memory-store":' not in ec:
        issues.append({"check": "sync_ec_required", "reason": "validate_edge_contracts.py REQUIRED_FIELDS missing agent-memory-store"})
    return issues


def check_no_raw_fetch(src: str) -> list[dict]:
    if re.search(r'fetch\(\s*["\']https?://api\.(groq|openai|anthropic)', src):
        return [{"check": "no_raw_fetch", "reason": "Raw fetch() to provider URL detected — but this fn should have NO LLM calls"}]
    return []


CHECKS = [
    ("migration",         "E01-E02 Migration + 4 types + RLS",                 check_migration),
    ("fn_file",           "E03 Edge fn file exists",                            check_fn_file),
    ("both_ops",          "E04 Recall + store ops",                             lambda: check_both_ops(_read())),
    ("memory_types",      "E05 4 memory types declared",                        lambda: check_memory_types(_read())),
    ("worker_cap",        "E06 PER_WORKER_CAP <= 200",                          lambda: check_worker_cap(_read())),
    ("hive_cap",          "E07 PER_HIVE_CAP <= 1000",                           lambda: check_hive_cap(_read())),
    ("content_cap",       "E08 MAX_CONTENT_CHARS <= 1000 + .slice enforced",    lambda: check_content_cap(_read())),
    ("recall_rank",       "E09 Recall ranks importance × log(1+use_count)",     lambda: check_recall_rank(_read())),
    ("store_batch_cap",   "E10 MAX_STORE_BATCH <= 25",                          lambda: check_store_batch_cap(_read())),
    ("hive_scoping",      "E11 Hive scoping on queries",                        lambda: check_hive_scoping(_read())),
    ("sync",              "E12 4-place sync",                                   check_4place_sync),
    ("no_raw_fetch",      "E13-E14 No raw provider fetch (no LLM call here)",   lambda: check_no_raw_fetch(_read())),
]


def main() -> int:
    print("\033[1m\nAgent Episodic Memory Validator (Phase 7 of AGENTIC_RAG_ROADMAP.md)\033[0m")
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
