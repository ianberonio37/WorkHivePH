#!/usr/bin/env python3
"""validate_oee_quality_derivation.py — Analytics arc F1b gate: the canonical OEE RPC must derive
Quality from good_units/total_units, not quality_pct alone.

THE BUG (recurred once): `descriptive.calc_oee` (the analytics PAGE) reads Quality from
production_output.quality_pct AND falls back to good_units/total_units — because seeders/UI write the
good/total shape, not quality_pct. `get_oee_by_machine` (the analytics-orchestrator REPORT path →
analytics-report.html / asset-hub) read ONLY quality_pct, so on real data (Lucena: 0 quality_pct /
60 good_units) its Quality defaulted high and OEE ran ~10 points ABOVE the page for the same asset.
The Python engine fixed this in May 2026; the RPC didn't get the fix until this arc.

THE CONTROL: the canonical `get_oee_by_machine` definition (latest CREATE OR REPLACE across the
migrations) must reference good_units + total_units in its quality derivation — so it can't silently
regress to a quality_pct-only read (which would re-open the page-vs-report OEE divergence).

Static (reads the migration SQL) → --fast-safe. Self-test: --self-test proves teeth.
Skills: data-engineer (canonical RPC), analytics-engineer (OEE quality basis), architect (one derivation).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations"
GREEN, RED = "\033[92m", "\033[91m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]


def latest_oee_def(mig_dir: Path) -> tuple[str, str] | None:
    """The most-recent migration (by filename ts) that CREATE-OR-REPLACEs get_oee_by_machine, + its body."""
    hits = []
    for f in sorted(mig_dir.glob("*.sql")):
        src = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r"create\s+or\s+replace\s+function\s+public\.get_oee_by_machine", src, re.I):
            hits.append((f.name, src))
    return hits[-1] if hits else None


def check(body: str) -> tuple[bool, str]:
    has_good = re.search(r"good_units", body) is not None
    has_total = re.search(r"total_units", body) is not None
    ok = has_good and has_total
    return ok, ("quality derives from good_units/total_units" if ok
                else f"good_units={has_good} total_units={has_total} — quality_pct-only risks page-vs-report OEE divergence")


def main() -> int:
    print(f"\n{'='*64}\n  Analytics arc F1b — canonical OEE quality derivation\n{'='*64}")
    found = latest_oee_def(MIG)
    if not found:
        print(f"{RED}  FAIL  no migration defines get_oee_by_machine{RST}"); return 1
    name, body = found
    print(f"  canonical def: {name}")

    if SELF_TEST:
        broken = "CREATE OR REPLACE FUNCTION public.get_oee_by_machine() ... quality_pct only ..."
        tok = not check(broken)[0]
        print(f"  self-test: a quality_pct-only def is caught = {tok} "
              f"({GREEN+'teeth OK'+RST if tok else RED+'NO TEETH'+RST})")

    ok, detail = check(body)
    print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  {detail}")
    print("-" * 64)
    print(f"{(GREEN if ok else RED)}  RESULT: {'GREEN — report/asset-hub OEE quality matches the analytics page (good/total).' if ok else 'RED — the canonical OEE RPC could inflate quality vs the page.'}{RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
