#!/usr/bin/env python3
"""validate_pm_compliance_weighted.py — Analytics arc F1d gate: canonical PM compliance = WEIGHTED.

THE BUG: SMRP Metric 2.1.1 PM Compliance = total_completed / total_scheduled across the program
(WEIGHTED). `get_pm_compliance_smrp` (canonical, read by analytics + pm-scheduler) returned
overall_pct = round(avg(compliance_pct)) — the UNWEIGHTED mean of per-asset %, letting a 1-PM asset
count the same as a 20-PM asset. That drifts from the "N of M PMs on time" count shown beside it
(a self-contradicting tile) and from journey_trace.py's terminus assertion (overall_pct ==
100·completed/scheduled). descriptive.calc_pm_compliance had the same np.mean.

THE CONTROL: the canonical `get_pm_compliance_smrp` definition (latest CREATE OR REPLACE across the
migrations) must derive overall_pct from total_completed/total_scheduled, NOT avg(compliance_pct);
and descriptive.calc_pm_compliance must not use np.mean for overall.

Static (reads the migration SQL + descriptive.py) → --fast-safe. Self-test: --self-test proves teeth.
Skills: analytics-engineer (SMRP 2.1.1 weighted), data-engineer (canonical RPC), maintenance-expert.
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
DESC = ROOT / "python-api" / "analytics" / "descriptive.py"
GREEN, RED = "\033[92m", "\033[91m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]


def latest_pm_def(mig_dir: Path) -> tuple[str, str] | None:
    hits = []
    for f in sorted(mig_dir.glob("*.sql")):
        src = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r"create\s+or\s+replace\s+function\s+public\.get_pm_compliance_smrp", src, re.I):
            hits.append((f.name, src))
    return hits[-1] if hits else None


def rpc_ok(body: str) -> tuple[bool, str]:
    # find the overall_pct value expression in the jsonb_build_object
    m = re.search(r"'overall_pct'\s*,\s*(.+?)(?:,\s*\n|\n\s*'total_scheduled')", body, re.S)
    expr = (m.group(1) if m else "").strip()
    weighted = ("sum(completed)" in expr and "sum(scheduled)" in expr) or \
               ("total_completed" in expr and "total_scheduled" in expr)
    unweighted = "avg(compliance_pct)" in expr
    ok = weighted and not unweighted
    return ok, (f"overall_pct = weighted (Σcompleted/Σscheduled)" if ok
                else f"overall_pct expr is not weighted: {expr[:70]!r}")


def desc_ok(src: str) -> tuple[bool, str]:
    # calc_pm_compliance must not compute `overall` via np.mean of compliance_pct
    bad = re.search(r"overall\s*=\s*float\(np\.mean\(\[r\[.compliance_pct.\]", src)
    weighted = "sum(r[\"completed\"]" in src or "sum(r['completed']" in src
    ok = (bad is None) and weighted
    return ok, ("calc_pm_compliance overall = weighted total" if ok
                else "descriptive.calc_pm_compliance still uses np.mean(compliance_pct) for overall")


def main() -> int:
    print(f"\n{'='*64}\n  Analytics arc F1d — canonical PM compliance is WEIGHTED\n{'='*64}")
    found = latest_pm_def(MIG)
    if not found:
        print(f"{RED}  FAIL  no migration defines get_pm_compliance_smrp{RST}"); return 1
    name, body = found
    print(f"  canonical RPC def: {name}")
    desc_src = DESC.read_text(encoding="utf-8", errors="replace") if DESC.exists() else ""

    if SELF_TEST:
        r_t = not rpc_ok("'overall_pct', round(avg(compliance_pct), 1), 'total_scheduled',")[0]
        d_t = not desc_ok("overall = float(np.mean([r[\"compliance_pct\"] for r in results]))")[0]
        print(f"  self-test: unweighted RPC + np.mean descriptive both caught = {r_t and d_t} "
              f"({GREEN+'teeth OK'+RST if (r_t and d_t) else RED+'NO TEETH'+RST})")

    r_ok, r_detail = rpc_ok(body)
    d_ok, d_detail = desc_ok(desc_src)
    for lbl, ok, detail in (("RPC", r_ok, r_detail), ("descriptive.py", d_ok, d_detail)):
        print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  {lbl}: {detail}")
    allok = r_ok and d_ok
    print("-" * 64)
    print(f"{(GREEN if allok else RED)}  RESULT: {'GREEN — PM compliance is SMRP-weighted (hero matches the N-of-M count).' if allok else 'RED — PM compliance overall is unweighted → contradicts its own count.'}{RST}")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
