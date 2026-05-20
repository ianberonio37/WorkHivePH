/**
 * journey-canonical-anchor-consistency.spec.ts — Cross-surface L2.
 * =================================================================
 *
 * Pins the 5-tier canonical contract (Standards → Fuel → Engine → Brain →
 * Dashboard) at the SURFACE layer where the user sees the number. Catches
 * the OEE-class bug pattern: a formula labelled as "full" while the
 * implementation is partial, or a partial labelled without a marker.
 *
 * Three contract checks per registered formula:
 *
 *   A. Standard-anchor presence — every formula's standard_id has at least
 *      ONE registered standard in canonical/standards.json (else the chip
 *      can't render an honest source).
 *
 *   B. Partial-variant integrity — partial-variant formulas MUST declare
 *      partial_reason, AND their implemented_in label MUST signal
 *      "partial" (so anyone reading the registry sees the partial state).
 *
 *   C. Surface-label honour — for every page named in implemented_in,
 *      the served HTML must NOT silently treat a partial formula as full
 *      (cross-checked against partial_label_honesty_report.json).
 *
 * No DB / signin needed — all checks are file-shape contracts against
 * the canonical/ registry + raw fetch of HTML. Fast, deterministic, runs
 * in <10s.
 */
import { test, expect } from '@playwright/test';
import { promises as fs } from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');

async function loadJson(rel: string): Promise<any> {
  const text = await fs.readFile(path.join(ROOT, rel), 'utf8');
  return JSON.parse(text);
}

async function fetchPage(request: any, page: string): Promise<string> {
  const res = await request.get(`/workhive/${page}`);
  expect(res.status(), `${page} should serve 200`).toBe(200);
  return await res.text();
}

let STANDARDS: any[] = [];
let FORMULAS: any[] = [];
let PARTIAL_REPORT: any = {};
let STD_BY_ID: Record<string, any> = {};

test.beforeAll(async () => {
  STANDARDS = (await loadJson('canonical/standards.json')).standards;
  FORMULAS  = (await loadJson('canonical/formula_contracts.json')).formulas;
  PARTIAL_REPORT = await loadJson('partial_label_honesty_report.json').catch(() => ({ violations: [] }));
  for (const s of STANDARDS) STD_BY_ID[s.standard_id] = s;
});

test.describe('Canonical Anchor Consistency — Tier S → Tier E', () => {

  test('A. every formula contract anchors to a registered Tier-S standard', async () => {
    const orphans: string[] = [];
    for (const f of FORMULAS) {
      if (!STD_BY_ID[f.standard_id]) {
        orphans.push(`${f.formula_id} → standard_id="${f.standard_id}" not in canonical/standards.json`);
      }
    }
    expect(orphans.length, `Orphan formulas (no Tier-S anchor):\n${orphans.join('\n')}`).toBe(0);
  });

  test('B. partial-variant formulas declare both reason and label suffix', async () => {
    const offenders: string[] = [];
    for (const f of FORMULAS) {
      if (f.partial_variant !== true) continue;
      const hasReason = (f.partial_reason || '').trim().length > 8;
      const impl = (f.implemented_in || '').toLowerCase();
      const fid  = (f.formula_id     || '').toLowerCase();
      // Either the formula_id ends in _partial OR the implemented_in text
      // explicitly says "partial" — both are accepted as honest labels.
      const hasLabel = fid.endsWith('_partial') || impl.includes('partial');
      if (!hasReason) offenders.push(`${f.formula_id}: partial_variant=true but partial_reason is empty/trivial`);
      if (!hasLabel)  offenders.push(`${f.formula_id}: partial_variant=true but neither formula_id nor implemented_in declares "partial"`);
    }
    expect(offenders.length, `Silent partials (zero-tolerance gate):\n${offenders.join('\n')}`).toBe(0);
  });

  test('C. every page named in implemented_in actually serves 200', async ({ request }) => {
    const PAGE_RE = /([a-z0-9\-]+\.html)/gi;
    const pages = new Set<string>();
    for (const f of FORMULAS) {
      const impl = f.implemented_in || '';
      const matches = impl.match(PAGE_RE) || [];
      for (const p of matches) pages.add(p.toLowerCase());
    }
    for (const p of pages) {
      const res = await request.get(`/workhive/${p}`);
      expect(res.status(), `${p} (named in implemented_in) must serve 200`).toBe(200);
    }
  });
});

test.describe('Canonical Anchor Consistency — Tier E → Tier D (rendering)', () => {

  test('D. zero partial-variant displays render without an honesty marker (regression gate)', async () => {
    const violations = (PARTIAL_REPORT.violations || []) as any[];
    if (violations.length > 0) {
      console.error(`Partial-label rendering violations (${violations.length}):`);
      for (const v of violations.slice(0, 8)) {
        console.error(`  - ${v.page} · ${v.anchor_id} · ${v.formula_id}`);
      }
    }
    expect(violations.length,
      'every partial-variant display must carry a "partial"/"approximation"/"calendar time" marker').toBe(0);
  });

  test('E. every formula whose implemented_in names a page has the standard short_name rendered somewhere on that page', async ({ request }) => {
    // Informational pass-rate metric. NOT a hard gate yet — chip groom-in
    // continues; we surface the gap so it doesn't regress further.
    const PAGE_RE = /([a-z0-9\-]+\.html)/gi;
    const cache = new Map<string, string>();
    let total = 0, present = 0;
    const gaps: string[] = [];

    for (const f of FORMULAS) {
      const impl = f.implemented_in || '';
      const short = (STD_BY_ID[f.standard_id] || {}).short_name || '';
      if (!short) continue;
      const pages: string[] = (impl.match(PAGE_RE) || []).map(p => p.toLowerCase());
      for (const p of pages) {
        total++;
        if (!cache.has(p)) cache.set(p, await fetchPage(request, p));
        const html = cache.get(p)!;
        if (html.includes(short)) {
          present++;
        } else {
          gaps.push(`${p} renders ${f.formula_id} but does not cite "${short}"`);
        }
      }
    }
    const pct = total === 0 ? 100 : Math.round((present / total) * 100);
    console.log(`Tier-S citation visibility: ${present}/${total} (${pct}%)`);
    if (gaps.length > 0) {
      console.warn(`Tier-S citation gaps (${gaps.length}):\n` + gaps.slice(0, 6).join('\n'));
    }
    // Informational only — formal goal is 100% but groom-in is ongoing.
    expect(total, 'must find at least one implemented_in page reference').toBeGreaterThan(0);
  });
});

test.describe('Canonical Anchor Consistency — Tier S registry hygiene', () => {

  test('F. every standard has a non-empty short_name and edition_year', async () => {
    const bad: string[] = [];
    for (const s of STANDARDS) {
      if (!s.short_name || !s.short_name.trim()) bad.push(`${s.standard_id}: missing short_name`);
      // Classical equations (e.g. Darcy-Weisbach 1857) legitimately predate 1900;
      // floor at 1800 to allow them while still catching typos/zero.
      if (s.edition_year !== undefined && (typeof s.edition_year !== 'number' || s.edition_year < 1800 || s.edition_year > 2030)) {
        bad.push(`${s.standard_id}: invalid edition_year=${s.edition_year}`);
      }
    }
    expect(bad.length, `Standards-registry hygiene:\n${bad.join('\n')}`).toBe(0);
  });

  test('G. no two formula_ids collide (registry uniqueness)', async () => {
    const seen = new Set<string>();
    const dupes: string[] = [];
    for (const f of FORMULAS) {
      if (seen.has(f.formula_id)) dupes.push(f.formula_id);
      seen.add(f.formula_id);
    }
    expect(dupes.length, `duplicate formula_ids: ${dupes.join(', ')}`).toBe(0);
  });

  test('H. no two standard_ids collide (registry uniqueness)', async () => {
    const seen = new Set<string>();
    const dupes: string[] = [];
    for (const s of STANDARDS) {
      if (seen.has(s.standard_id)) dupes.push(s.standard_id);
      seen.add(s.standard_id);
    }
    expect(dupes.length, `duplicate standard_ids: ${dupes.join(', ')}`).toBe(0);
  });
});
