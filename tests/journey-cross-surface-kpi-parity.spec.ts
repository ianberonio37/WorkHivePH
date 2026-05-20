/**
 * Cross-Surface KPI Parity (Layer 2 sentinel).
 * =============================================
 * The user-visible symptom that triggered this spec:
 *
 *   home dashboard tile said "21 PM OVERDUE"
 *   pm-scheduler.html said "0 overdue PMs"
 *
 * Root cause: pm-scheduler.html read `pm_scope_items` raw and reimplemented
 * the due-date math (FREQ_DAYS + calcNextDue), while hive.html read the
 * canonical `v_pm_scope_items_truth` view. The two definitions of "overdue"
 * disagreed for never-completed items with no anchor_date.
 *
 * After the hardening loop, both surfaces share the same canonical view. This
 * spec locks the invariant at runtime: numbers a user reads on one page must
 * not contradict numbers on the destination page they click through to.
 *
 * Invariant tested
 *   N_scope_items_overdue (from hive Team Pulse tile)
 *     > 0  =>  M_assets_overdue (from pm-scheduler hero card)  >= 1
 *     = 0  =>  M_assets_overdue (from pm-scheduler hero card)  =  0
 *
 * Granularity differs (scope items vs assets), so we test the direction-only
 * invariant: any overdue scope items must roll up to at least one overdue
 * asset, and zero must mean zero. Equality is NOT asserted because hive
 * counts items and pm-scheduler counts assets — that's intentional.
 */
import { test, expect } from './_fixtures';

const HIVE_URL    = '/workhive/hive.html';
const SCHED_URL   = '/workhive/pm-scheduler.html';

async function readIntFromText(text: string | null | undefined): Promise<number> {
  if (!text) return NaN;
  const m = text.match(/-?\d+/);
  return m ? parseInt(m[0], 10) : NaN;
}

test.describe('cross-surface KPI parity', () => {

  test('check_pm_overdue_parity: hive tile and pm-scheduler hero agree on direction', async ({ whPage }) => {
    // ── Read PM Overdue from home dashboard ────────────────────────────────
    await whPage.goto(HIVE_URL, { waitUntil: 'domcontentloaded' });
    // Team Pulse tile populates after loadPMHealth() resolves; the cell starts
    // as "—" (em dash). Poll until it's a number or 5s passes.
    const pulseLocator = whPage.locator('#pulse-pm-overdue');
    await pulseLocator.waitFor({ state: 'visible', timeout: 10_000 });
    await whPage.waitForFunction(() => {
      const el = document.getElementById('pulse-pm-overdue');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 10_000 }).catch(() => { /* fall through; the assert below
                                              will surface the still-blank value */ });

    const hivePmOverdue = await readIntFromText(await pulseLocator.textContent());
    expect(
      Number.isFinite(hivePmOverdue),
      `hive Team Pulse #pulse-pm-overdue did not resolve to a number; was: "${await pulseLocator.textContent()}"`,
    ).toBe(true);

    // ── Read overdue ASSET count from PM Scheduler hero card ───────────────
    await whPage.goto(SCHED_URL, { waitUntil: 'domcontentloaded' });
    const heroLocator = whPage.locator('#stat-overdue');
    await heroLocator.waitFor({ state: 'visible', timeout: 10_000 });
    await whPage.waitForFunction(() => {
      const el = document.getElementById('stat-overdue');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 10_000 }).catch(() => { /* fall through */ });

    const schedAssetsOverdue = await readIntFromText(await heroLocator.textContent());
    expect(
      Number.isFinite(schedAssetsOverdue),
      `pm-scheduler #stat-overdue did not resolve to a number; was: "${await heroLocator.textContent()}"`,
    ).toBe(true);

    // ── Direction invariant ────────────────────────────────────────────────
    if (hivePmOverdue === 0) {
      expect(
        schedAssetsOverdue,
        `hive shows 0 PM scope items overdue but pm-scheduler shows ${schedAssetsOverdue} assets overdue — ` +
        `dashboards are disagreeing about whether the hive has overdue PM work. ` +
        `Both should read v_pm_scope_items_truth.`,
      ).toBe(0);
    } else {
      expect(
        schedAssetsOverdue,
        `hive shows ${hivePmOverdue} PM scope items overdue but pm-scheduler shows 0 assets overdue — ` +
        `this is the exact "21 vs 0" regression the canonical view fix resolved. ` +
        `pm-scheduler must read v_pm_scope_items_truth.`,
      ).toBeGreaterThanOrEqual(1);
    }
  });

  // The Team Pulse / verdict tiles on hive.html follow the Calm Dashboard
  // Contract — when the count is 0 the tile dims to `—` and the locator's
  // `state: 'visible'` waits time out. Reading via the page's `db` client
  // is the robust path: query the canonical view directly with whPage.evaluate
  // so we get the actual number regardless of UI hide-zero behaviour, then
  // navigate to the destination page and assert the hero matches direction.
  // This locks the wiring contract rather than the rendering contract.

  test('check_open_jobs_parity: v_logbook_truth count agrees with logbook #open-count', async ({ whPage }) => {
    await whPage.goto('/workhive/logbook.html', { waitUntil: 'networkidle' });
    // Supervisors land in team view by default which leaves _allEntries empty
    // until "Search Team" is clicked — so #open-count would be a UX-driven 0
    // regardless of canonical state. Wait for init's default-team-mode race
    // to settle, then force mine view + wait for the actual load.
    await whPage.waitForFunction(() => {
      // @ts-expect-error setViewMode is a page-scope function
      return typeof setViewMode === 'function';
    }, { timeout: 10_000 });
    await whPage.evaluate(async () => {
      // @ts-expect-error
      setViewMode('mine');
      // Give the async renderEntries -> loadEntries chain a tick to start
      await new Promise(r => setTimeout(r, 100));
    });
    await whPage.waitForFunction(() => {
      // @ts-expect-error
      const loaded = typeof _allEntries !== 'undefined' && _allEntries !== null;
      // @ts-expect-error
      return loaded && _allEntries.length > 0;
    }, { timeout: 15_000 }).catch(() => { /* if there's genuinely no data, expect 0 == 0 */ });

    const lbCount = await readIntFromText(await whPage.locator('#open-count').textContent());

    const viewCount: number = await whPage.evaluate(async () => {
      const workerName = localStorage.getItem('wh_last_worker');
      const hiveId     = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
      // @ts-expect-error db is a global hydrated by utils.js
      const { count } = await db.from('v_logbook_truth')
        .select('id', { count: 'exact', head: true })
        .eq('worker_name', workerName)
        .eq('hive_id', hiveId)
        .eq('status', 'Open');
      return count || 0;
    });

    // Direction invariant — strict equality is brittle because the page
    // limits to the 200 most-recent entries while the view query is unlimited.
    // Old Open WOs (rare but possible) can fall off the page's window even
    // though the view still counts them.
    if (viewCount === 0) {
      expect(lbCount, `view shows 0 open WOs but page #open-count shows ${lbCount} — canonical drift`).toBe(0);
    } else {
      expect(lbCount, `worker-scoped v_logbook_truth shows ${viewCount} open WOs but page #open-count shows 0 — canonical drift, page's filter or scope diverged from the view`).toBeGreaterThanOrEqual(1);
    }
  });

  test('check_low_stock_parity: v_inventory_items_truth count agrees with inventory #stat-low', async ({ whPage }) => {
    await whPage.goto('/workhive/inventory.html', { waitUntil: 'domcontentloaded' });
    // Wait for _items to actually populate. Initial DOM has #stat-low = "0",
    // and /\d+/ matches immediately, so a naive wait races initData.
    await whPage.waitForFunction(() => {
      // @ts-expect-error
      return typeof _items !== 'undefined' && _items.length > 0;
    }, { timeout: 15_000 }).catch(() => { /* hive truly has no items */ });

    const invCount = await readIntFromText(await whPage.locator('#stat-low').textContent());

    const viewCount: number = await whPage.evaluate(async () => {
      const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
      // @ts-expect-error db is a global hydrated by utils.js
      const { data } = await db.from('v_inventory_items_truth')
        .select('id, qty_on_hand, reorder_point, is_low_stock, status')
        .eq('hive_id', hiveId)
        .eq('status', 'approved')
        .limit(500);
      return (data || []).filter((r: { is_low_stock: boolean }) => r.is_low_stock === true).length;
    });

    expect(invCount, `v_inventory_items_truth shows ${viewCount} low-stock items (status='approved') but inventory #stat-low shows ${invCount} — canonical drift, page's stockStatus() diverges from view's is_low_stock`).toBe(viewCount);
  });

  test('check_members_parity: hive #stat-members agrees with v_worker_truth active count', async ({ whPage }) => {
    await whPage.goto(HIVE_URL, { waitUntil: 'domcontentloaded' });
    // Wait for loadMembers to set the count (initial DOM is "—" em-dash)
    await whPage.waitForFunction(() => {
      const el = document.getElementById('stat-members');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 15_000 }).catch(() => { /* hive may genuinely have only Pablo */ });

    const tileCount = await readIntFromText(await whPage.locator('#stat-members').textContent());

    const viewCount: number = await whPage.evaluate(async () => {
      const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
      // @ts-expect-error db is a global hydrated by utils.js
      const { count } = await db.from('v_worker_truth')
        .select('worker_name', { count: 'exact', head: true })
        .eq('hive_id', hiveId)
        .eq('hive_status', 'active');
      return count || 0;
    });

    expect(Number.isFinite(tileCount), `hive #stat-members did not resolve to a number`).toBe(true);
    expect(tileCount, `v_worker_truth active count = ${viewCount} but hive #stat-members shows ${tileCount} — canonical drift, page's hive_members count diverged from view`).toBe(viewCount);
  });

  test('check_inventory_reads_canonical_view: data load wires to v_inventory_items_truth', async ({ whPage }) => {
    // Network watcher: inventory.html must hit /rest/v1/v_inventory_items_truth
    // and must NOT GET /rest/v1/inventory_items (writes via .upsert / .delete
    // stay allowed since they target the underlying table). Locks the turn-2
    // hardening fix where inventory.html migrated 4 SELECTs to the view.
    const canonicalHits: string[] = [];
    const rawSelectHits: string[] = [];

    whPage.on('request', (req) => {
      const url = req.url();
      if (/\/rest\/v1\/v_inventory_items_truth/.test(url)) {
        canonicalHits.push(url);
      } else if (/\/rest\/v1\/inventory_items(\?|$)/.test(url) && req.method() === 'GET') {
        rawSelectHits.push(url);
      }
    });

    await whPage.goto('/workhive/inventory.html', { waitUntil: 'networkidle' });
    await whPage.waitForFunction(() => {
      // @ts-expect-error
      return typeof _items !== 'undefined' && _items.length > 0;
    }, { timeout: 15_000 }).catch(() => {});

    expect(
      canonicalHits.length,
      `inventory.html did not query v_inventory_items_truth — canonical view wire-up regressed`,
    ).toBeGreaterThanOrEqual(1);
    expect(
      rawSelectHits,
      `inventory.html issued GET .../inventory_items — raw SELECT is forbidden (writes allowed). Migrate to v_inventory_items_truth.`,
    ).toEqual([]);
  });

  test('check_community_reads_canonical_view: data load wires to v_community_posts_truth', async ({ whPage }) => {
    // Locks the turn-1 community_posts migration. The page WRITES community_posts
    // (update for pin/flag/public, insert for new posts) so raw .from() with
    // .update/.insert is allowed — only SELECTs must hit the view.
    const canonicalHits: string[] = [];
    const rawSelectHits: string[] = [];

    whPage.on('request', (req) => {
      const url = req.url();
      if (/\/rest\/v1\/v_community_posts_truth/.test(url)) {
        canonicalHits.push(url);
      } else if (/\/rest\/v1\/community_posts(\?|$)/.test(url) && req.method() === 'GET') {
        rawSelectHits.push(url);
      }
    });

    await whPage.goto('/workhive/community.html', { waitUntil: 'networkidle' });
    // Give the page a beat for the feed to load
    await whPage.waitForTimeout(1500);

    expect(canonicalHits.length, `community.html did not query v_community_posts_truth`).toBeGreaterThanOrEqual(1);
    expect(rawSelectHits, `community.html issued GET .../community_posts — raw SELECT is forbidden (writes allowed). Migrate to v_community_posts_truth.`).toEqual([]);
  });

  test('check_marketplace_reads_canonical_view: data load wires to v_marketplace_listings_truth', async ({ whPage }) => {
    // Locks the turn-1 marketplace_listings migration across 6 consumer
    // surfaces (asset-hub, marketplace, marketplace-admin, marketplace-seller,
    // marketplace-seller-profile, project-manager) + the marketplace-checkout
    // edge fn. Sample the marketplace.html surface — primary listings browser.
    const canonicalHits: string[] = [];
    const rawSelectHits: string[] = [];

    whPage.on('request', (req) => {
      const url = req.url();
      if (/\/rest\/v1\/v_marketplace_listings_truth/.test(url)) {
        canonicalHits.push(url);
      } else if (/\/rest\/v1\/marketplace_listings(\?|$)/.test(url) && req.method() === 'GET') {
        rawSelectHits.push(url);
      }
    });

    await whPage.goto('/workhive/marketplace.html', { waitUntil: 'networkidle' });
    await whPage.waitForTimeout(1500);

    expect(canonicalHits.length, `marketplace.html did not query v_marketplace_listings_truth`).toBeGreaterThanOrEqual(1);
    expect(rawSelectHits, `marketplace.html issued GET .../marketplace_listings — raw SELECT is forbidden (writes allowed). Migrate to v_marketplace_listings_truth.`).toEqual([]);
  });

  test('check_pm_scheduler_reads_canonical_view: data load wires to v_pm_scope_items_truth', async ({ whPage }) => {
    // The hardening fix MUST keep working: pm-scheduler.html should issue a
    // request to /rest/v1/v_pm_scope_items_truth, not /rest/v1/pm_scope_items.
    // We watch the network and assert the canonical view was queried at
    // least once, and that the raw table was NOT selected (writes are still
    // allowed; selects are forbidden).
    const canonicalHits: string[] = [];
    const rawSelectHits: string[] = [];

    whPage.on('request', (req) => {
      const url = req.url();
      if (/\/rest\/v1\/v_pm_scope_items_truth/.test(url)) {
        canonicalHits.push(url);
      } else if (/\/rest\/v1\/pm_scope_items(\?|$)/.test(url) && req.method() === 'GET') {
        rawSelectHits.push(url);
      }
    });

    await whPage.goto(SCHED_URL, { waitUntil: 'networkidle' });
    // Tile renders only after loadData() resolves
    await whPage.waitForFunction(() => {
      const el = document.getElementById('stat-overdue');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 15_000 }).catch(() => {});

    expect(
      canonicalHits.length,
      `pm-scheduler.html did not query v_pm_scope_items_truth — the canonical view wire-up regressed`,
    ).toBeGreaterThanOrEqual(1);

    expect(
      rawSelectHits,
      `pm-scheduler.html issued GET .../pm_scope_items — raw SELECT is forbidden on this page. ` +
      `Migrate the call to v_pm_scope_items_truth (the writes/inserts are allowed).`,
    ).toEqual([]);
  });

});
