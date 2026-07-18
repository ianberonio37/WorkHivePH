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
    // Team Pulse populates after loadPMHealth() resolves; the cell starts as "—" (em dash).
    // NOTE (2026-07-11): Team Pulse was FUSED — the visible PM-overdue tile was removed as
    // redundant with the alert cards + Open-Issues glance, so #pulse-pm-overdue is now a HIDDEN
    // canonical parity cell (still populated by loadTeamPulse). This test verifies the VALUE matches
    // pm-scheduler, not the tile's visibility, so wait for 'attached' (in DOM) not 'visible'.
    // pw-selector-allow: #pulse-pm-overdue lives in hive.html (HIVE_URL constant; validator's GOTO_RE matches literals only)
    const pulseLocator = whPage.locator('#pulse-pm-overdue');
    await pulseLocator.waitFor({ state: 'attached', timeout: 10_000 });
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
    // pw-selector-allow: #stat-overdue lives in pm-scheduler.html (SCHED_URL constant; validator's GOTO_RE matches literals only)
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

  test('check_pm_overdue_magnitude: get_hive_dashboard.pm_overdue_count == DISTINCT overdue assets', async ({ whPage }) => {
    // Locks the 2026-06-07 unify fix. The home (index.html) "PM Overdue" tile is
    // RPC-driven (get_hive_dashboard.pm_overdue_count) and links straight to
    // pm-scheduler, so it must equal pm-scheduler #stat-overdue — i.e. the count
    // of DISTINCT assets with an overdue scope item in the frequency-aware
    // canonical view. The direction-only invariant above slept through a 26-vs-4
    // magnitude gap (the tile read v_pm_compliance_truth.is_due, a flat-30-day
    // anchor proxy). This asserts the wiring EXACTLY, so a revert is caught.
    await whPage.goto(SCHED_URL, { waitUntil: 'domcontentloaded' });

    const { rpcOverdue, canonicalOverdue } = await whPage.evaluate(async () => {
      const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
      // @ts-expect-error db is a global hydrated by utils.js
      const { data: dash } = await db.rpc('get_hive_dashboard', { p_hive_id: hiveId });
      // @ts-expect-error db is a global hydrated by utils.js
      const { data: rows } = await db.from('v_pm_scope_items_truth')
        .select('pm_asset_id, is_overdue')
        .eq('hive_id', hiveId)
        .eq('is_overdue', true)
        .limit(5000);
      const distinct = new Set((rows || []).map((r: { pm_asset_id: string }) => r.pm_asset_id)).size;
      return { rpcOverdue: Number(dash?.pm_overdue_count ?? -1), canonicalOverdue: distinct };
    });

    expect(
      rpcOverdue,
      `get_hive_dashboard.pm_overdue_count = ${rpcOverdue} but v_pm_scope_items_truth has ${canonicalOverdue} ` +
      `distinct overdue assets — the home "PM Overdue" tile has drifted from the frequency-aware canonical view. ` +
      `Do NOT revert it to v_pm_compliance_truth.is_due (that was the inflated 26-vs-4 bug).`,
    ).toBe(canonicalOverdue);
  });

  test('check_critical_pm_overdue_integrity: nudge asset is genuinely overdue + critical', async ({ whPage }) => {
    // Guards the 2026-06-07 fix that added get_hive_dashboard.critical_pm_overdue
    // (drives the home "Critical PM Overdue" nudge, previously dead on the RPC
    // path). Also locks the case-insensitive criticality match: the seed stores
    // title-case 'Critical', so an `= 'critical'` filter silently returns nothing.
    // When the field is present it MUST be a real is_overdue + critical asset.
    await whPage.goto(SCHED_URL, { waitUntil: 'domcontentloaded' });
    const { crit, isRealCritOverdue } = await whPage.evaluate(async () => {
      const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
      // @ts-expect-error db is a global hydrated by utils.js
      const { data: dash } = await db.rpc('get_hive_dashboard', { p_hive_id: hiveId });
      const c = dash?.critical_pm_overdue || null;
      if (!c) return { crit: null, isRealCritOverdue: true }; // no critical-overdue asset is a valid state
      // @ts-expect-error db is a global hydrated by utils.js
      const { data: rows } = await db.from('v_pm_scope_items_truth')
        .select('asset_name, is_overdue, asset_criticality')
        .eq('hive_id', hiveId)
        .eq('pm_asset_id', c.pm_asset_id)
        .eq('is_overdue', true);
      const ok = (rows || []).some((r: { asset_criticality: string }) => (r.asset_criticality || '').toLowerCase() === 'critical');
      return { crit: c.asset_name as string, isRealCritOverdue: ok };
    });
    expect(
      isRealCritOverdue,
      `get_hive_dashboard.critical_pm_overdue returned "${crit}" but it is not an is_overdue + critical asset — ` +
      `the nudge would point at the wrong asset (check the case-insensitive criticality match).`,
    ).toBe(true);
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

    // pw-selector-allow: #stat-members lives in hive.html (HIVE_URL constant; validator's GOTO_RE matches literals only)
    const tileCount = await readIntFromText(await whPage.locator('#stat-members').textContent());

    // 2026-07-11: canonical corrected v_worker_truth → hive_members. #stat-members is set by
    // loadMembers() from hive_members (active), so THAT is its source of truth. v_worker_truth
    // (= worker_profiles ⨝ hive_members) exposes email/persona, so worker_profiles RLS correctly
    // restricts it to the caller's OWN row (privacy) — it returns 1, not the hive member count, so it
    // was never a valid canonical for a member COUNT and drifted to 1-vs-5. Compare to hive_members
    // active (page-scoped, RLS-visible to any member) — the tile's real source.
    const viewCount: number = await whPage.evaluate(async () => {
      const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
      // @ts-expect-error db is a global hydrated by utils.js
      const { count } = await db.from('hive_members')
        .select('worker_name', { count: 'exact', head: true })
        .eq('hive_id', hiveId)
        .eq('status', 'active');
      return count || 0;
    });

    expect(Number.isFinite(tileCount), `hive #stat-members did not resolve to a number`).toBe(true);
    expect(tileCount, `hive_members active count = ${viewCount} but hive #stat-members shows ${tileCount} — the members tile diverged from its hive_members source`).toBe(viewCount);
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
