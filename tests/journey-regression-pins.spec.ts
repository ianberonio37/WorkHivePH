/**
 * Tier 12 — Regression pins (7 scenarios, P0)
 *
 * Past bugs that MUST never reappear. These assertions are STATIC
 * (file content checks + report parsing) so they run with zero setup.
 *
 * Each test pins down a specific historical bug from the 2026-05-18/19
 * session. The names use scenario ID `M{N}_<descriptor>` for sentinel
 * auto-match traceability.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync, statSync, existsSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

function listProductionHtml(): string[] {
  return readdirSync(ROOT)
    .filter((f) => f.endsWith('.html')
      && !/-test\.html$/.test(f)
      && !/\.backup\d*\.html$/.test(f)
      && statSync(resolve(ROOT, f)).isFile());
}

test.describe('Tier 12 — Regression pins', () => {

  test('M1_ph_intelligence_eschtml_quote_escape: utils.js escHtml replaces single-quote', async () => {
    // WHY: ph-intelligence had an inline _escHtml that dropped the &#39; escape — real stored-XSS
    // PIN: ensure the canonical escHtml in utils.js still covers all 5 chars
    const utils = readFileSync(resolve(ROOT, 'utils.js'), 'utf-8');
    expect(utils, "utils.js escHtml must escape ' to &#39;")
      .toMatch(/replace\(\s*\/'\/g\s*,\s*['"]&#39;['"]/);
    // And ph-intelligence must NOT redefine escHtml inline.
    const ph = readFileSync(resolve(ROOT, 'ph-intelligence.html'), 'utf-8');
    expect(ph, 'ph-intelligence must not define escHtml inline (single source: utils.js)')
      .not.toMatch(/function\s+escHtml\s*\(/);
  });

  test('M2_cp1252_guard_on_every_validator: all validate_*.py install the Windows stdout guard', async () => {
    // WHY: 33 latent Windows crashes patched 2026-05-18; the validator gate locks this in
    const files = readdirSync(ROOT).filter((f) => f.startsWith('validate_') && f.endsWith('.py'));
    const missing: string[] = [];
    for (const f of files) {
      const c = readFileSync(resolve(ROOT, f), 'utf-8');
      if (!/sys\.stdout\s*=\s*io\.TextIOWrapper/.test(c)) missing.push(f);
    }
    expect(missing, 'every validator must install the cp1252 stdout guard').toEqual([]);
  });

  test('M3_main_landmark_on_every_page: every production HTML has <main>', async () => {
    // WHY: 21 a11y-broken pages fixed 2026-05-18; pin so they stay fixed
    const missing: string[] = [];
    for (const f of listProductionHtml()) {
      const c = readFileSync(resolve(ROOT, f), 'utf-8');
      if (!/<main\b/i.test(c)) missing.push(f);
    }
    expect(missing, 'every production page must include <main>').toEqual([]);
  });

  test('M4_no_inline_eschtml_anywhere: utils.js is the single source of truth', async () => {
    // WHY: 8 inline escHtml dedup'd 2026-05-18, security skill rule
    const offenders: string[] = [];
    for (const f of listProductionHtml()) {
      const c = readFileSync(resolve(ROOT, f), 'utf-8');
      if (/function\s+escHtml\s*\(/.test(c)) offenders.push(f);
    }
    expect(offenders, 'no HTML page should redefine escHtml inline').toEqual([]);
  });

  test('M5_edge_fns_import_shared_cors: marketplace + project fns use _shared/cors.ts', async () => {
    // WHY: 6 fns migrated 2026-05-18; only marketplace-webhook keeps wildcard
    const targets = [
      'marketplace-checkout', 'marketplace-connect-onboard', 'marketplace-connect-status',
      'marketplace-release', 'project-orchestrator', 'project-progress',
    ];
    const offenders: string[] = [];
    for (const fnName of targets) {
      const p = resolve(ROOT, 'supabase', 'functions', fnName, 'index.ts');
      if (!existsSync(p)) continue;
      const c = readFileSync(p, 'utf-8');
      const hasImport = /from\s+['"]\.\.\/_shared\/cors\.ts['"]/.test(c);
      const hasInlineFn = /^function\s+getCorsHeaders\s*\(/m.test(c);
      if (!hasImport || hasInlineFn) offenders.push(fnName);
    }
    expect(offenders, 'every listed fn must import getCorsHeaders from _shared/cors.ts (and not redefine inline)').toEqual([]);
  });

  test('M6_canonical_overlap_allowlist_fresh: documented surface overlaps still match the registry', async () => {
    // WHY: stale allowlist entries hide real consolidation work; the validator already pins this
    const reportPath = resolve(ROOT, 'canonical_overlap_report.json');
    expect(existsSync(reportPath), 'run validate_canonical_overlap before this spec').toBeTruthy();
    const r = JSON.parse(readFileSync(reportPath, 'utf-8'));
    expect(r.census.stale_allowlist_entries,
      'no stale entries in canonical_overlap_allowlist.json').toBe(0);
  });

  test('M7_no_phantom_views_in_edge_fns: no v_*_truth referenced but undefined', async () => {
    // WHY: platform-scraper had v_pm_truth + v_inventory_truth (renamed away); fixed 2026-05-19
    const regPath = resolve(ROOT, 'canonical_registry.json');
    expect(existsSync(regPath), 'run mine_canonical_registry before this spec').toBeTruthy();
    const reg = JSON.parse(readFileSync(regPath, 'utf-8'));
    const phantoms = Object.keys(reg.phantom_tables || {});
    expect(phantoms, 'no phantom tables/views referenced in code without migration').toEqual([]);
  });
});
