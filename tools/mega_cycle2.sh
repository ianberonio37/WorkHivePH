#!/bin/sh
# mega_cycle2.sh — phase 2 of the 2026-08-22 re-earn cycle: the report producers the first pass
# missed (every converter family's report must be FRESHER than its edited-page deps, or the
# convert/restamp rails rightly refuse it). Run AFTER tools/mega_cycle.sh completes.
set -u
LOG=.tmp/mega_cycle.log
mkdir -p .tmp
note() { printf '%s\n' "$*" | tee -a "$LOG"; }
run() {
  name="$1"; shift
  t0=$(date +%s)
  if "$@" >> .tmp/mega_cycle_out.txt 2>&1; then st=OK; else st=FAIL; fi
  t1=$(date +%s)
  note "$st  $name  $((t1 - t0))s"
}

note "== mega cycle PHASE 2 started $(date) =="

# backnav re-runs here: phase 1 graded it with a bodyLocked term that matched index's by-design
# `overflow: hidden auto` shorthand and with section-kind targets held to a sheet's close rule.
run backnav_views2     node tools/prove_backnav_views.mjs
run journey            node tools/prove_journey.mjs
run double_fire        node tools/prove_double_fire.mjs
run back_out           node tools/prove_back_out.mjs
run modal_escape_live  node tools/prove_modal_escape_live.mjs
run quota_legible      node tools/prove_quota_legible.mjs
run zoom200            node tools/prove_zoom200.mjs
run session_died       node tools/prove_session_died.mjs
run session_expiry     node tools/prove_session_expiry.mjs
run dialog_a11y        node tools/prove_dialog_a11y.mjs
run dialog_session_died node tools/prove_dialog_session_died.mjs
run did_it_land        node tools/prove_did_it_land.mjs
run wrong_then_fix     node tools/prove_wrong_then_fix.mjs
run gateway_tenancy    python tools/validate_gateway_bypass.py
run hive_isolation     python tools/validate_hive_isolation.py

# convert everything again now that ALL reports are fresh, then the final whole-bank read
run convert_all2       python tools/bank_prover_reports.py --family all --apply
run validate_bank2     python tools/validate_live_mcp_bank.py

note "== mega cycle PHASE 2 finished $(date) =="
