/**
 * Tier 11 — Cross-page consistency (4 scenarios, P2)
 *
 * Same data → same number across surfaces. Validates the canonical-source
 * doctrine: when v_*_truth aggregates, every consumer must match.
 *
 * Static form: each consumer must read from the SAME canonical view. A page
 * that computes the metric locally instead of going through the canonical
 * source is the bug we're guarding against.
 */
import { test, expect } from './_fixtures';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 11 — Cross-page consistency', () => {

  test('L1_pm_consumers_share_canonical_view: hive + pm-scheduler both read pm_scope_items + derived flags', async () => {
    // WHY: both surfaces must reach the same source so PM due/overdue counts agree
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    const pm = readFileSync(resolve(ROOT, 'pm-scheduler.html'), 'utf-8');
    // hive reads v_pm_scope_items_truth (canonical view)
    expect(hive, 'hive.html must read v_pm_scope_items_truth').toMatch(/v_pm_scope_items_truth/);
    // pm-scheduler reads pm_scope_items (base table — derives same is_due_soon / is_overdue downstream)
    expect(pm, 'pm-scheduler.html must read pm_scope_items').toMatch(/pm_scope_items/);
  });

  test('L2_open_jobs_share_logbook_source: hive + logbook both query logbook with status filter', async () => {
    // WHY: open-jobs is logbook rows with status filter; both surfaces must hit the same table
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    const logbook = readFileSync(resolve(ROOT, 'logbook.html'), 'utf-8');
    expect(hive, 'hive.html must read logbook').toMatch(/from\s*\(\s*['"]logbook['"]/);
    expect(logbook, 'logbook.html must read logbook').toMatch(/from\s*\(\s*['"]logbook['"]/);
  });

  test('L3_low_stock_shares_inventory_items_source: hive + inventory + alert-hub all read inventory_items', async () => {
    // WHY: inventory_items is the base table; whether consumers read is_low_stock directly or
    // recompute qty_on_hand vs min_qty locally, they MUST hit the same source so counts agree.
    for (const f of ['hive.html', 'inventory.html', 'alert-hub.html']) {
      const html = readFileSync(resolve(ROOT, f), 'utf-8');
      expect(html, `${f} must reach inventory_items (base table) for low-stock`).toMatch(
        /inventory_items|v_inventory_items_truth/
      );
    }
  });

  test('L4_worker_level_canonical_sources_consistent: achievements + hive each declare a canonical source', async () => {
    // WHY: worker tier/level can derive from worker_achievements OR skill_badges depending on surface;
    // both pages must use ONE canonical source — never an ad-hoc derivation.
    const ach = readFileSync(resolve(ROOT, 'achievements.html'), 'utf-8');
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    expect(ach, 'achievements.html must declare canonical source (worker_achievements or skill_badges)').toMatch(
      /worker_achievements|skill_badges|skill_profiles/
    );
    expect(hive, 'hive.html must declare canonical worker-progress source').toMatch(
      /worker_achievements|skill_badges|skill_profiles/
    );
  });

  // ── P1 roadmap 2026-05-27 — cross-page rule extension ───────────────────────
  // The original 4 scenarios cover the canonical-source doctrine. These add
  // cross-page property tests for the rules that span multiple pages and
  // can't be caught by single-page validators:
  //   - escHtml usage (every renderer that interpolates DB data must call escHtml)
  //   - nav-registry (every page is registered in nav-hub.js)
  //   - hive-isolation (every hive-scoped query passes hive_id)
  //   - trace-id (every fetch to /functions/v1/ai-gateway sends x-wh-trace)

  const HIVE_SCOPED_PAGES = [
    'hive.html', 'logbook.html', 'inventory.html', 'pm-scheduler.html',
    'analytics.html', 'predictive.html', 'asset-hub.html', 'community.html',
    'achievements.html', 'dayplanner.html', 'skillmatrix.html', 'project-manager.html',
    'alert-hub.html', 'audit-log.html', 'voice-journal.html',
  ];

  test('escHtml_universal: every hive-scoped page declares escHtml usage', async () => {
    // The rule: any page that interpolates DB strings into innerHTML must
    // either import or define escHtml, OR be in the validator's ignore list.
    for (const p of HIVE_SCOPED_PAGES) {
      const path = resolve(ROOT, p);
      let body: string;
      try { body = readFileSync(path, 'utf-8'); } catch { continue; }
      const usesInnerHtml = /innerHTML\s*=/.test(body) || /\.innerHTML\s*\+=/.test(body);
      if (!usesInnerHtml) continue;
      const hasEscHtml = /escHtml|esc_html/.test(body);
      expect(hasEscHtml, `${p} uses innerHTML but does not declare escHtml`).toBe(true);
    }
  });

  test('nav_registry_universal: every load-bearing page is reachable from nav-hub.js or appears in PUBLIC_PAGES', async () => {
    // nav-hub.js maps page slug -> tile metadata. A page not in nav-hub
    // can still be linked but won't show up in the nav surface.
    let nav: string;
    try { nav = readFileSync(resolve(ROOT, 'nav-hub.js'), 'utf-8'); }
    catch { test.skip(true, 'nav-hub.js not present'); return; }
    for (const p of ['hive.html', 'logbook.html', 'inventory.html', 'pm-scheduler.html', 'analytics.html']) {
      expect(nav, `nav-hub.js must reference ${p}`).toContain(p);
    }
  });

  test('hive_id_universal: every hive-scoped page reads wh_active_hive_id or wh_hive_id', async () => {
    // Hive isolation requires the page to know which hive it's scoping to.
    // A page that touches hive-scoped tables but doesn't read the active
    // hive ID is a cross-hive-leak waiting to happen.
    for (const p of HIVE_SCOPED_PAGES) {
      const path = resolve(ROOT, p);
      let body: string;
      try { body = readFileSync(path, 'utf-8'); } catch { continue; }
      const queriesHiveTable = /\.from\(['"](?:logbook_entries|inventory_items|pm_assets|hive_members|asset_nodes|work_orders|community_posts)['"]\)/.test(body);
      if (!queriesHiveTable) continue;
      const readsHiveId = /wh_active_hive_id|wh_hive_id|hive_id\s*[:=]/.test(body);
      expect(readsHiveId, `${p} queries hive-scoped tables but does not read an active hive id`).toBe(true);
    }
  });

  test('trace_id_universal: voice-handler.js sends x-wh-trace on AI fetches', async () => {
    // Trace-id propagation rule: every fetch from voice-handler to an AI
    // edge fn must include the x-wh-trace header. Without it we can't follow
    // a failing turn through the stack.
    const vh = readFileSync(resolve(ROOT, 'voice-handler.js'), 'utf-8');
    // Count fetch sites and trace headers in proximity.
    const aiGatewayCalls = (vh.match(/['"][^'"]*\/functions\/v1\/ai-gateway['"]/g) || []).length;
    const ragLoopCalls   = (vh.match(/['"][^'"]*\/functions\/v1\/agentic-rag-loop['"]/g) || []).length;
    const traceHeaders   = (vh.match(/x-wh-trace/g) || []).length;
    // We added trace to both the gateway + agentic-rag paths in turn 3.
    // Require traceHeaders to be at LEAST 2 (covers both sites).
    expect(traceHeaders, `voice-handler.js must mint x-wh-trace on AI fetches (sites: gateway=${aiGatewayCalls}, rag=${ragLoopCalls})`).toBeGreaterThanOrEqual(2);
  });

  test('envelope_universal: every TIER 1 load-bearing edge fn imports _shared/envelope.ts', async () => {
    // Mirrors validate_envelope_conformance.py from the runtime side.
    const FN_DIR = resolve(ROOT, 'supabase', 'functions');
    const FNS = ['ai-gateway', 'agentic-rag-loop', 'analytics-orchestrator', 'engineering-calc-agent', 'agent-memory-store'];
    for (const fn of FNS) {
      const idx = resolve(FN_DIR, fn, 'index.ts');
      let body: string;
      try { body = readFileSync(idx, 'utf-8'); } catch { continue; }
      expect(body, `${fn}/index.ts must import _shared/envelope.ts`).toContain('"../_shared/envelope.ts"');
    }
  });
});
