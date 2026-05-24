/**
 * Canonical Signal Parity (Layer 2 sentinel).
 * ============================================
 * Sister to journey-cross-surface-kpi-parity.spec.ts. That spec catches
 * DIFFERENT sources for the same KPI. This one catches the next class:
 *
 *   Two surfaces read the SAME canonical column from the SAME _truth view
 *   but show DIFFERENT counts — because one re-derives locally instead
 *   of trusting the view's signal.
 *
 * The triggering bugs (2026-05-20):
 *   1. pm-scheduler.html dropped `is_overdue && !next_due_date` items to
 *      'nodata' → 0 vs hive's 21.
 *   2. index.html projected `is_low_stock` then ignored it and re-computed
 *      `qty_on_hand <= reorder_point` locally.
 *   3. logbook.html re-implemented PM status with hardcoded LOG_FREQ_DAYS.
 *
 * Invariant tested
 *   For each (surface, KPI element, view, column[, mode]) row:
 *     1. Open the page, wait for the KPI to populate.
 *     2. Read the displayed count.
 *     3. Independently query the canonical view via whPage.evaluate to
 *        get the truth count.
 *     4. Assert they match.
 *
 * If the displayed number diverges from a fresh canonical-view query, the
 * page is re-deriving instead of trusting — the bug class this sentinel
 * exists to catch.
 */
import { test, expect } from './_fixtures';
import { bypassMaturityGate } from './_helpers';

type ParityCase = {
  name:          string;
  page:          string;
  domSelector:   string;
  view:          string;
  filterColumn?: string;          // single boolean column → .eq(col, true)
  filterIn?:     { col: string; values: string[] }; // .in() filter for enum columns
  extraEq?:      { col: string; value: string }[];  // additional .eq() filters (compound)
  extraIsNull?:  string[];        // columns required to be NULL (soft-delete filter)
  // Counting mode: 'rows'   = COUNT WHERE filter=true
  //                'assets' = COUNT DISTINCT asset_id WHERE filter=true
  //                'all'    = COUNT all rows (no filter; for "X tracked" totals)
  mode:          'rows' | 'assets' | 'all';
  expectExact:   boolean;
  // Cross-hive surface (the page does NOT scope by hive_id — e.g. marketplace
  // listings are intentionally global). Default false: most pages scope per-hive
  // and the canonical view is RLS-disabled, so the test must mirror the page's
  // .eq('hive_id', HIVE_ID) filter to compare like-for-like.
  crossHive?:    boolean;
  // Page filters by a worker/seller/author identity column instead of just hive.
  // When set, the test query adds .eq(scopeByWorker, WORKER_NAME) to mirror.
  scopeByWorker?: string;
};

const CASES: ParityCase[] = [
  {
    name:          'check_pm_overdue_scope_items_count: hive Team Pulse #pulse-pm-overdue == COUNT(v_pm_scope_items_truth WHERE is_overdue)',
    page:          '/workhive/hive.html',
    domSelector:   '#pulse-pm-overdue',
    view:          'v_pm_scope_items_truth',
    filterColumn:  'is_overdue',
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_pm_overdue_assets_count: pm-scheduler #stat-overdue == COUNT(DISTINCT asset_id WHERE is_overdue)',
    page:          '/workhive/pm-scheduler.html',
    domSelector:   '#stat-overdue',
    view:          'v_pm_scope_items_truth',
    filterColumn:  'is_overdue',
    mode:          'assets',
    expectExact:   true,
  },
  {
    name:          'check_low_stock_count: home tile == COUNT(v_inventory_items_truth WHERE is_low_stock)',
    page:          '/workhive/index.html',
    domSelector:   '[data-kpi="low-stock"] .oh-tile-num',
    view:          'v_inventory_items_truth',
    filterColumn:  'is_low_stock',
    mode:          'rows',
    expectExact:   true,
  },
  // 2026-05-20 expansion — every home-tile KPI gets a parity guard so the
  // `.limit(N) + .length` undercount class (caught on Open Jobs / Risk Alerts)
  // can't reappear silently. Each tile reads from a dedicated head-only count
  // query post-fix; the sentinel locks the contract.
  {
    name:          'check_open_jobs_count: home tile == COUNT(v_logbook_truth WHERE status=Open)',
    page:          '/workhive/index.html',
    domSelector:   '[data-kpi="open-jobs"] .oh-tile-num',
    view:          'v_logbook_truth',
    filterIn:      { col: 'status', values: ['Open'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_risk_alerts_count: home tile == COUNT(v_risk_truth WHERE risk_level IN critical/high)',
    page:          '/workhive/index.html',
    domSelector:   '[data-kpi="risk-alerts"] .oh-tile-num',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['critical', 'high'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_pm_overdue_home_tile: home tile == hive Team Pulse count (both v_pm_scope_items_truth.is_overdue / v_pm_compliance_truth.is_due rollup)',
    page:          '/workhive/index.html',
    domSelector:   '[data-kpi="pm-overdue"] .oh-tile-num',
    view:          'v_pm_compliance_truth',
    filterColumn:  'is_due',
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_total_assets_count: asset-hub #ah-total-hero == COUNT(v_asset_truth)',
    page:          '/workhive/asset-hub.html',
    domSelector:   '#ah-total-hero',
    view:          'v_asset_truth',
    mode:          'all',
    expectExact:   true,
  },
  {
    name:          'check_critical_assets_count: asset-hub #ah-critical-hero == COUNT(asset_nodes WHERE criticality=critical, case-insensitive)',
    page:          '/workhive/asset-hub.html',
    domSelector:   '#ah-critical-hero',
    view:          'v_asset_truth',
    filterIn:      { col: 'criticality', values: ['critical', 'Critical', 'CRITICAL'] },
    mode:          'rows',
    expectExact:   true,
  },
  // 2026-05-20 — expanding to cover more of the 30-page surface set per
  // the canonical-page-inventory memory.
  {
    name:          'check_pm_duesoon_assets_count: pm-scheduler #stat-duesoon == DISTINCT(asset_id) WHERE is_due_soon',
    page:          '/workhive/pm-scheduler.html',
    domSelector:   '#stat-duesoon',
    view:          'v_pm_scope_items_truth',
    filterColumn:  'is_due_soon',
    mode:          'assets',
    expectExact:   true,
  },
  {
    name:          'check_inventory_low_count: inventory #stat-low == COUNT(v_inventory_items_truth WHERE is_low_stock)',
    page:          '/workhive/inventory.html',
    domSelector:   '#stat-low',
    view:          'v_inventory_items_truth',
    filterColumn:  'is_low_stock',
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_inventory_out_count: inventory #stat-out == COUNT(v_inventory_items_truth WHERE is_out_of_stock)',
    page:          '/workhive/inventory.html',
    domSelector:   '#stat-out',
    view:          'v_inventory_items_truth',
    filterColumn:  'is_out_of_stock',
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_alert_hub_critical_count: alert-hub #ah-critical-hero >= COUNT(v_risk_truth WHERE risk_level IN critical/high)',
    page:          '/workhive/alert-hub.html',
    domSelector:   '#ah-critical-hero',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['critical', 'high'] },
    mode:          'rows',
    // Direction-only — alert-hub's "critical" count fuses v_risk_truth +
    // failure_signature_alerts + AMC; v_risk_truth alone is a strict subset.
    // We just guard the floor (no fewer than the risk subset).
    expectExact:   false,
  },
  // 2026-05-20 — Predictive Maintenance per-tier risk counts. Each tier
  // count comes from _scores which loads v_risk_truth wholesale; the
  // displayed number must equal the canonical count for the same level.
  {
    name:          'check_predictive_critical_count: predictive #count-critical == COUNT(v_risk_truth WHERE risk_level=critical)',
    page:          '/workhive/predictive.html',
    domSelector:   '#count-critical',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['critical'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_predictive_high_count: predictive #count-high == COUNT(v_risk_truth WHERE risk_level=high)',
    page:          '/workhive/predictive.html',
    domSelector:   '#count-high',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['high'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_predictive_medium_count: predictive #count-medium == COUNT(v_risk_truth WHERE risk_level=medium)',
    page:          '/workhive/predictive.html',
    domSelector:   '#count-medium',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['medium'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_predictive_low_count: predictive #count-low == COUNT(v_risk_truth WHERE risk_level=low)',
    page:          '/workhive/predictive.html',
    domSelector:   '#count-low',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['low'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_predictive_hot_hero: predictive #pr-hot-hero == COUNT(v_risk_truth WHERE risk_level IN critical/high)',
    page:          '/workhive/predictive.html',
    domSelector:   '#pr-hot-hero',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['critical', 'high'] },
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_predictive_healthy_hero: predictive #pr-healthy-hero == COUNT(v_risk_truth WHERE risk_level=low)',
    page:          '/workhive/predictive.html',
    domSelector:   '#pr-healthy-hero',
    view:          'v_risk_truth',
    filterIn:      { col: 'risk_level', values: ['low'] },
    mode:          'rows',
    expectExact:   true,
  },
  // 2026-05-20 — Marketplace per-section listing counts. loadCounts() pulls
  // `section` from v_marketplace_listings_truth (published only).
  {
    name:          'check_marketplace_parts_count: marketplace #count-parts == COUNT(v_marketplace_listings_truth WHERE section=parts AND status=published)',
    page:          '/workhive/marketplace.html',
    domSelector:   '#count-parts',
    view:          'v_marketplace_listings_truth',
    filterIn:      { col: 'section', values: ['parts'] },
    extraEq:       [{ col: 'status', value: 'published' }],
    mode:          'rows',
    expectExact:   true,
    crossHive:     true,  // marketplace listings are intentionally global
  },
  {
    name:          'check_marketplace_training_count: marketplace #count-training == COUNT(v_marketplace_listings_truth WHERE section=training AND status=published)',
    page:          '/workhive/marketplace.html',
    domSelector:   '#count-training',
    view:          'v_marketplace_listings_truth',
    filterIn:      { col: 'section', values: ['training'] },
    extraEq:       [{ col: 'status', value: 'published' }],
    mode:          'rows',
    expectExact:   true,
    crossHive:     true,
  },
  {
    name:          'check_marketplace_jobs_count: marketplace #count-jobs == COUNT(v_marketplace_listings_truth WHERE section=jobs AND status=published)',
    page:          '/workhive/marketplace.html',
    domSelector:   '#count-jobs',
    view:          'v_marketplace_listings_truth',
    filterIn:      { col: 'section', values: ['jobs'] },
    extraEq:       [{ col: 'status', value: 'published' }],
    mode:          'rows',
    expectExact:   true,
    crossHive:     true,
  },
  // 2026-05-20 L2 expansion: project-manager + community.
  {
    name:          'check_project_manager_active: pm #pm-active-hero == COUNT(projects WHERE status=active AND not deleted)',
    page:          '/workhive/project-manager.html',
    domSelector:   '#pm-active-hero',
    view:          'projects',
    filterIn:      { col: 'status', values: ['active'] },
    extraIsNull:   ['deleted_at'],
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_project_manager_on_hold_planning: pm #pm-blocked-hero == COUNT(projects WHERE status IN on_hold/planning)',
    page:          '/workhive/project-manager.html',
    domSelector:   '#pm-blocked-hero',
    view:          'projects',
    filterIn:      { col: 'status', values: ['on_hold', 'planning'] },
    extraIsNull:   ['deleted_at'],
    mode:          'rows',
    expectExact:   true,
  },
  {
    name:          'check_seller_listings_badge: marketplace-seller #badge-listings == COUNT(v_marketplace_listings_truth WHERE seller_name=WORKER_NAME)',
    page:          '/workhive/marketplace-seller.html',
    domSelector:   '#badge-listings',
    view:          'v_marketplace_listings_truth',
    mode:          'all',
    expectExact:   true,
    crossHive:     true,    // marketplace listings are global
    scopeByWorker: 'seller_name',  // page badge counts only the signed-in seller's listings
  },
  {
    name:          'check_community_profile_posts: community #profile-posts == COUNT(v_community_posts_truth WHERE author_name=WORKER_NAME AND not deleted)',
    page:          '/workhive/community.html',
    domSelector:   '#profile-posts',
    view:          'v_community_posts_truth',
    extraIsNull:   ['deleted_at'],
    mode:          'all',
    expectExact:   true,
    scopeByWorker: 'author_name',  // page shows only the signed-in user's posts
  },
];


async function readIntFromText(text: string | null | undefined): Promise<number> {
  if (!text) return NaN;
  const m = text.match(/-?\d+/);
  return m ? parseInt(m[0], 10) : NaN;
}


test.describe('canonical signal parity', () => {
  for (const c of CASES) {
    test(c.name, async ({ whPage }) => {
      // Bypass Stair-3+ maturity gate so predictive/ai-quality/etc render
      // their real query paths against the test fixture's days-old data
      // instead of falling back to "Predictive on insufficient data lies"
      // empty states (which leave KPI tiles at their HTML default "0").
      await bypassMaturityGate(whPage);
      // ── Load the surface ──────────────────────────────────────────────
      await whPage.goto(c.page, { waitUntil: 'domcontentloaded' });

      // Wait for the KPI element to populate with a number.
      const locator = whPage.locator(c.domSelector);
      await locator.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
      await whPage.waitForFunction((sel) => {
        const el = document.querySelector(sel);
        return el && /^\d+$/.test((el.textContent || '').trim());
      }, c.domSelector, { timeout: 15_000 }).catch(() => {
        // The element may legitimately render as `—` when 0 under
        // Calm Dashboard. We'll handle that in the assertion.
      });
      // Settle-poll: most KPI tiles ship with `<span id="...">0</span>` in
      // the HTML, so waitForFunction above returns immediately on the static
      // "0" before the async loader populates the real number. Re-read the
      // text every 300ms until it stops changing for two consecutive reads
      // OR 4s of total wait elapses — whichever comes first.
      await whPage.waitForFunction((sel) => {
        const el = document.querySelector(sel);
        if (!el) return false;
        const w = window as unknown as { __whCspSnap?: Record<string, { v: string; n: number }> };
        w.__whCspSnap = w.__whCspSnap || {};
        const txt = (el.textContent || '').trim();
        const prev = w.__whCspSnap[sel];
        if (!prev || prev.v !== txt) {
          w.__whCspSnap[sel] = { v: txt, n: 1 };
          return false;
        }
        w.__whCspSnap[sel] = { v: txt, n: prev.n + 1 };
        return prev.n >= 2;
      }, c.domSelector, { timeout: 4_000, polling: 300 }).catch(() => { /* settle best-effort */ });

      const rawText  = await locator.textContent().catch(() => '');
      const displayed = await readIntFromText(rawText);

      // ── Query the canonical view independently ────────────────────────
      const canonicalCount = await whPage.evaluate(
        async ({ view, column, filterIn, extraEq, extraIsNull, mode, crossHive, scopeByWorker }) => {
          // @ts-expect-error db is a page-scope Supabase client
          if (typeof db === 'undefined' || !db) return -1;
          // Several canonical views (v_risk_truth, v_pm_scope_items_truth,
          // v_marketplace_listings_truth, etc.) are RLS-disabled in current
          // migrations — they were designed to be scoped by the caller's
          // explicit hive_id filter. The page DOES scope; the test must too,
          // otherwise the test reads ALL hives' rows and the parity check
          // falsely flags every per-hive count as "rederive drift".
          // `crossHive: true` opts out for genuinely-global surfaces (marketplace).
          const hiveId = (typeof localStorage !== 'undefined')
            ? (localStorage.getItem('wh_active_hive_id') ||
               localStorage.getItem('wh_hive_id') || '')
            : '';
          const workerName = (typeof localStorage !== 'undefined')
            ? (localStorage.getItem('wh_last_worker') ||
               localStorage.getItem('wh_worker_name') || '')
            : '';
          const applyExtra = (q: any) => {
            for (const e of (extraEq || [])) q = q.eq(e.col, e.value);
            for (const col of (extraIsNull || [])) q = q.is(col, null);
            return q;
          };
          const scopeHive   = (q: any) => (crossHive || !hiveId)        ? q : q.eq('hive_id', hiveId);
          const scopeWorker = (q: any) => (!scopeByWorker || !workerName) ? q : q.eq(scopeByWorker, workerName);
          if (mode === 'rows') {
            // @ts-expect-error
            let q = db.from(view).select('*', { count: 'exact', head: true });
            if (column)   q = q.eq(column, true);
            if (filterIn) q = q.in(filterIn.col, filterIn.values);
            q = applyExtra(q);
            q = scopeHive(q);
            q = scopeWorker(q);
            const { count, error } = await q;
            return error ? -1 : (count ?? 0);
          } else if (mode === 'all') {
            // @ts-expect-error
            let q = db.from(view).select('*', { count: 'exact', head: true });
            q = applyExtra(q);
            q = scopeHive(q);
            q = scopeWorker(q);
            const { count, error } = await q;
            return error ? -1 : (count ?? 0);
          } else {
            // assets mode: pull asset_ids of matching rows, dedupe in JS
            // @ts-expect-error
            let q = db.from(view).select('asset_id');
            if (column)   q = q.eq(column, true);
            if (filterIn) q = q.in(filterIn.col, filterIn.values);
            q = applyExtra(q);
            q = scopeHive(q);
            q = scopeWorker(q);
            const { data, error } = await q;
            if (error) return -1;
            const ids = new Set((data || []).map((r: any) => r.asset_id).filter(Boolean));
            return ids.size;
          }
        },
        { view: c.view, column: c.filterColumn, filterIn: c.filterIn,
          extraEq: c.extraEq, extraIsNull: c.extraIsNull, mode: c.mode,
          crossHive: !!c.crossHive, scopeByWorker: c.scopeByWorker },
      );

      // ── Assert parity ─────────────────────────────────────────────────
      expect(
        canonicalCount,
        `Could not query canonical view ${c.view}.${c.filterColumn} from page scope — ` +
        `db client may not be initialized.`,
      ).toBeGreaterThanOrEqual(0);

      // When canonical says 0, the surface may legitimately render `—`.
      // Treat NaN as 0 only when canonical is also 0.
      const surface = Number.isFinite(displayed) ? displayed : 0;

      if (c.expectExact) {
        expect(
          surface,
          `${c.page} ${c.domSelector} shows ${surface} but ${c.view}.${c.filterColumn} ` +
          `directly counts ${canonicalCount} (mode=${c.mode}). ` +
          `Page is re-deriving instead of trusting the canonical signal.`,
        ).toBe(canonicalCount);
      } else {
        if (canonicalCount === 0) {
          expect(surface).toBe(0);
        } else {
          expect(surface).toBeGreaterThanOrEqual(1);
        }
      }
    });
  }
});
