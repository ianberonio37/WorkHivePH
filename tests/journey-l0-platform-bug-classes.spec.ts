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
});
