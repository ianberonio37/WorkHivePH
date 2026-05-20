"""
Truth-View Signal-Trust Validator (L0, ratcheted).
==================================================
Codifies the rule from `mine_truth_view_signal_trust.py`:

  When a surface reads from `v_<...>_truth`, it must TRUST the canonical
  signals AS-IS — no local re-derivation of overdue/low-stock/risk-band
  using `Date.now() - last_*`, `qty_on_hand < reorder_point`, FREQ_DAYS,
  hand-rolled status maps, etc.

Reads `truth_view_signal_trust_report.json` (re-runs the miner first to
keep it fresh) and gates on:

  AT_RISK pairs  — re-gating across consumers (e.g. one trusts, one
                   uses `else { st = 'nodata' }`). HARD FAIL.
  REVIEW pairs   — multiple consumers AND at least one shows a
                   local-math smell (qty_on_hand < reorder_point,
                   FREQ_DAYS, daysUntil, etc.) inside a `db.from(v_*)`
                   scope. RATCHET — fail only if the count went UP
                   vs. the locked baseline.

Baseline: `truth_view_signal_trust_baseline.json` stores the canonical
REVIEW count when this validator first ran cleanly. New REVIEWs above
that count fail; resolved REVIEWs below it tighten the ratchet.

Exit codes:
  0  no AT_RISK pairs + REVIEW count <= baseline
  1  any AT_RISK OR REVIEW count > baseline
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent

REPORT_PATH   = ROOT / "truth_view_signal_trust_report.json"
BASELINE_PATH = ROOT / "truth_view_signal_trust_baseline.json"
MINER_PATH    = ROOT / "tools" / "mine_truth_view_signal_trust.py"


def _bold(s):  return f"\033[1m{s}\033[0m"
def _red(s):   return f"\033[91m{s}\033[0m"
def _green(s): return f"\033[92m{s}\033[0m"
def _yellow(s):return f"\033[93m{s}\033[0m"


# Sentinel binding: name the L2 test `test('truth_view_signal_trust: ...')` for coverage credit.
CHECK_NAMES = ["truth_view_signal_trust"]


def main() -> int:
    # Refresh the miner report (miner exits 1 on AT_RISK; we still want
    # the JSON output for our own gating).
    subprocess.run([sys.executable, str(MINER_PATH)], check=False)

    if not REPORT_PATH.exists():
        print(_red("FAIL: truth_view_signal_trust_report.json missing — miner did not run"))
        return 2

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    s = report.get("summary", {})
    pairs = report.get("pairs", [])

    at_risk = s.get("at_risk", 0)
    review  = s.get("review", 0)

    # Baseline ratchet — first run establishes the locked REVIEW count.
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("review", 0)
        except Exception:
            baseline = 0
    else:
        # Initialize baseline to current REVIEW count (forward-only ratchet:
        # we don't fail on baseline establishment, but every future run
        # must stay <= baseline).
        baseline = review
        BASELINE_PATH.write_text(
            json.dumps({"review": baseline, "established_at_at_risk": at_risk}, indent=2),
            encoding="utf-8",
        )

    # If REVIEW dropped, ratchet the baseline DOWN. Forward-only — never up.
    if review < baseline:
        baseline = review
        BASELINE_PATH.write_text(
            json.dumps({"review": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    print()
    print(_bold("Truth-View Signal-Trust Validator (L0)"))
    print("=" * 56)
    print(f"  view/column pairs:    {s.get('view_column_pairs', 0)}")
    print(f"  AT_RISK pairs:        {at_risk}")
    print(f"  REVIEW pairs:         {review} (baseline: {baseline})")
    print(f"  files scanned:        {s.get('files_scanned', 0)}")

    failed = False
    if at_risk > 0:
        print()
        print(_red("FAIL: AT_RISK pairs (different interpretations across consumers)"))
        for r in pairs:
            if r.get("risk") != "AT_RISK":
                continue
            print(f"  {r['view']}.{r['column']}")
            for c in r.get("consumers", []):
                tail = f" 🚩 {','.join(c.get('smells', []))}" if c.get("smells") else ""
                print(f"    {c['file']} → {c['shape']}{tail}")
        failed = True

    if review > baseline:
        print()
        print(_red(f"FAIL: REVIEW count {review} > baseline {baseline} — new smells introduced"))
        # Identify the diff is not stored; we just report the current REVIEW set.
        for r in pairs[:30]:
            if r.get("risk") != "REVIEW":
                continue
            print(f"  {r['view']}.{r['column']}  smells={r['smells']}")
        failed = True

    if not failed:
        print()
        print(_green(f"PASS — 0 AT_RISK + {review} REVIEW (== baseline {baseline})"))
        return 0

    print()
    print(_yellow("Run `python tools/mine_truth_view_signal_trust.py` for the full punch list."))
    return 1


if __name__ == "__main__":
    sys.exit(main())
