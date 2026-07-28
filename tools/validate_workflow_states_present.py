#!/usr/bin/env python3
"""
validate_workflow_states_present.py — AHK3: a workflow state with no rows is a state nobody has walked.

THE CLASS: the seeder is part of the test surface. When a table has a review lifecycle and the
fixture only ever contains the TERMINAL state, every affordance built for the other states is
unreachable — and the failure is quiet, because a fixture missing a state looks exactly like a
fixture that is fine.

The Asset Hub arc hit this THREE times, for three different reasons:

  asset_nodes      95 rows, ALL status='approved', 0 pending, 0 rejected, 0 with auth_uid.
                   Cause: assets.py computed auth_uid but asset_brain.py dropped it in the hand-off
                   and hardcoded status='approved'. Consequence: the PDDA arc's F21 (a worker's
                   Pending tile always reads 0) sat undiagnosed — there had never been a pending
                   asset to see — and AH3's authority hole hid behind the same gap.
  rcm_strategies   172 approved / 0 unapproved. Cause: reliability.py set approved_at
                   unconditionally, while the fmea_modes rows twelve lines above already had an
                   is_approved branch. Consequence: pushStrategyToPm's REFUSAL had never once run.
  weibull_fits     91 fits, 0 'insufficient_data'. Consequence: the refusal path — the state that
                   tells a planner NOT to act on a number — had never been rendered.

This gate holds those states open. It does NOT demand a particular ratio; it demands that a
non-terminal state a workflow can reach is REPRESENTED, so the next walk has something to walk.

Live tier; SKIPS cleanly (exit 0) without docker. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent

# (label, SQL returning one integer, why the state matters if it empties)
REQUIRED_STATES = [
    ("asset_nodes.pending",
     "SELECT count(*) FROM public.asset_nodes WHERE status = 'pending'",
     "the approval queue itself — with none, a worker's Pending tile and the whole review flow are "
     "unwalkable (the inherited F21)"),
    ("asset_nodes.rejected",
     "SELECT count(*) FROM public.asset_nodes WHERE status = 'rejected'",
     "the rejection path, including the reviewer's rejection_reason that AH3 secured and AH4 "
     "finally shows to the submitter"),
    ("asset_nodes.authored",
     "SELECT count(*) FROM public.asset_nodes WHERE auth_uid IS NOT NULL",
     "without an author no row can exercise the OWNERSHIP half of asset_nodes_write, and no "
     "self-approval or self-reject probe is possible at all"),
    ("rcm_strategies.unapproved",
     "SELECT count(*) FROM public.rcm_strategies WHERE approved_at IS NULL",
     "pushStrategyToPm refuses an unapproved strategy; with none in existence that refusal never runs"),
    ("rcm_strategies.pushed_to_pm",
     "SELECT count(*) FROM public.rcm_strategies WHERE written_to_pm_scope_item_id IS NOT NULL",
     "the linked branch — pushStrategyToPm's idempotence guard and the FK have no row to protect "
     "when every strategy is cold-start"),
    ("weibull_fits.insufficient_data",
     "SELECT count(*) FROM public.weibull_fits WHERE failure_pattern = 'insufficient_data'",
     "the REFUSAL state — the one that tells a planner not to act on a number"),
    ("asset_nodes.cold_start",
     "SELECT count(*) FROM public.asset_nodes n WHERE n.status = 'approved'"
     " AND NOT EXISTS (SELECT 1 FROM public.rcm_fmea_modes m WHERE m.asset_id = n.id)"
     " AND NOT EXISTS (SELECT 1 FROM public.weibull_fits  w WHERE w.asset_id = n.id)"
     " AND NOT EXISTS (SELECT 1 FROM public.pf_intervals  p WHERE p.asset_id = n.id)",
     "an asset with NO reliability work at all — the state every newly-commissioned machine and "
     "every new customer's whole fleet is in. reliability.py used to fit EVERY node, so 0 of 79 "
     "approved assets were cold and the three Workbench empty states could never render"),
]


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


def main():
    if "--selftest" in sys.argv:
        probs = []
        if len(REQUIRED_STATES) < 7:
            probs.append("REQUIRED_STATES shrank — the gate is losing the states three walks opened")
        if not all(len(t) == 3 and t[1].lower().startswith("select count(") for t in REQUIRED_STATES):
            probs.append("every entry must be a single scalar count query")
        print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
        return 1 if probs else 0

    print(f"\n{BOLD}WORKFLOW STATES PRESENT (a state with no rows is a state nobody walked){RESET}")
    print("-" * 70)

    probe = psql("SELECT 1;")
    if probe is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable")
        return 0

    fails = 0
    report = {}
    for label, sql, why in REQUIRED_STATES:
        raw = psql(sql)
        try:
            n = int((raw or "0").splitlines()[0])
        except (ValueError, IndexError):
            n = 0
        report[label] = n
        if n > 0:
            print(f"  {GREEN}PASS{RESET}  {label}: {n} row(s)")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {label}: EMPTY — {why}")

    print(f"\n  Summary: {len(REQUIRED_STATES) - fails} pass · {fails} fail")
    (ROOT / "workflow_states_report.json").write_text(
        json.dumps({"validator": "workflow_states_present",
                    "counts": report, "fail": fails}, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
