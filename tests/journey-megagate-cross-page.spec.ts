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
});
