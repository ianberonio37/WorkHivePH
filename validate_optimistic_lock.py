#!/usr/bin/env python3
"""validate_optimistic_lock.py - Arc S (Resilience/DR) C-lens cell `optimistic_lock`.
================================================================================
Read-modify-write must use compare-and-set (optimistic concurrency), so a parallel
edit by another worker is DETECTED and surfaced, not silently lost (lost-update).
The platform's pattern (PRODUCTION_FIXES #43) is the `ocUpdate(db, table, id, updates,
oldStamp)` helper in utils.js, which adds `.eq('updated_at', oldStamp)` to the UPDATE
so a stale write matches 0 rows -> conflict -> "another worker edited this, refresh".

This gate locks that pattern: the helper must exist, AND the primary user-editable
surface (logbook in-place edit) must route its update through it (or apply the
`.eq('updated_at', ...)` guard directly). Forward-only against regressions.

Exit 0 = optimistic-lock pattern present + used; 1 = missing/unused. Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"

# Pages with a user-editable row that has an `updated_at` and must use OC on edit.
OC_EDIT_PAGES = ["logbook.html"]


def _read(name: str) -> str:
    try:
        return (ROOT / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    print(f"{B}Arc S - optimistic-lock (C-lens, no lost-update){X}")
    print("=" * 60)
    issues = []

    utils = _read("utils.js")
    helper_ok = bool(re.search(r"\bfunction\s+ocUpdate\b|\bocUpdate\s*=", utils))
    print(f"  {(G+'PASS'+X) if helper_ok else (R+'FAIL'+X)}  utils.js ocUpdate compare-and-set helper")
    if not helper_ok:
        issues.append("utils.js missing ocUpdate helper")

    for page in OC_EDIT_PAGES:
        t = _read(page)
        used = ("ocUpdate" in t) or bool(re.search(r"\.eq\(\s*['\"]updated_at['\"]", t))
        print(f"  {(G+'PASS'+X) if used else (R+'FAIL'+X)}  {page} uses ocUpdate / updated_at guard on edit")
        if not used:
            issues.append(f"{page} edit path lacks an optimistic-lock guard")

    if issues:
        print(f"\n{R}{B}  OPTIMISTIC-LOCK: FAIL{X} - {'; '.join(issues)}")
        return 1
    print(f"\n{G}{B}  OPTIMISTIC-LOCK: PASS{X} - compare-and-set guards the edit path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
