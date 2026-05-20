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

  // FIXME(2026-05-20): the Team Pulse / verdict tiles on hive.html use the
  // Calm Dashboard Contract hide-zero pattern, so when the test hive has 0
  // open jobs / 0 low-stock items the tile is dimmed and locator.waitFor
  // ({ state: 'visible' }) times out. The pm_overdue parity test passes
  // because Pablo's seeded hive always has overdue PMs. Two fix options:
  //   (a) seed at least one open WO + one low-stock item before the run
  //   (b) read the canonical view directly via whPage.evaluate and only
  //       assert the destination-page hero (skip the source-tile read)
  // Pattern is proven by check_pm_overdue_parity; these two are next.
  test.fixme('check_open_jobs_parity: hive Open Jobs tile and logbook open-count agree on direction', async ({ whPage }) => {
    // Open WO count appears on the home dashboard (`#stat-open`) AND on the
    // logbook page header pill (`#open-count`). Both should read from
    // v_logbook_truth filtered by status='Open'. Direction invariant: if the
    // home tile shows N>0 open jobs the logbook open-count must show >=1; if
    // 0, both must be 0.
    await whPage.goto(HIVE_URL, { waitUntil: 'domcontentloaded' });
    const homeOpen = whPage.locator('#stat-open');
    await homeOpen.waitFor({ state: 'visible', timeout: 10_000 });
    await whPage.waitForFunction(() => {
      const el = document.getElementById('stat-open');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 10_000 }).catch(() => {});
    const homeCount = await readIntFromText(await homeOpen.textContent());

    await whPage.goto('/workhive/logbook.html', { waitUntil: 'domcontentloaded' });
    const lbOpen = whPage.locator('#open-count');
    await lbOpen.waitFor({ state: 'visible', timeout: 10_000 });
    await whPage.waitForFunction(() => {
      const el = document.getElementById('open-count');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 10_000 }).catch(() => {});
    const lbCount = await readIntFromText(await lbOpen.textContent());

    expect(Number.isFinite(homeCount), `hive #stat-open did not resolve to a number; was "${await homeOpen.textContent()}"`).toBe(true);
    expect(Number.isFinite(lbCount), `logbook #open-count did not resolve to a number; was "${await lbOpen.textContent()}"`).toBe(true);

    if (homeCount === 0) {
      expect(lbCount, `home tile shows 0 open jobs but logbook shows ${lbCount} — canonical drift, both should read v_logbook_truth`).toBe(0);
    } else {
      expect(lbCount, `home tile shows ${homeCount} open jobs but logbook shows 0 — canonical drift, both should read v_logbook_truth`).toBeGreaterThanOrEqual(1);
    }
  });

  test.fixme('check_low_stock_parity: hive low-stock tile and inventory low count agree on direction', async ({ whPage }) => {
    // Home tile (Team Pulse) renders `#pulse-stock-issues` from
    // v_inventory_items_truth filtered by qty_on_hand <= min_qty. Inventory
    // page renders `#stat-low` from the same view. Both should agree.
    await whPage.goto(HIVE_URL, { waitUntil: 'domcontentloaded' });
    const pulse = whPage.locator('#pulse-stock-issues');
    await pulse.waitFor({ state: 'visible', timeout: 10_000 });
    await whPage.waitForFunction(() => {
      const el = document.getElementById('pulse-stock-issues');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 10_000 }).catch(() => {});
    const homeCount = await readIntFromText(await pulse.textContent());

    await whPage.goto('/workhive/inventory.html', { waitUntil: 'domcontentloaded' });
    const invLow = whPage.locator('#stat-low');
    await invLow.waitFor({ state: 'visible', timeout: 10_000 });
    await whPage.waitForFunction(() => {
      const el = document.getElementById('stat-low');
      return el && /^\d+$/.test((el.textContent || '').trim());
    }, { timeout: 10_000 }).catch(() => {});
    const invCount = await readIntFromText(await invLow.textContent());

    expect(Number.isFinite(homeCount), `hive #pulse-stock-issues did not resolve to a number; was "${await pulse.textContent()}"`).toBe(true);
    expect(Number.isFinite(invCount), `inventory #stat-low did not resolve to a number; was "${await invLow.textContent()}"`).toBe(true);

    if (homeCount === 0) {
      expect(invCount, `home tile shows 0 stock issues but inventory shows ${invCount} low — canonical drift`).toBe(0);
    } else {
      expect(invCount, `home tile shows ${homeCount} stock issues but inventory shows 0 low — canonical drift`).toBeGreaterThanOrEqual(1);
    }
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
