"""
cold-archive-wiring — L0 ratchet for the Hierarchical / cold-tier layer
(Turn 3 of the AI Agent Memory Stack flywheel).

Where validate_cold_archive.py guards the I/O contract (4-place sync, hive
scoping, exporter safety), this validator asserts the *read path is genuinely
wired* with hyparquet — not a stub. Forward-only: baseline 0 issues.

  W01  _shared/cold-archive.ts exists + exports the quarter helpers
  W02  edge fn imports hyparquet (parquetReadObjects) + hyparquet-compressors (compressors)
  W03  edge fn imports selectRelevantQuarters from _shared/cold-archive.ts
  W04  edge fn actually calls parquetReadObjects(...) and storage .download(...)
  W05  edge fn maps logical voice_journal -> voice_journal_entries (TABLE_FILE)
  W06  edge fn bounds fan-out (MAX_QUARTERS) and caps rows (LIMIT_CAP)
  W07  edge fn returns ok:true success path (and no 503 scaffold remains)
"""
from __future__ import annotations
import os, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

EDGE_FN = os.path.join("supabase", "functions", "cold-archive-query", "index.ts")
MODULE  = os.path.join("supabase", "functions", "_shared", "cold-archive.ts")


def _read_fn() -> str:  return read_file(EDGE_FN) or ""


def check_module() -> list[dict]:
    if not os.path.isfile(MODULE):
        return [{"check": "module", "reason": f"{MODULE} not found"}]
    src = read_file(MODULE) or ""
    issues = []
    for fn in ("selectRelevantQuarters", "quarterToRange", "quarterOverlapsRange"):
        if f"export function {fn}" not in src:
            issues.append({"check": "module", "reason": f"cold-archive.ts must export {fn}"})
    return issues


def check_hyparquet_import(src: str) -> list[dict]:
    issues = []
    if "hyparquet@" not in src or "parquetReadObjects" not in src:
        issues.append({"check": "hyparquet_import", "reason": "edge fn must import parquetReadObjects from hyparquet"})
    if "hyparquet-compressors@" not in src or "compressors" not in src:
        issues.append({"check": "hyparquet_import", "reason": "edge fn must import compressors from hyparquet-compressors"})
    return issues


def check_module_import(src: str) -> list[dict]:
    if "cold-archive.ts" not in src or "selectRelevantQuarters" not in src:
        return [{"check": "module_import", "reason": "edge fn must import selectRelevantQuarters from _shared/cold-archive.ts"}]
    return []


def check_reads(src: str) -> list[dict]:
    issues = []
    if "parquetReadObjects(" not in src:
        issues.append({"check": "reads", "reason": "edge fn must call parquetReadObjects(...)"})
    if ".download(" not in src:
        issues.append({"check": "reads", "reason": "edge fn must download Parquet via storage.from(BUCKET).download(...)"})
    return issues


def check_table_file_map(src: str) -> list[dict]:
    if "TABLE_FILE" not in src:
        return [{"check": "table_file", "reason": "edge fn must declare a TABLE_FILE logical->file map"}]
    if "voice_journal_entries" not in src:
        return [{"check": "table_file", "reason": "TABLE_FILE must map voice_journal -> voice_journal_entries"}]
    return []


def check_bounds(src: str) -> list[dict]:
    issues = []
    if "MAX_QUARTERS" not in src:
        issues.append({"check": "bounds", "reason": "edge fn must bound fan-out with MAX_QUARTERS"})
    if "LIMIT_CAP" not in src:
        issues.append({"check": "bounds", "reason": "edge fn must cap returned rows with LIMIT_CAP"})
    return issues


def check_contract(src: str) -> list[dict]:
    flat = src.replace(" ", "")
    issues = []
    if "ok:true" not in flat:
        issues.append({"check": "contract", "reason": "edge fn must return ok:true on the success path"})
    if "status:503" in flat:
        issues.append({"check": "contract", "reason": "503 scaffold must be gone — fn returns 200 now"})
    return issues


CHECKS = [
    ("module",          "W01 cold-archive.ts exists + exports helpers",   check_module),
    ("hyparquet_import","W02 imports hyparquet + compressors",            lambda: check_hyparquet_import(_read_fn())),
    ("module_import",   "W03 imports selectRelevantQuarters",             lambda: check_module_import(_read_fn())),
    ("reads",           "W04 calls parquetReadObjects + .download",       lambda: check_reads(_read_fn())),
    ("table_file",      "W05 TABLE_FILE maps voice_journal_entries",      lambda: check_table_file_map(_read_fn())),
    ("bounds",          "W06 MAX_QUARTERS + LIMIT_CAP bounds",            lambda: check_bounds(_read_fn())),
    ("contract",        "W07 ok:true success path, no 503",               lambda: check_contract(_read_fn())),
]


def main() -> int:
    print("\033[1m\ncold-archive-wiring — Turn 3 (Hierarchical / cold tier, hyparquet)\033[0m")
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
