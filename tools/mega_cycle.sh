#!/bin/sh
# mega_cycle.sh — the ONE final re-earn cycle after a fix-wave (2026-08-22).
# Re-runs every report-producing family prover ONCE, serially (Playwright fleets must not
# overlap on this host), so every edited page's bank rows re-earn against fresh reports,
# then converts all families and re-validates the whole bank.
#
# Usage:  sh tools/mega_cycle.sh            (from the project root; logs to .tmp/mega_cycle.log)
# Each line of the log is "<status> <prover> <seconds>s" — a FAIL line means the prover
# exited non-zero (real findings or a crashed run: read its own report/output before assuming).
set -u
LOG=.tmp/mega_cycle.log
mkdir -p .tmp
: > "$LOG"
note() { printf '%s\n' "$*" | tee -a "$LOG"; }

run() {
  name="$1"; shift
  t0=$(date +%s)
  if "$@" >> .tmp/mega_cycle_out.txt 2>&1; then st=OK; else st=FAIL; fi
  t1=$(date +%s)
  note "$st  $name  $((t1 - t0))s"
}

note "== mega cycle started $(date) =="

# ── the VIEW families (share view_pass.mjs, which changed this wave) ──
run why_refused      node tools/prove_why_refused.mjs
run cost_views       node tools/prove_cost_views.mjs
run rate_views       node tools/prove_rate_views.mjs
run number_views     node tools/prove_number_views.mjs
run backnav_views    node tools/prove_backnav_views.mjs
run retry_views      node tools/prove_retry_views.mjs
run fallback_views   node tools/prove_fallback_views.mjs
# offline_refusal is PER-CASE (a bare run exits 2 asking for --case); the per-case report
# artifact accumulates keyed by case, so serial re-runs rebuild the whole artifact.
for c in calc resume strategy logbook exam hail contact send reaction dismiss publish signup \
         persona partdelete newtask newproject delproject kick join reply scopestatus lessons; do
  run "offline_refusal:$c" node tools/prove_offline_refusal.mjs --case "$c"
done

# ── page-level families whose subject pages were edited in the whReadError sweep ──
run failure_injection node tools/prove_failure_injection.mjs
run a11y_states       node tools/prove_a11y_states.mjs
run session_expiry    node tools/prove_session_expiry_read.mjs
run units_visible     node tools/prove_units_visible.mjs
run source_chip       node tools/prove_source_chip.mjs
run number_explained  node tools/prove_number_explained.mjs
run dialog_layout     node tools/prove_dialog_layout.mjs
run dialog_back_out   node tools/prove_dialog_back_out.mjs
run what_happens_next node tools/prove_what_happens_next.mjs
run retry_path        node tools/prove_retry_path.mjs
run fallback_engaged  node tools/prove_fallback_engaged.mjs

# ── convert every family against the fresh reports, then validate ──
run convert_all      python tools/bank_prover_reports.py --family all --apply
run validate_bank    python tools/validate_live_mcp_bank.py

note "== mega cycle finished $(date) =="
