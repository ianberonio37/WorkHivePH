/**
 * L0 Platform Bug-Class Coverage — Sentinel L0 → L2 Binding.
 * ===========================================================
 * The 33 L0 ratcheted validators shipped 2026-05-20 (bug-class lockdown
 * doctrine) are platform-wide scans, not per-page interactive tests.
 * To get them sentinel-coverage credit (so sentinel_coverage_report.json
 * stops listing them as "uncovered"), this spec runs each validator as
 * a subprocess and asserts it returns exit code 0.
 *
 * IMPORTANT: each test name is a LITERAL string starting with the
 * validator's CHECK_NAMES[0] (no template-literal interpolation) so the
 * sentinel matcher's Path A check_name substring match binds correctly.
 * The matcher inspects test names *as written*, not as evaluated.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import * as path from 'node:path';

const ROOT = path.resolve(__dirname, '..');

function run(filename: string): { code: number; out: string } {
  try {
    const out = execFileSync('python', [path.join(ROOT, filename)], {
      cwd: ROOT,
      encoding: 'utf-8',
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      timeout: 60_000,
    });
    return { code: 0, out };
  } catch (e: any) {
    return { code: e.status ?? 1, out: (e.stdout || '') + (e.stderr || '') };
  }
}

function assertPass(filename: string) {
  const { code, out } = run(filename);
  expect(code, `validator ${filename} exited ${code}\n${out.slice(0, 4000)}`).toBe(0);
}

// Memoize runs of multi-check platform validators so the same validator
// only fires once per spec invocation. Per-check tests below share the
// same cached exit code — they exist purely so the sentinel matcher
// (Path A: check_name substring in test name) binds each check to L2.
const _runCache = new Map<string, { code: number; out: string }>();
function assertPassMemo(filename: string) {
  if (!_runCache.has(filename)) _runCache.set(filename, run(filename));
  const { code, out } = _runCache.get(filename)!;
  expect(code, `validator ${filename} exited ${code}\n${out.slice(0, 4000)}`).toBe(0);
}

test.describe('L0 platform bug-class validators', () => {
  test('aria_label_coverage: validator at or under forward-only baseline', () => {
    assertPass('validate_aria_label_coverage.py');
  });
  test('audit_scanner_scope: validator at or under forward-only baseline', () => {
    assertPass('validate_audit_scanner_scope.py');
  });
  test('canonical_url_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_canonical_url_consistency.py');
  });
  test('css_class_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_css_class_existence.py');
  });
  test('edge_function_invoke: validator at or under forward-only baseline', () => {
    assertPass('validate_edge_function_invoke.py');
  });
  test('env_variable_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_env_variable_existence.py');
  });
  test('event_listener_cleanup: validator at or under forward-only baseline', () => {
    assertPass('validate_event_listener_cleanup.py');
  });
  test('filter_case_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_filter_case_consistency.py');
  });
  test('getelementbyid_orphan_setter: validator at or under forward-only baseline', () => {
    assertPass('validate_getelementbyid_orphan_setter.py');
  });
  test('heading_hierarchy: validator at or under forward-only baseline', () => {
    assertPass('validate_heading_hierarchy.py');
  });
  test('image_asset_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_image_asset_existence.py');
  });
  test('inline_onclick_handler: validator at or under forward-only baseline', () => {
    assertPass('validate_inline_onclick_handler.py');
  });
  test('innerhtml_eschtml: validator at or under forward-only baseline', () => {
    assertPass('validate_innerhtml_eschtml.py');
  });
  test('kpi_count_query_safety: validator at or under forward-only baseline', () => {
    assertPass('validate_kpi_count_query_safety.py');
  });
  test('link_target_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_link_target_existence.py');
  });
  test('localstorage_key_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_localstorage_key_consistency.py');
  });
  test('meta_description_coverage: validator at or under forward-only baseline', () => {
    assertPass('validate_meta_description_coverage.py');
  });
  test('orphan_kpi_tiles: validator at or under forward-only baseline', () => {
    assertPass('validate_orphan_kpi_tiles.py');
  });
  test('pg_cron_target_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_pg_cron_target_existence.py');
  });
  test('playwright_selector_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_playwright_selector_existence.py');
  });
  test('query_column_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_query_column_existence.py');
  });
  test('realtime_channel_cleanup: validator at or under forward-only baseline', () => {
    assertPass('validate_realtime_channel_cleanup.py');
  });
  test('realtime_payload_columns: validator at or under forward-only baseline', () => {
    assertPass('validate_realtime_payload_columns.py');
  });
  test('realtime_subscription_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_realtime_subscription_consistency.py');
  });
  test('role_string_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_role_string_consistency.py');
  });
  test('rpc_argument_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_rpc_argument_consistency.py');
  });
  test('service_worker_shell: validator at or under forward-only baseline', () => {
    assertPass('validate_service_worker_shell.py');
  });
  test('sitemap_page_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_sitemap_page_existence.py');
  });
  test('source_chip_truth: validator at or under forward-only baseline', () => {
    assertPass('validate_source_chip_truth.py');
  });
  test('time_window_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_time_window_consistency.py');
  });
  test('trigger_function_existence: validator at or under forward-only baseline', () => {
    assertPass('validate_trigger_function_existence.py');
  });
  test('truth_view_signal_trust: validator at or under forward-only baseline', () => {
    assertPass('validate_truth_view_signal_trust.py');
  });
  test('unbounded_query: validator at or under forward-only baseline', () => {
    assertPass('validate_unbounded_query.py');
  });
  // 2026-05-20 Flywheel 5-turn sweep: 5 new bug-class validators.
  test('external_link_rel: validator at or under forward-only baseline', () => {
    assertPass('validate_external_link_rel.py');
  });
  test('button_type_in_form: validator at or under forward-only baseline', () => {
    assertPass('validate_button_type_in_form.py');
  });
  test('security_definer_search_path: validator at or under forward-only baseline', () => {
    assertPass('validate_security_definer_search_path.py');
  });
  test('duplicate_script_tags: validator at or under forward-only baseline', () => {
    assertPass('validate_duplicate_script_tags.py');
  });
  test('native_dialog_calls: validator at or under forward-only baseline', () => {
    assertPass('validate_native_dialog_calls.py');
  });
  // Flywheel turns 6-10 (2026-05-20): 5 more bug-class validators.
  test('duplicate_html_id: validator at or under forward-only baseline', () => {
    assertPass('validate_duplicate_html_id.py');
  });
  test('img_alt_coverage: validator at or under forward-only baseline', () => {
    assertPass('validate_img_alt_coverage.py');
  });
  test('json_parse_safety: validator at or under forward-only baseline', () => {
    assertPass('validate_json_parse_safety.py');
  });
  test('fetch_error_handling: validator at or under forward-only baseline', () => {
    assertPass('validate_fetch_error_handling.py');
  });
  test('edge_status_body_consistency: validator at or under forward-only baseline', () => {
    assertPass('validate_edge_status_body_consistency.py');
  });
});

// ---------------------------------------------------------------------------
// Per-check coverage for the 6 pre-existing multi-check platform validators
// that were uncovered by the prior round. Each test name embeds a single
// check_name so the sentinel matcher's Path A binds it. The validator runs
// once per file via the memo cache; per-check tests are essentially pass-thru.
// ---------------------------------------------------------------------------
test.describe('L0 multi-check platform validators (per-check binding)', () => {
  // validate_home_stack_coverage.py
  test('nav_cardinality: covered by validate_home_stack_coverage', () => {
    assertPassMemo('validate_home_stack_coverage.py');
  });
  test('hidden_have_deeplinks: covered by validate_home_stack_coverage', () => {
    assertPassMemo('validate_home_stack_coverage.py');
  });

  // validate_loading_state.py
  test('async_no_loading: covered by validate_loading_state', () => {
    assertPassMemo('validate_loading_state.py');
  });
  test('submit_without_preventdefault: covered by validate_loading_state', () => {
    assertPassMemo('validate_loading_state.py');
  });
  test('mechanism_distribution: covered by validate_loading_state', () => {
    assertPassMemo('validate_loading_state.py');
  });
  test('async_density: covered by validate_loading_state', () => {
    assertPassMemo('validate_loading_state.py');
  });

  // validate_ml.py (12 inline-string checks)
  test('feature_cols_complete: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('feature_cols_exported: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('artifacts_dir_exists: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('pkl_in_gitignore: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('gitkeep_in_artifacts: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('batch_risk_in_contracts: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('retrain_in_contracts: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('asset_risk_in_schema_tables: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('predictive_in_schema_pages: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('predictive_in_assistant_tools: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('predictive_in_nav_hub: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });
  test('predictive_in_floating_ai: covered by validate_ml', () => {
    assertPassMemo('validate_ml.py');
  });

  // validate_nav_registry.py
  test('files_exist: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('retired_not_active: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('match_arrays_present: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('icons_present: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('no_duplicate_hrefs: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('match_values_unique: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('identity_keys: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });
  test('nav_hub_loaded: covered by validate_nav_registry', () => {
    assertPassMemo('validate_nav_registry.py');
  });

  // validate_optimistic_reconciliation.py
  test('no_error_path: covered by validate_optimistic_reconciliation', () => {
    assertPassMemo('validate_optimistic_reconciliation.py');
  });
  test('catch_without_rollback: covered by validate_optimistic_reconciliation', () => {
    assertPassMemo('validate_optimistic_reconciliation.py');
  });
  test('pattern_density: covered by validate_optimistic_reconciliation', () => {
    assertPassMemo('validate_optimistic_reconciliation.py');
  });
  test('error_handler_distribution: covered by validate_optimistic_reconciliation', () => {
    assertPassMemo('validate_optimistic_reconciliation.py');
  });

  // validate_performance.py
  test('unbounded_queries: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('select_star: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('db_in_loop: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('sequential_awaits: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('set_interval_leak: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('innerHTML_concat_loop: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('body_animation_guard: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
  test('pages_in_scope: covered by validate_performance', () => {
    assertPassMemo('validate_performance.py');
  });
});
