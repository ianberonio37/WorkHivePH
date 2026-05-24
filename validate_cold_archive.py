"""
Cold Lakehouse Archive Validator (Phase 6 of AGENTIC_RAG_ROADMAP.md, SCAFFOLDING)
================================================================================
Forward-only L0 ratchet for the cold-archive read endpoint + Python exporter.

  C01  cold-archive-query edge fn file exists
  C02  Edge fn declares all 4 SUPPORTED_TABLES
  C03  Edge fn returns 503 with structured reason (scaffolding contract)
  C04  Edge fn lists available_quarters via storage.from(BUCKET).list
  C05  Hive scoping enforced (hive_id required)
  C06  Python exporter tool exists
  C07  Exporter has --commit flag (defaults to dry-run)
  C08  Exporter has ARCHIVE_AGE_MONTHS = 18 (per roadmap)
  C09  Exporter does NOT auto-delete hot rows (highest-risk safety guard)
  C10  4-place sync (config + deploy + edge_contracts ALL + REQUIRED)
"""
from __future__ import annotations
import os, sys, re

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

EDGE_FN = os.path.join("supabase", "functions", "cold-archive-query", "index.ts")
EXPORTER = os.path.join("tools", "cold_archive_exporter.py")
CONFIG_TOML  = os.path.join("supabase", "config.toml")
DEPLOY_PS1   = "deploy-functions.ps1"
EDGE_CONTRACT = "validate_edge_contracts.py"


def _read_fn() -> str:  return read_file(EDGE_FN) or ""
def _read_py() -> str:  return read_file(EXPORTER) or ""


def check_fn_file() -> list[dict]:
    if not os.path.isfile(EDGE_FN):
        return [{"check": "fn_file", "reason": f"{EDGE_FN} not found"}]
    return []


def check_supported_tables(src: str) -> list[dict]:
    issues = []
    for t in ("logbook", "pm_completions", "unified_events", "voice_journal"):
        if f'"{t}"' not in src:
            issues.append({"check": "supported_tables", "reason": f"SUPPORTED_TABLES missing: {t}"})
    return issues


def check_503_scaffolding(src: str) -> list[dict]:
    # Must return 503 with a structured body containing 'reason' and 'available_quarters'
    if "status:503" not in src.replace(" ", ""):
        return [{"check": "scaffolding_503", "reason": "Scaffolding fn must return 503 (not 200 — there is no data yet)"}]
    if "reason" not in src or "available_quarters" not in src:
        return [{"check": "scaffolding_503", "reason": "Response body must include 'reason' and 'available_quarters' fields"}]
    return []


def check_lists_quarters(src: str) -> list[dict]:
    if "storage.from(" not in src or ".list(" not in src:
        return [{"check": "lists_quarters", "reason": "Must call db.storage.from(BUCKET).list(...) to discover available quarters"}]
    return []


def check_hive_scoping(src: str) -> list[dict]:
    if "body.hive_id" not in src:
        return [{"check": "hive_scoping", "reason": "Edge fn must require hive_id at entry"}]
    return []


def check_exporter_file() -> list[dict]:
    if not os.path.isfile(EXPORTER):
        return [{"check": "exporter_file", "reason": f"{EXPORTER} not found"}]
    return []


def check_commit_flag(src: str) -> list[dict]:
    if '--commit' not in src:
        return [{"check": "commit_flag", "reason": "Exporter must have --commit flag (defaults to dry-run for safety)"}]
    if "default=" in src and 'commit' in src and 'False' not in src and 'store_true' not in src:
        return [{"check": "commit_flag", "reason": "Exporter --commit must default to False (store_true action)"}]
    return []


def check_age_const(src: str) -> list[dict]:
    m = re.search(r"ARCHIVE_AGE_MONTHS\s*=\s*(\d+)", src)
    if not m: return [{"check": "age_const", "reason": "ARCHIVE_AGE_MONTHS constant missing"}]
    if int(m.group(1)) != 18:
        return [{"check": "age_const", "reason": f"ARCHIVE_AGE_MONTHS = {m.group(1)}, must be 18 per roadmap"}]
    return []


def check_no_auto_delete(src: str) -> list[dict]:
    # The exporter must NOT delete hot rows automatically. Look for any
    # destructive verb that would imply auto-cleanup.
    if re.search(r"\.delete\s*\(", src) or re.search(r"DELETE FROM", src, re.IGNORECASE):
        return [{"check": "no_auto_delete", "reason": "Exporter must NOT call .delete() — destructive cleanup is a separate manual step"}]
    return []


def check_4place_sync() -> list[dict]:
    cfg = read_file(CONFIG_TOML) or ""
    dep = read_file(DEPLOY_PS1) or ""
    ec  = read_file(EDGE_CONTRACT) or ""
    issues = []
    if "[functions.cold-archive-query]" not in cfg:
        issues.append({"check": "sync_config", "reason": "config.toml missing [functions.cold-archive-query]"})
    if "cold-archive-query" not in dep:
        issues.append({"check": "sync_deploy", "reason": "deploy-functions.ps1 missing cold-archive-query line"})
    if '"cold-archive-query"' not in ec:
        issues.append({"check": "sync_ec_all", "reason": "validate_edge_contracts ALL_FUNCTIONS missing cold-archive-query"})
    if '"cold-archive-query":' not in ec:
        issues.append({"check": "sync_ec_required", "reason": "validate_edge_contracts REQUIRED_FIELDS missing cold-archive-query"})
    return issues


CHECKS = [
    ("fn_file",          "C01 cold-archive-query edge fn exists",         check_fn_file),
    ("supported_tables", "C02 SUPPORTED_TABLES declared (4 tables)",      lambda: check_supported_tables(_read_fn())),
    ("scaffolding_503",  "C03 Scaffolding returns 503 + structured body", lambda: check_503_scaffolding(_read_fn())),
    ("lists_quarters",   "C04 Lists available_quarters via storage.list", lambda: check_lists_quarters(_read_fn())),
    ("hive_scoping",     "C05 hive_id required at entry",                 lambda: check_hive_scoping(_read_fn())),
    ("exporter_file",    "C06 Python exporter tool exists",               check_exporter_file),
    ("commit_flag",      "C07 Exporter --commit defaults to dry-run",     lambda: check_commit_flag(_read_py())),
    ("age_const",        "C08 ARCHIVE_AGE_MONTHS = 18",                   lambda: check_age_const(_read_py())),
    ("no_auto_delete",   "C09 Exporter does NOT auto-delete hot rows",    lambda: check_no_auto_delete(_read_py())),
    ("sync",             "C10 4-place sync",                              check_4place_sync),
]


def main() -> int:
    print("\033[1m\nCold Lakehouse Archive Validator (Phase 6 of AGENTIC_RAG_ROADMAP.md, scaffolding)\033[0m")
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
