#!/bin/sh
# mega_cycle3.sh — phase 3 of the 2026-08-22 re-earn cycle: the remaining gate PRODUCERS whose
# rows sat stale (component_states 330 rows, viewport_overflow 264, view_contrast 88, safe_area 66,
# number_labelled 66, effect_visible 32, count_matches_source, and the four psql write harnesses),
# then ONE restamp per gate against its fresh report, then the final whole-bank validate.
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

note "== mega cycle PHASE 3 started $(date) =="

run component_states  node tools/prove_component_states.mjs
run viewport_overflow node tools/prove_viewport_overflow.mjs
run view_contrast     node tools/prove_view_contrast.mjs
run safe_area         node tools/prove_safe_area.mjs
run number_labelled   node tools/prove_number_labelled.mjs
run effect_visible    node tools/prove_effect_visible.mjs
run count_matches     node tools/prove_count_matches_source.mjs
run values_survive    python tools/prove_values_survive_the_write.py
run field_names       python tools/prove_field_names_survive.py
run null_semantics    python tools/prove_null_semantics.py
run write_atomicity   python tools/prove_write_atomicity.py

# ── restamp EVERY gate whose report is now fresh (refusals are the rail working) ──
restamp() { run "restamp:$1" python tools/bank_gate_restamp.py --gate "$1" --report "$2" --apply; }
restamp ck_component_states      component_states_report.json
restamp cj_viewport_overflow     viewport_overflow_report.json
restamp cn_journey               journey_report.json
restamp cl_a11y_states           a11y_states_report.json
restamp cl_view_contrast         view_contrast_report.json
restamp cl_page_contrast         view_contrast_report.json
restamp cj_safe_area             safe_area_report.json
restamp cm_number_labelled       number_labelled_report.json
restamp co_session_died          session_died_report.json
restamp cf_effect_visible        effect_visible_report.json
restamp cf_count_matches_source  count_matches_source_report.json
restamp values_survive_write     values_survive_report.json
restamp field_names_survive      field_names_report.json
restamp null_semantics           null_semantics_report.json
restamp write_atomicity          write_atomicity_report.json
restamp hive-isolation           hive_isolation_report.json
restamp gateway-tenancy          gateway_tenancy_report.json
restamp cm_why_refused           why_refused_report.json
restamp cb_retry_path            retry_path_report.json
restamp co_back_out              back_out_report.json
restamp co_modal_escape_live     modal_escape_live_report.json
restamp cb_did_it_land           did_it_land_report.json
restamp cf_source_chip           source_chip_report.json
restamp cm_backnav_views         backnav_views_report.json
restamp cb_what_happens_next     what_happens_next_report.json
restamp cb_wrong_then_fix        wrong_then_fix_report.json
restamp cb_double_fire           double_fire_report.json
restamp cl_dialog_a11y           dialog_a11y_report.json
restamp cm_number_explained      number_explained_report.json
restamp cf_units_visible         units_visible_report.json
restamp cm_quota_legible         quota_legible_report.json
restamp cm_cost_views            cost_views_report.json
restamp cd_fallback_engaged      fallback_engaged_report.json
restamp cj_zoom200               zoom200_report.json
restamp cm_number_views          number_views_report.json
restamp cg_offline_views         offline_refusal_report.json
restamp cm_retry_views           retry_views_report.json
restamp co_dialog_session_died   dialog_session_died_report.json
restamp cm_rate_views            rate_views_report.json
restamp cc_failure_injection     failure_injection_report.json

run validate_bank3    python tools/validate_live_mcp_bank.py

note "== mega cycle PHASE 3 finished $(date) =="
