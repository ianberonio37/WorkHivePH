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

  test('standards_alignment_report.json: every formula either supersets its standard OR is honestly partial', async () => {
    const r = await loadJson('standards_alignment_report.json');
    expect(r.summary).toBeDefined();
    for (const k of ['total_formulas', 'pass', 'fail', 'partial_honest', 'partial_silent']) {
      expect(r.summary[k], `summary.${k} must exist`).toBeDefined();
    }
    // Strictest invariant: zero SILENT partials (a formula labelled as full
    // when it actually misses the standard's required_inputs is the OEE-class
    // bug this auditor exists to catch).
    expect(r.summary.partial_silent, 'no formula may be a silent partial').toBe(0);
    expect(r.summary.fail,           'every formula must pass standards alignment').toBe(0);

    // Per-result contract
    expect(Array.isArray(r.results)).toBe(true);
    for (const row of r.results) {
      expect(row.formula_id).toBeTruthy();
      expect(typeof row.ok).toBe('boolean');
      expect(typeof row.is_partial).toBe('boolean');
    }
  });

  test('partial_label_honesty_report.json: zero pages display a partial without an honesty marker', async () => {
    const r = await loadJson('partial_label_honesty_report.json');
    expect(r.summary).toBeDefined();
    for (const k of [
      'pages_scanned', 'partial_formulas', 'pages_with_partial_display',
      'pages_with_honesty', 'pages_with_violation', 'total_violations',
    ]) {
      expect(r.summary[k], `summary.${k} must exist`).toBeDefined();
    }
    // Strictest invariant — zero UI-layer OEE-class bugs
    if (r.summary.total_violations > 0) {
      console.error(`Partial-label violations (${r.summary.total_violations}):`);
      for (const v of (r.violations as any[]).slice(0, 5)) {
        console.error(`  - ${v.page} · ${v.anchor_id} · ${v.formula_id}`);
      }
    }
    expect(r.summary.total_violations,
           'every partial-variant display must carry an honesty marker').toBe(0);
  });

  test('displayed_values_report.json: per-page classification of every value-display anchor', async () => {
    const r = await loadJson('displayed_values_report.json');
    expect(r.summary).toBeDefined();
    for (const k of [
      'pages_scanned', 'total_display_anchors', 'contracted',
      'uncontracted', 'raw', 'unknown', 'formula_ids_in_registry',
    ]) {
      expect(r.summary[k], `summary.${k} must exist`).toBeDefined();
    }
    // Bucket-sum invariant — every anchor classifies into exactly one of 4 buckets
    expect(
      r.summary.contracted + r.summary.uncontracted + r.summary.raw + r.summary.unknown
    ).toBe(r.summary.total_display_anchors);

    // Per-page contract — every entry is an object with the 4 buckets as arrays
    expect(typeof r.by_page).toBe('object');
    for (const [page, e] of Object.entries(r.by_page as Record<string, any>)) {
      for (const bucket of ['contracted', 'uncontracted', 'raw', 'unknown']) {
        expect(Array.isArray(e[bucket]), `${page}.${bucket} must be an array`).toBe(true);
      }
    }
  });

  test('ai_prompt_standards_report.json: schema (informational; report is the punch list)', async () => {
    const r = await loadJson('ai_prompt_standards_report.json');
    expect(r.summary).toBeDefined();
    for (const k of ['files_scanned', 'metric_hits', 'standards_cited', 'metric_uncited']) {
      expect(r.summary[k], `summary.${k} must exist`).toBeDefined();
    }
    // metric_hits should equal cited + uncited (no leaks)
    expect(r.summary.metric_hits).toBe(r.summary.standards_cited + r.summary.metric_uncited);
    expect(Array.isArray(r.findings)).toBe(true);
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

  test('standards.json + formula_contracts.json: cross-registry referential integrity', async () => {
    // Locks the Tier-S → Tier-E foreign-key contract at the registry-file level
    // so a future refactor that renames a standard_id without rewriting referencing
    // formulas fires red here BEFORE the audit (audit_standards_alignment) catches it
    // at a higher cost.
    const stds = (await loadJson('canonical/standards.json')).standards;
    const formulas = (await loadJson('canonical/formula_contracts.json')).formulas;
    const stdIds = new Set<string>(stds.map((s: any) => s.standard_id));

    const orphans: string[] = [];
    for (const f of formulas) {
      if (!stdIds.has(f.standard_id)) {
        orphans.push(`${f.formula_id} references unknown standard_id "${f.standard_id}"`);
      }
    }
    expect(orphans.length, `Tier S→E orphan references:\n${orphans.join('\n')}`).toBe(0);

    // And: every partial formula must declare both partial_reason and an
    // honest implemented_in label — same gate as the L2 anchor-consistency
    // spec, but enforced here against the FILE shape so a malformed registry
    // edit fails fast during pre-flight rather than at test-runtime.
    const silentPartials: string[] = [];
    for (const f of formulas) {
      if (f.partial_variant !== true) continue;
      if (!f.partial_reason || f.partial_reason.trim().length < 8) {
        silentPartials.push(`${f.formula_id}: partial_variant=true but partial_reason is empty/trivial`);
      }
      const impl = (f.implemented_in || '').toLowerCase();
      const fid  = (f.formula_id     || '').toLowerCase();
      if (!fid.endsWith('_partial') && !impl.includes('partial')) {
        silentPartials.push(`${f.formula_id}: partial_variant=true but no "partial" tag in formula_id or implemented_in`);
      }
    }
    expect(silentPartials.length, `silent partials in canonical/formula_contracts.json:\n${silentPartials.join('\n')}`).toBe(0);
  });

  test('Tier-S citation visibility: every implemented_in page cites the standard short_name (100% ratchet)', async () => {
    // Forward-only ratchet — locks the 100% citation visibility achieved
    // 2026-05-20 (commits 6643c87 + 4e5edab). Any future change that drops
    // visibility below 100% fires red here BEFORE merge. The Layer 2
    // anchor-consistency spec ran this as informational ("test E"); this
    // version is the hard regression gate so the achievement cannot quietly
    // erode as new formulas/pages land without their chip text.
    const fs = await import('fs');
    const path = await import('path');
    const root = path.resolve(__dirname, '..');
    const stds     = (await loadJson('canonical/standards.json')).standards;
    const formulas = (await loadJson('canonical/formula_contracts.json')).formulas;
    const stdShort: Record<string, string> = {};
    for (const s of stds) stdShort[s.standard_id] = s.short_name;

    const PAGE_RE = /([a-z0-9\-]+\.html)/gi;
    const fileCache: Record<string, string> = {};
    const gaps: string[] = [];
    let total = 0, present = 0;

    for (const f of formulas) {
      const short = stdShort[f.standard_id] || '';
      if (!short) continue;
      const impl = (f.implemented_in || '');
      const pages = (impl.match(PAGE_RE) || []).map((p: string) => p.toLowerCase());
      for (const p of pages) {
        total++;
        const fp = path.join(root, p);
        if (!(p in fileCache)) {
          try { fileCache[p] = fs.readFileSync(fp, 'utf8'); }
          catch { fileCache[p] = ''; }
        }
        if (fileCache[p].includes(short)) {
          present++;
        } else {
          gaps.push(`${p} renders ${f.formula_id} but does not cite "${short}"`);
        }
      }
    }
    if (gaps.length > 0) {
      console.error(`Tier-S citation gaps (${gaps.length}):\n` + gaps.slice(0, 6).join('\n'));
    }
    expect(gaps.length,
      `Tier-S citation visibility regressed below 100%. ${present}/${total} citations honoured. ` +
      `Either add the standard short_name to the page that renders the formula, or update ` +
      `canonical/formula_contracts.json implemented_in if the page no longer renders it.`).toBe(0);
  });
});
