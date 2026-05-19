/**
 * Canonical Lineage Sentinel (Layer 2).
 * =====================================
 *
 * Locks the output contract of the two Layer -1.5 auditors that today's
 * Mega Gate now runs:
 *
 *   - audit_calm_dashboard_canonical.py  (forward: dashboard -> v_*_truth)
 *   - audit_phantom_captures.py           (reverse: capture -> consumer)
 *
 * The auditors regenerate `calm_canonical_audit_report.json` and
 * `phantom_captures_report.json` on every Mega Gate run. This spec
 * enforces that:
 *   (a) both reports exist after a run,
 *   (b) the calm-canonical report has a populated `by_page` array with
 *       the required summary fields,
 *   (c) the phantom report distinguishes alive/phantom/allowlisted.
 *
 * If a future refactor breaks the report shape, this spec fires red and
 * the hardening-loop / Sentinel pipeline catches the schema drift before
 * downstream consumers (cron dashboards, AI prompts, mega-gate badges).
 */
import { test, expect } from '@playwright/test';
import { promises as fs } from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');

async function loadJson(rel: string): Promise<any> {
  const text = await fs.readFile(path.join(ROOT, rel), 'utf8');
  return JSON.parse(text);
}

test.describe('Canonical Lineage Sentinel (L2 report-shape contract)', () => {
  test('calm_canonical_audit_report.json: schema + non-trivial coverage', async () => {
    const r = await loadJson('calm_canonical_audit_report.json');

    // Required summary keys
    expect(r.summary).toBeDefined();
    for (const k of [
      'calm_opted_in_pages', 'compliant_pages', 'conformance',
      'total_canonical_reads', 'total_drift_reads', 'total_gap_reads',
      'total_allowed_reads', 'v_truth_views_in_registry',
    ]) {
      expect(r.summary[k], `summary.${k} must exist`).toBeDefined();
    }

    // Per-page detail must enumerate every opted-in dashboard.
    expect(Array.isArray(r.by_page)).toBe(true);
    expect(r.by_page.length).toBe(r.summary.calm_opted_in_pages);

    // Each row must classify into the 4 buckets.
    for (const row of r.by_page) {
      expect(row.page).toBeTruthy();
      expect(Array.isArray(row.canonical)).toBe(true);
      expect(Array.isArray(row.drift)).toBe(true);
      expect(Array.isArray(row.gap)).toBe(true);
      expect(Array.isArray(row.allowed)).toBe(true);
      expect(typeof row.compliant).toBe('boolean');
    }

    // Sanity: at least one truth view exists in the registry, and the
    // platform has at least one canonical-shaped read somewhere.
    expect(r.summary.v_truth_views_in_registry).toBeGreaterThan(0);
    expect(r.summary.total_canonical_reads).toBeGreaterThan(0);
  });

  test('calm_canonical_audit_report.json: gap+drift counts are tracked', async () => {
    const r = await loadJson('calm_canonical_audit_report.json');
    // gap_counts / drift_counts are the per-table aggregates the
    // hardening loop reads to prioritise fixes. Both must be objects
    // (may be empty if the platform is 100% canonical).
    expect(typeof r.gap_counts).toBe('object');
    expect(typeof r.drift_counts).toBe('object');
  });

  test('phantom_captures_report.json: schema + bucket totals add up', async () => {
    const r = await loadJson('phantom_captures_report.json');

    expect(r.summary).toBeDefined();
    const s = r.summary;
    for (const k of [
      'total_captures_discovered', 'framework_skipped',
      'alive', 'phantom', 'allowlisted',
    ]) {
      expect(s[k], `summary.${k} must exist`).toBeDefined();
    }

    // alive + phantom + allowlisted should equal total minus framework-skipped
    expect(s.alive + s.phantom + s.allowlisted)
      .toBe(s.total_captures_discovered - s.framework_skipped);

    // by_name keys exist
    expect(typeof r.by_name).toBe('object');

    // Every entry classifies into one of three statuses
    const allowed = new Set(['alive', 'phantom', 'allowlisted']);
    for (const [name, v] of Object.entries(r.by_name)) {
      const row = v as any;
      expect(allowed.has(row.status), `${name} status must be alive/phantom/allowlisted (got ${row.status})`).toBe(true);
      expect(typeof row.consumer_count).toBe('number');
      expect(Array.isArray(row.capture_sites)).toBe(true);
    }
  });

  test('phantom_captures_report.json: zero unjustified phantoms (regression gate)', async () => {
    const r = await loadJson('phantom_captures_report.json');
    const unjustified = Object.values(r.by_name as Record<string, any>)
      .filter(v => v.status === 'phantom');
    if (unjustified.length > 0) {
      console.error(
        `Phantom captures detected (${unjustified.length}). ` +
        `Either wire a consumer or add a phantom-allow comment:\n` +
        unjustified.slice(0, 10).map(v => `  - ${v.name}`).join('\n')
      );
    }
    expect(unjustified.length, 'no unjustified phantom captures should ship').toBe(0);
  });

  test('phantom_columns_report.json: schema + per-table bucket totals', async () => {
    const r = await loadJson('phantom_columns_report.json');
    expect(r.summary).toBeDefined();
    for (const k of ['tables_scanned', 'total_columns', 'alive', 'phantom', 'universal_skipped', 'allowlisted']) {
      expect(r.summary[k], `summary.${k} must exist`).toBeDefined();
    }
    // alive + phantom + universal + allowlisted should equal total
    expect(r.summary.alive + r.summary.phantom + r.summary.universal_skipped + r.summary.allowlisted)
      .toBe(r.summary.total_columns);
    // by_table contract
    expect(typeof r.by_table).toBe('object');
  });

  test('tier_contracts_report.json: 4-tier shape + zero broken chain references', async () => {
    const r = await loadJson('tier_contracts_report.json');
    expect(Array.isArray(r.tiers)).toBe(true);
    expect(r.tiers.length).toBe(4);

    // Tier identity: Fuel / Engine / Brain / Glue
    const tierNames = r.tiers.map((t: any) => t.tier);
    expect(tierNames[0]).toContain('Fuel');
    expect(tierNames[1]).toContain('Engine');
    expect(tierNames[2]).toContain('Brain');
    expect(tierNames[3]).toContain('lineage');

    // Chain integrity: no broken references anywhere
    let totalBroken = 0;
    for (const t of r.tiers) {
      const broken = (t.broken_references as string[] | undefined) || [];
      totalBroken += broken.length;
      if (broken.length > 0) {
        console.error(`Tier ${t.tier} has ${broken.length} broken refs:\n` +
          broken.slice(0, 6).map(b => `  - ${b}`).join('\n'));
      }
    }
    expect(totalBroken, 'tier contract registry must reference only known IDs').toBe(0);
  });
});
