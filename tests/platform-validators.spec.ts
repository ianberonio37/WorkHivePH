/**
 * platform-validators.spec.ts — Sentinel behavioral coverage for the 3
 * L-1 / L-1.5 validators added in the 2026-05-19 session.
 *
 * The Sentinel coverage map matches checks to specs by substring:
 *   test('<check_name>: ...', ...)  ← literal check_name from CHECK_NAMES
 *
 * Each test below mirrors a validator's invariant by reading the validator's
 * own report JSON (no UI / DB needed -- the validators themselves enforced
 * the invariant; these specs assert the report shape proves it).
 *
 * Covered:
 *   validate_loads_utils_js          → loads_utils_js, allowlist_freshness
 *   validate_validator_cp1252_guard  → cp1252_guard_present, allowlist_freshness, guard_placement
 *   validate_canonical_overlap       → phantom_table, documented_overlap, documented_column_pair, allowlist_freshness
 *
 * Unique check names (7) covered with one test each.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

function readReport(name: string): any {
  const p = resolve(ROOT, name);
  if (!existsSync(p)) {
    throw new Error(`Validator report missing: ${name}. Run the validator first.`);
  }
  return JSON.parse(readFileSync(p, 'utf-8'));
}


test.describe('Layer 0 validator behavioral coverage (2026-05-19 additions)', () => {

  test('loads_utils_js: every non-allowlisted root HTML page loads utils.js', () => {
    const r = readReport('loads_utils_js_report.json');
    // Validator wrote: { summary: { fail: N, ... }, census, allowlist, issues }
    expect(r.summary.fail, 'loads_utils_js check should have 0 failures').toBe(0);
    // Non-allowlisted compliant count should exceed zero (else scope misconfig).
    expect(r.summary.required_and_compliant, 'at least 1 page must be required-and-compliant').toBeGreaterThan(0);
  });

  test('cp1252_guard_present: every validate_*.py installs the Windows cp1252 stdout guard', () => {
    const r = readReport('validator_cp1252_guard_report.json');
    expect(r.summary.fail, 'cp1252_guard_present check should have 0 failures').toBe(0);
    // Every validator file should appear in the compliant census.
    expect(r.summary.compliant, 'compliant count must be > 0').toBeGreaterThan(180);
    expect(r.summary.violating, 'no validators should be missing the guard').toBe(0);
  });

  test('guard_placement: cp1252 guard appears before the first executable print()', () => {
    const r = readReport('validator_cp1252_guard_report.json');
    // L3 is informational (SKIP-level). The census tracks deep_placement count
    // -- after the placement-rule refinement, this should be 0.
    expect(r.summary.deep_placement, 'no validators should have guard placed after first print()').toBe(0);
  });

  test('phantom_table: no tables referenced in code but undefined in migrations', () => {
    const r = readReport('canonical_overlap_report.json');
    expect(r.census.phantom_tables, 'phantom_tables count must be 0 (real bug class)').toBe(0);
    // No phantom-table issues in the issues array.
    const phantomIssues = (r.issues || []).filter((i: any) => i.check === 'phantom_table');
    expect(phantomIssues, 'no phantom_table issues should be raised').toEqual([]);
  });

  test('documented_overlap: every surface-pair overlap is in the allowlist', () => {
    const r = readReport('canonical_overlap_report.json');
    expect(r.census.surface_overlaps_undocumented,
      'every surface-pair overlap must be documented in canonical_overlap_allowlist.json').toBe(0);
    expect(r.census.surface_overlaps_total).toBe(r.census.surface_overlaps_allowlisted);
  });

  test('documented_column_pair: every near-duplicate column pair is allowlisted', () => {
    const r = readReport('canonical_overlap_report.json');
    expect(r.census.near_dup_cols_undocumented,
      'every near-duplicate column pair must be documented').toBe(0);
    expect(r.census.near_dup_cols_total).toBe(r.census.near_dup_cols_allowlisted);
  });

  test('allowlist_freshness: no allowlist entries are stale (every entry still matches a real overlap or violation)', () => {
    // canonical_overlap_report.json tracks stale allowlist entries.
    const overlap = readReport('canonical_overlap_report.json');
    expect(overlap.census.stale_allowlist_entries,
      'no stale entries in canonical_overlap_allowlist.json').toBe(0);

    // validator_cp1252_guard_report.json also has allowlist freshness baked in.
    const guard = readReport('validator_cp1252_guard_report.json');
    expect(guard.summary.allowlisted, 'no validators should be on a now-graduated allowlist').toBe(0);

    // loads_utils_js_report.json -- allowlisted_graduated must be 0.
    const utils = readReport('loads_utils_js_report.json');
    expect(utils.summary.allowlisted_graduated || 0,
      'no allowlisted pages should have graduated without being removed').toBe(0);
  });
});
