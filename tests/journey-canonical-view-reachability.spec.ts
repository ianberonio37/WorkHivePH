/**
 * journey-canonical-view-reachability.spec.ts — Engine → Brain/Dashboard.
 * ========================================================================
 *
 * Catches the inverse-phantom class of silent failure: we BUILT a canonical
 * view (Engine tier) but nobody reads it. The forward audit
 * (audit_calm_dashboard_canonical) tells us when a dashboard reads a raw
 * table that has a wrapper available; THIS spec asks the opposite
 * question — when a wrapper exists, does ANY consumer actually use it?
 *
 * An unused canonical view is dead weight: it generates schema drift
 * risk, confuses future readers, and represents engineering effort
 * that didn't ship value.
 *
 * Coverage:
 *   1. Every CREATE [OR REPLACE] VIEW public.v_*_truth in supabase/migrations
 *      must have at least one consumer reference in HTML, edge function,
 *      or python_api/.
 *   2. Exemption: views explicitly tagged
 *      `-- canonical-view-allow: <reason>` in the migration.
 */
import { test, expect } from '@playwright/test';
import { promises as fs } from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');

async function walk(dir: string, exts: string[]): Promise<string[]> {
  const out: string[] = [];
  async function rec(d: string) {
    let entries;
    try { entries = await fs.readdir(d, { withFileTypes: true }); }
    catch { return; }
    for (const e of entries) {
      const full = path.join(d, e.name);
      if (e.isDirectory()) {
        // Skip noisy dirs
        if (['node_modules', '.git', 'test-results', 'playwright-report',
             '.tmp', 'dist', '__pycache__'].includes(e.name)) continue;
        await rec(full);
      } else if (exts.some(x => e.name.endsWith(x))) {
        out.push(full);
      }
    }
  }
  await rec(dir);
  return out;
}

let MIGRATION_TEXT_BY_FILE: Record<string, string> = {};
let CANONICAL_VIEWS: Array<{ view: string; migration: string; allow: string | null }> = [];
let CONSUMER_FILES: string[] = [];

test.beforeAll(async () => {
  // Collect canonical views from migrations
  const migrationFiles = await walk(path.join(ROOT, 'supabase', 'migrations'), ['.sql']);
  const VIEW_RE = /CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+public\.(v_\w+_truth)\s+AS/gi;
  const ALLOW_RE = /v_\w+_truth.*canonical-view-allow:\s*([^\n]+)/i;

  const seen = new Map<string, { migration: string; allow: string | null }>();
  // Pass 1: collect every CREATE [OR REPLACE] VIEW v_*_truth
  for (const f of migrationFiles) {
    const text = await fs.readFile(f, 'utf8');
    MIGRATION_TEXT_BY_FILE[f] = text;
    let m;
    VIEW_RE.lastIndex = 0;
    while ((m = VIEW_RE.exec(text)) !== null) {
      const view = m[1];
      // Look for an allow tag in the surrounding lines (within 5 lines before)
      const lines = text.split('\n');
      const idx = lines.findIndex(ln => ln.includes(`VIEW public.${view}`));
      const ctx = lines.slice(Math.max(0, idx - 5), idx + 1).join('\n');
      const allowMatch = ctx.match(/canonical-view-allow:\s*([^\n]+)/i);
      const allow = allowMatch ? allowMatch[1].trim() : null;
      // Last writer wins (latest migration for the same view name)
      seen.set(view, { migration: path.basename(f), allow });
    }
  }
  // Pass 2: scan ALL migrations for stand-alone "canonical-view-allow: <view>"
  // markers (used when the original migration is immutable and a follow-up
  // declaration migration carries the allow).
  const STANDALONE_ALLOW_RE = /canonical-view-allow:\s*(v_\w+_truth)\b([^\n]*)/gi;
  for (const f of migrationFiles) {
    const text = MIGRATION_TEXT_BY_FILE[f] || '';
    let m;
    STANDALONE_ALLOW_RE.lastIndex = 0;
    while ((m = STANDALONE_ALLOW_RE.exec(text)) !== null) {
      const view = m[1];
      const tail = (m[2] || '').trim();
      const reason = tail || `declared in ${path.basename(f)}`;
      if (seen.has(view) && !seen.get(view)!.allow) {
        seen.set(view, { migration: seen.get(view)!.migration, allow: reason });
      }
    }
  }
  for (const [view, info] of seen) {
    CANONICAL_VIEWS.push({ view, ...info });
  }

  // Collect consumer files (HTML + edge functions + python-api + js)
  const htmlFiles  = await walk(ROOT, ['.html']);
  const edgeFiles  = await walk(path.join(ROOT, 'supabase', 'functions'), ['.ts']);
  let pythonFiles: string[] = [];
  try { pythonFiles = await walk(path.join(ROOT, 'python-api'), ['.py']); } catch { /* may not exist */ }
  const jsFiles    = await walk(ROOT, ['.js']);
  CONSUMER_FILES = [...htmlFiles, ...edgeFiles, ...pythonFiles, ...jsFiles]
    .filter(f => !f.includes(path.join('supabase', 'migrations')))
    .filter(f => !f.includes('node_modules'))
    .filter(f => !f.includes('test-results'));
});

test.describe('Canonical View Reachability — Engine has at least one consumer', () => {

  test('every v_*_truth view in migrations has ≥1 consumer reference outside migrations', async () => {
    const orphans: Array<{ view: string; migration: string }> = [];
    const consumerCache: Record<string, string> = {};
    for (const f of CONSUMER_FILES) {
      consumerCache[f] = await fs.readFile(f, 'utf8').catch(() => '');
    }

    for (const { view, migration, allow } of CANONICAL_VIEWS) {
      if (allow) continue;  // explicitly exempt
      // Look for the view name in any consumer file
      let found = false;
      for (const f of CONSUMER_FILES) {
        if (consumerCache[f].includes(view)) { found = true; break; }
      }
      if (!found) orphans.push({ view, migration });
    }

    if (orphans.length > 0) {
      console.error(`Orphan canonical views (${orphans.length}) — built but unread:`);
      for (const o of orphans) console.error(`  - ${o.view} (created in ${o.migration})`);
      console.error(`Either wire a consumer or add a canonical-view-allow comment above the CREATE VIEW.`);
    }
    expect(orphans.length,
      `every canonical view must have ≥1 consumer or a documented canonical-view-allow exemption`).toBe(0);
  });

  test('canonical-view registry: at least 10 v_*_truth views shipped (regression floor)', async () => {
    expect(CANONICAL_VIEWS.length,
      `canonical-view inventory floor: should have at least 10 v_*_truth views`).toBeGreaterThanOrEqual(10);
  });
});
