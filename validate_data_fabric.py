"""
Data Fabric Normalizer Validator (Phase 5 of AGENTIC_RAG_ROADMAP.md)
====================================================================
Forward-only L0 ratchet for the scaffolding-level data fabric normalizer.

  F01  Migration creates unified_events with 10-value source CHECK
  F02  Migration enables RLS + service-role-only insert
  F03  Edge fn file exists
  F04  All 10 sources declared in TS SOURCES const
  F05  At least 3 adapters present (sap_pm, opc_ua, generic)
  F06  Idempotent ingest via sha256 hash
  F07  Hive scoping enforced (hive_id required at entry)
  F08  Duplicate handled gracefully (23505 → ok:true deduped:1)
  F09  No raw fetch to provider URLs (no LLM call in this fn)
  F10  4-place sync (config + deploy + edge_contracts ALL + REQUIRED)
"""
from __future__ import annotations
import os, sys, re, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FN_PATH       = os.path.join("supabase", "functions", "data-fabric-normalizer", "index.ts")
CONFIG_TOML   = os.path.join("supabase", "config.toml")
DEPLOY_PS1    = "deploy-functions.ps1"
EDGE_CONTRACT = "validate_edge_contracts.py"
MIGRATIONS    = os.path.join("supabase", "migrations")

SOURCES = ["sap_pm","maximo","opc_ua","mqtt","cmms_webhook","voice","photo_ocr","manual_log","sensor","email_ingest"]


def _read() -> str:
    return read_file(FN_PATH) or ""


def check_migration() -> list[dict]:
    matches = glob.glob(os.path.join(MIGRATIONS, "*unified_events*.sql"))
    if not matches:
        return [{"check": "migration", "reason": "No migration matching *unified_events*.sql"}]
    src = read_file(matches[0]) or ""
    issues = []
    if "CREATE TABLE" not in src.upper() or "unified_events" not in src:
        issues.append({"check": "migration", "reason": "Migration does not CREATE TABLE unified_events"})
    for s in SOURCES:
        if f"'{s}'" not in src:
            issues.append({"check": "migration", "reason": f"Missing source CHECK value '{s}'"})
    if "ENABLE ROW LEVEL SECURITY" not in src.upper():
        issues.append({"check": "migration_rls", "reason": "Missing ENABLE ROW LEVEL SECURITY"})
    if "WITH CHECK (false)" not in src:
        issues.append({"check": "migration_rls", "reason": "Insert policy must reject anon/auth"})
    return issues


def check_fn_file() -> list[dict]:
    if not os.path.isfile(FN_PATH):
        return [{"check": "fn_file", "reason": f"{FN_PATH} not found"}]
    return []


def check_sources_declared(src: str) -> list[dict]:
    issues = []
    for s in SOURCES:
        if f'"{s}"' not in src:
            issues.append({"check": "sources", "reason": f"Missing source in SOURCES const: {s}"})
    return issues


def check_adapters(src: str) -> list[dict]:
    issues = []
    for name in ("adaptSapPm", "adaptOpcUa", "adaptGeneric"):
        if name not in src:
            issues.append({"check": "adapters", "reason": f"Missing adapter: {name}"})
    return issues


def check_hash(src: str) -> list[dict]:
    if "crypto.subtle.digest" not in src or '"SHA-256"' not in src:
        return [{"check": "hash", "reason": "Must compute sha256 hash via crypto.subtle.digest('SHA-256', ...) for idempotent ingest"}]
    return []


def check_hive_scoping(src: str) -> list[dict]:
    if "body.hive_id" not in src:
        return [{"check": "hive_scoping", "reason": "Edge fn must require hive_id at entry"}]
    return []


def check_dup_handling(src: str) -> list[dict]:
    if '"23505"' not in src and 'duplicate' not in src.lower():
        return [{"check": "dup_handling", "reason": "Must handle Postgres unique-violation (23505) as ok:true deduped:1"}]
    return []


def check_no_raw_fetch(src: str) -> list[dict]:
    if re.search(r'fetch\(\s*["\']https?://api\.(groq|openai|anthropic)', src):
        return [{"check": "no_raw_fetch", "reason": "No LLM calls in normalizer — raw provider fetch detected"}]
    return []


def check_4place_sync() -> list[dict]:
    cfg = read_file(CONFIG_TOML) or ""
    dep = read_file(DEPLOY_PS1) or ""
    ec  = read_file(EDGE_CONTRACT) or ""
    issues = []
    if "[functions.data-fabric-normalizer]" not in cfg:
        issues.append({"check": "sync_config", "reason": "config.toml missing [functions.data-fabric-normalizer]"})
    if "data-fabric-normalizer" not in dep:
        issues.append({"check": "sync_deploy", "reason": "deploy-functions.ps1 missing data-fabric-normalizer line"})
    if '"data-fabric-normalizer"' not in ec:
        issues.append({"check": "sync_ec_all", "reason": "validate_edge_contracts ALL_FUNCTIONS missing data-fabric-normalizer"})
    if '"data-fabric-normalizer":' not in ec:
        issues.append({"check": "sync_ec_required", "reason": "validate_edge_contracts REQUIRED_FIELDS missing data-fabric-normalizer"})
    return issues


CHECKS = [
    ("migration",       "F01-F02 Migration + 10 sources + RLS",         check_migration),
    ("fn_file",         "F03 Edge fn file exists",                       check_fn_file),
    ("sources",         "F04 All 10 sources declared in SOURCES const",  lambda: check_sources_declared(_read())),
    ("adapters",        "F05 3 adapters present (sap_pm/opc_ua/generic)", lambda: check_adapters(_read())),
    ("hash",            "F06 SHA-256 dedup hash",                         lambda: check_hash(_read())),
    ("hive_scoping",    "F07 hive_id required at entry",                  lambda: check_hive_scoping(_read())),
    ("dup_handling",    "F08 Duplicate (23505) handled gracefully",       lambda: check_dup_handling(_read())),
    ("no_raw_fetch",    "F09 No raw provider fetch (no LLM in this fn)",  lambda: check_no_raw_fetch(_read())),
    ("sync",            "F10 4-place sync",                                check_4place_sync),
]


def main() -> int:
    print("\033[1m\nData Fabric Normalizer Validator (Phase 5 of AGENTIC_RAG_ROADMAP.md, scaffolding)\033[0m")
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
